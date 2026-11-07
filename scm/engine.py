"""Ereignisdiskreter Simulationskern (SimPy).

Zeiteinheit: Tag. Modellzeit t = 0 beginnt am Start der Einschwingphase; Auswertungstag
te = t - warmup_days (Szenarien-Ereignisse und Ausgaben nutzen te).

Prozesse
  daily_process   Nachfrage -> Verkauf ab Fertigwarenlager -> Montage -> Bestellprüfung (s, Q) -> Tagesprotokoll
  order_process   Tier-2-Vorlauf -> Tier-1-Fertigung -> Transportkette (Routing, ggf. Umleitung) -> Wareneingang
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import simpy
from scipy.stats import poisson

from .config import Config
from .network import SupplyNetwork, Disruptions

K_PROD, K_T2, K_LEG, K_DEL, K_DEM = 1, 2, 3, 4, 5


@dataclass
class RunResult:
    scenario: str
    seed: int
    rep: int
    kpis: dict
    daily: pd.DataFrame
    events: pd.DataFrame
    legs: pd.DataFrame
    lead_by_comp: dict
    cost_breakdown: dict
    intervals: list
    cfg: Config = field(repr=False, default=None)


def plan_lead_days(cfg: Config, cid: str) -> float:
    """Geplante Wiederbeschaffungszeit (Modalwerte) – Basis des Bestellpunkts."""
    c = cfg.components[cid]
    s = cfg.suppliers[c.supplier]
    t2 = max([t.prod_days[1] + cfg.edges[t.edge].days[1] for t in s.tier2], default=0.0)
    ship = sum(cfg.edges[e].days[1] for e in cfg.base_routes[cid])
    return t2 + s.prod_days[1] + ship


def plan_unit_costs(cfg: Config, cid: str, qty: int | None = None) -> dict:
    """Stückkosten der Regelroute (Referenzrechnung, auch Testgrundlage)."""
    c = cfg.components[cid]
    q = qty or max(1, round(c.order_qty * cfg.p("order_q_factor")))
    net = SupplyNetwork(cfg)
    kg = q * c.weight_kg
    freight = sum(net.edge_cost(cfg.edges[e], kg) for e in cfg.base_routes[cid])
    co2 = sum(net.edge_co2(cfg.edges[e], kg) for e in cfg.base_routes[cid])
    goods = c.price_eur * q
    duty = c.duty_rate * (goods + freight)
    return dict(goods=goods / q, freight=freight / q, duty=duty / q, co2=co2 / q)


def reference_landed_cost(cfg: Config) -> float:
    """Handrechnung ohne Simulation: Σ(Einkauf+Fracht+Zoll) + Montagelohn."""
    a = cfg.p("assembly")
    parts = sum(sum(plan_unit_costs(cfg, c)[k] for k in ("goods", "freight", "duty")) for c in cfg.components)
    return parts + a["time_h_per_watch"] * a["wage_eur_h"]


class SimulationEngine:
    def __init__(self, cfg: Config, seed: int | None = None, rep: int = 0):
        self.cfg = cfg
        self.seed = int(cfg.p("seed") if seed is None else seed)
        self.rep = rep
        self.stoch = bool(cfg.p("stochastic"))
        self.net = SupplyNetwork(cfg)
        self.dis = Disruptions(cfg)
        self.warm = int(cfg.p("warmup_days"))
        self.H = int(cfg.p("horizon_days"))
        self.total = self.warm + self.H
        self.d_mean = cfg.p("annual_demand") / 365.0
        self.cids = list(cfg.components)
        self.focal = cfg.focal
        self.events, self.legs, self.daily_rows = [], [], []
        self.order_no = {c: 0 for c in self.cids}
        self.leads = {c: [] for c in self.cids}
        self.lead_max = 0.0

    # ------------------------------------------------------------------ Zufall
    def _rng(self, *key):
        return np.random.default_rng([self.seed, self.rep, *key])

    def tri(self, t3, *key):
        a, b, c = t3
        if not self.stoch or a == c:
            return b
        return float(self._rng(*key).triangular(a, b, c))

    # ------------------------------------------------------------------ Hilfen
    def te(self):
        return self.env.now - self.warm

    def log(self, typ, comp="", node="", qty=0, info=""):
        self.events.append(dict(day=round(self.te(), 3), type=typ, comp=comp, node=node, qty=qty, info=info))

    def safety_days(self, cid):
        c = self.cfg.components[cid]
        return self.cfg.p("safety_stock_days") if c.safety_days is None else c.safety_days

    def qty(self, cid):
        return max(1, round(self.cfg.components[cid].order_qty * self.cfg.p("order_q_factor")))

    # ------------------------------------------------------------------ Lager
    def _init_state(self):
        self.pool = {}
        self.on_order = {c: 0 for c in self.cids}
        self.s = {}
        for ci, cid in enumerate(self.cids):
            self.s[cid] = math.ceil(self.d_mean * (plan_lead_days(self.cfg, cid) + self.safety_days(cid)))
            u = plan_unit_costs(self.cfg, cid, self.qty(cid))
            n = self.s[cid] + self.qty(cid)
            self.pool[cid] = dict(units=n, goods=u["goods"] * n, freight=u["freight"] * n,
                                  duty=u["duty"] * n, co2=u["co2"] * n)
        a = self.cfg.p("assembly")
        self.labor_per_watch = a["time_h_per_watch"] * a["wage_eur_h"]
        self.cap = int(a["workers"] * a["shift_h"] // a["time_h_per_watch"])
        self.fg_target = math.ceil(self.d_mean * self.cfg.p("fg_target_days"))
        unit = {k: sum(plan_unit_costs(self.cfg, c, self.qty(c))[k] for c in self.cids)
                for k in ("goods", "freight", "duty", "co2")}
        n = self.fg_target
        self.fg = dict(units=n, goods=unit["goods"] * n, freight=unit["freight"] * n,
                       duty=unit["duty"] * n, labor=self.labor_per_watch * n, co2=unit["co2"] * n)
        self.carry = 0.0
        # Auswertungsgrößen
        self.m = dict(demand=0, lost=0, sold=0, assembled=0, goods=0.0, freight=0.0, duty=0.0,
                      labor=0.0, co2=0.0, outbound=0.0)
        regs = [n for n in self.cfg.nodes.values() if n.kind == "customer"]
        self.regions = [(r.id, r.share) for r in regs]
        self.out_edge = {e.dst: e for e in self.cfg.edges.values() if e.kind == "outbound"}

    def _take(self, pool, n):
        """n Einheiten zum gleitenden Durchschnittswert entnehmen; liefert entnommene Werte."""
        if n <= 0:
            return {k: 0.0 for k in pool if k != "units"}
        f = n / pool["units"]
        out = {k: v * f for k, v in pool.items() if k != "units"}
        for k in out:
            pool[k] -= out[k]
        pool["units"] -= n
        return out

    # ------------------------------------------------------------------ Prozesse
    def order_process(self, ci, cid, qty, no):
        env, cfg = self.env, self.cfg
        c = cfg.components[cid]
        sup = cfg.suppliers[c.supplier]
        t_order = env.now
        self.log("order", cid, sup.id, qty)
        ready = env.now
        for k, t2 in enumerate(sup.tier2):                      # Tier-2-Vorlauf
            start = self.dis.supplier_ready_at(t2.node, t_order - self.warm) + self.warm
            prod = self.tri(t2.prod_days, K_T2, ci, no, k)
            e = cfg.edges[t2.edge]
            tr = self.tri(e.days, K_T2, ci, no, 10 + k) * self.dis.transit_factor(e.mode, start - self.warm)
            arr = start + prod + tr
            self.legs.append(dict(kind="inbound", comp=cid, t0=start + prod - self.warm, t1=arr - self.warm,
                                  src=e.src, dst=e.dst, mode=e.mode, qty=qty, edge=e.id))
            ready = max(ready, arr)
        if ready > env.now:
            yield env.timeout(ready - env.now)
        start = self.dis.supplier_ready_at(sup.id, self.te()) + self.warm   # Tier-1-Fertigung
        if start > env.now:
            self.log("supplier_wait", cid, sup.id, qty, f"Ausfall bis Tag {start - self.warm:.0f}")
        prod = self.tri(sup.prod_days, K_PROD, ci, no)
        yield env.timeout(start + prod - env.now)
        self.log("shipped", cid, sup.id, qty)
        kg = qty * c.weight_kg
        pos, freight, co2, leg_no = sup.id, 0.0, 0.0, 0
        while pos != self.focal:                                 # Transportkette
            te = self.te()
            route = self.net.plan_route(cid, pos, te, self.dis, kg)
            if route is None:
                if leg_no == 0 or True:
                    self.log("route_wait", cid, pos, qty, "keine offene Route")
                yield env.timeout(1)
                continue
            e = cfg.edges[route[0]]
            if leg_no >= 0 and e.id not in cfg.base_routes[cid]:
                self.log("reroute", cid, pos, qty, f"Umleitung über {e.id}")
            dur = self.tri(e.days, K_LEG, ci, no, leg_no) * self.dis.transit_factor(e.mode, te)
            freight += self.net.edge_cost(e, kg)
            co2 += self.net.edge_co2(e, kg)
            self.legs.append(dict(kind="inbound", comp=cid, t0=te, t1=te + dur, src=e.src, dst=e.dst,
                                  mode=e.mode, qty=qty, edge=e.id))
            yield env.timeout(dur)
            pos = e.dst
            leg_no += 1
        goods = c.price_eur * qty
        duty = c.duty_rate * (goods + freight)
        p = self.pool[cid]
        p["units"] += qty; p["goods"] += goods; p["freight"] += freight; p["duty"] += duty; p["co2"] += co2
        self.on_order[cid] -= qty
        lead = env.now - t_order
        self.log("receipt", cid, self.focal, qty, f"Lieferzeit {lead:.1f} d")
        if self.te() >= 0:
            self.leads[cid].append(lead)
            self.lead_max = max(self.lead_max, lead)

    def _demand(self, day, te):
        lam = self.d_mean * self.dis.demand_factor(te)
        if self.stoch:
            return int(poisson.ppf(self._u[day], lam))
        self.carry += lam
        n = int(self.carry)
        self.carry -= n
        return n

    def daily_process(self):
        env, cfg = self.env, self.cfg
        a = cfg.p("assembly")
        self._u = self._rng(K_DEM).random(self.total + 1)
        for day in range(self.total):
            te = day - self.warm
            ev = te >= 0
            # 1) Nachfrage und Verkauf ab Fertigwarenlager (Verlustverkauf bei Fehlmenge)
            demand = self._demand(day, te)
            sold = min(self.fg["units"], demand)
            lost = demand - sold
            taken = self._take(self.fg, sold)
            if sold:
                self._distribute(day, te, sold, ev)
            # 2) Montage (make-to-stock bis Zielbestand), nur an Arbeitstagen
            asm = 0
            if (day % 7) < a["workdays_per_week"]:
                gap = max(0, self.fg_target - self.fg["units"])
                asm = int(min(self.cap, gap, min(self.pool[c]["units"] for c in self.cids)))
            if asm:
                tot = dict(goods=0.0, freight=0.0, duty=0.0, co2=0.0)
                for c in self.cids:
                    t = self._take(self.pool[c], asm)
                    for k in tot:
                        tot[k] += t[k]
                labor = asm * self.labor_per_watch
                for k in tot:
                    self.fg[k] += tot[k]
                self.fg["labor"] += labor
                self.fg["units"] += asm
                if ev:
                    for k in tot:
                        self.m[k] += tot[k]
                    self.m["labor"] += labor
                    self.m["assembled"] += asm
            if ev:
                self.m["demand"] += demand; self.m["lost"] += lost; self.m["sold"] += sold
            # 3) Bestellprüfung (s, Q)
            for ci, cid in enumerate(self.cids):
                ip = self.pool[cid]["units"] + self.on_order[cid]
                n = 0
                while ip <= self.s[cid] and n < 10:
                    q = self.qty(cid)
                    self.on_order[cid] += q
                    ip += q
                    n += 1
                    self.order_no[cid] += 1
                    env.process(self.order_process(ci, cid, q, self.order_no[cid]))
            # 4) Tagesprotokoll
            row = dict(day=te, demand=demand, sold=sold, lost=lost, assembled=asm, fg=self.fg["units"])
            inv = 0.0
            for c in self.cids:
                p = self.pool[c]
                row[f"stock_{c}"] = p["units"]
                row[f"onorder_{c}"] = self.on_order[c]
                inv += p["goods"] + p["freight"] + p["duty"]
            fgv = self.fg["goods"] + self.fg["freight"] + self.fg["duty"] + self.fg["labor"]
            row["inventory_value"] = inv + fgv
            self.daily_rows.append(row)
            yield env.timeout(1)

    def _distribute(self, day, te, sold, ev):
        """Auslieferung an Kundenregionen (Largest-Remainder-Aufteilung)."""
        raw = [(rid, sold * sh) for rid, sh in self.regions]
        base = {rid: int(x) for rid, x in raw}
        rest = sold - sum(base.values())
        for rid, x in sorted(raw, key=lambda z: z[1] - int(z[1]), reverse=True)[:rest]:
            base[rid] += 1
        for k, (rid, n) in enumerate(base.items()):
            if n <= 0:
                continue
            e = self.out_edge[rid]
            dur = self.tri(e.days, K_DEL, day, k)
            if ev:
                self.m["outbound"] += n * self.cfg.p("watch_pack_kg") * e.eur_per_kg
            self.legs.append(dict(kind="outbound", comp="uhr", t0=te, t1=te + dur, src=e.src, dst=e.dst,
                                  mode=e.mode, qty=n, edge=e.id))

    # ------------------------------------------------------------------ Lauf
    def run(self) -> RunResult:
        self.env = simpy.Environment()
        self._init_state()
        self.env.process(self.daily_process())
        self.env.run(until=self.total)
        daily = pd.DataFrame(self.daily_rows)
        daily = daily[daily["day"] >= 0].reset_index(drop=True)
        events = pd.DataFrame(self.events)
        legs = pd.DataFrame(self.legs)
        m = self.m
        n = max(1, m["assembled"])
        years = self.H / 365.0
        avg_inv = float(daily["inventory_value"].mean())
        lead_by = {c: (float(np.mean(v)) if v else float("nan")) for c, v in self.leads.items()}
        valid = [v for v in lead_by.values() if not math.isnan(v)]
        breakdown = dict(
            einkauf=m["goods"] / n, fracht=m["freight"] / n, zoll=m["duty"] / n, montage=m["labor"] / n,
            lager=avg_inv * self.cfg.p("holding_cost_rate") * years / n,
            versand=m["outbound"] / max(1, m["sold"]))
        kpis = dict(
            landed_cost=breakdown["einkauf"] + breakdown["fracht"] + breakdown["zoll"] + breakdown["montage"],
            lieferzeit=max(valid) if valid else float("nan"),
            servicegrad=1.0 - m["lost"] / m["demand"] if m["demand"] else 1.0,
            co2=m["co2"] / n,
            lagerwert=avg_inv,
            # Zusatzgrößen (nicht Zielkriterium)
            lagerhaltungskosten=breakdown["lager"], lieferzeit_max=self.lead_max,
            uhren_montiert=m["assembled"], nachfrage=m["demand"], fehlmenge=m["lost"])
        return RunResult(self.cfg.scenario_name, self.seed, self.rep, kpis, daily, events, legs, lead_by,
                         breakdown, self.dis.intervals(), self.cfg)
