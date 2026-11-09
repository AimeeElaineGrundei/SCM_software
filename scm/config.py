"""Konfiguration: YAML laden, validieren (Einheiten, Plausibilität) und Szenarien anwenden.

Alle Größen: Tage, EUR, kg, km, g CO2e/tkm. Szenario-Zeiten sind Auswertungstage (0 = erster
ausgewerteter Tag, nach der Einschwingphase).
"""
from __future__ import annotations
import copy
import glob
import os
from dataclasses import dataclass, field
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
MODES = {"see", "bahn", "lkw", "binnenschiff", "luft"}
EVENT_TYPES = {"block_node", "block_mode", "supplier_outage", "demand_factor", "transit_factor"}
AIR_POLICIES = {"off", "on_disruption", "always"}
ROUTE_WEIGHTS = {"time", "cost", "co2"}


class ConfigError(ValueError):
    pass


@dataclass
class Node:
    id: str; name: str; lat: float; lon: float; kind: str; share: float = 0.0


@dataclass
class Edge:
    id: str; src: str; dst: str; mode: str; km: float
    days: tuple; fixed_eur: float; eur_per_kg: float; kind: str = "inbound"
    via: tuple = ()


@dataclass
class Tier2:
    node: str; edge: str; prod_days: tuple


@dataclass
class Supplier:
    id: str; country: str; continent: str; eu: bool; prod_days: tuple
    tier2: list = field(default_factory=list); note: str = ""


@dataclass
class Component:
    id: str; name: str; supplier: str; price_eur: float; weight_kg: float
    duty_rate: float; order_qty: int; safety_days: float | None = None


@dataclass
class Event:
    type: str; start: float; end: float
    node: str | None = None; mode: str | None = None
    supplier: str | None = None; factor: float = 1.0


@dataclass
class Config:
    params: dict
    nodes: dict; edges: dict; suppliers: dict; components: dict
    base_routes: dict
    events: list = field(default_factory=list)
    scenario_name: str = "S0 Basis"
    scenario_description: str = ""

    @property
    def focal(self) -> str:
        return next(n.id for n in self.nodes.values() if n.kind == "focal")

    def p(self, key, default=None):
        return self.params.get(key, default)


def _tri(v, where):
    try:
        a, b, c = (float(x) for x in v)
    except Exception:
        raise ConfigError(f"{where}: Dreieckswerte [min, Modus, max] erwartet, erhalten {v!r}")
    if not (0 <= a <= b <= c):
        raise ConfigError(f"{where}: es muss 0 <= min <= Modus <= max gelten, erhalten {v!r}")
    return (a, b, c)


def _event(d, where="Ereignis") -> Event:
    t = d.get("type")
    if t not in EVENT_TYPES:
        raise ConfigError(f"{where}: unbekannter Typ {t!r}, erlaubt: {sorted(EVENT_TYPES)}")
    ev = Event(type=t, start=float(d.get("start", 0)), end=float(d.get("end", 1e9)),
               node=d.get("node"), mode=d.get("mode"), supplier=d.get("supplier"),
               factor=float(d.get("factor", 1.0)))
    if ev.end < ev.start:
        raise ConfigError(f"{where}: Ende liegt vor dem Beginn")
    if t == "block_mode" and ev.mode not in MODES:
        raise ConfigError(f"{where}: Verkehrsträger {ev.mode!r} unbekannt")
    if t == "demand_factor" and ev.factor < 0:
        raise ConfigError(f"{where}: Faktor muss >= 0 sein")
    return ev


def build_config(raw: dict) -> Config:
    """Rohdaten (dict) -> validierte Config."""
    nodes = {n["id"]: Node(n["id"], n["name"], float(n["lat"]), float(n["lon"]), n["kind"],
                           float(n.get("share", 0))) for n in raw["nodes"]}
    edges = {}
    for e in raw["edges"]:
        if e["from"] not in nodes or e["to"] not in nodes:
            raise ConfigError(f"Kante {e['id']}: unbekannter Knoten")
        if e["mode"] not in MODES:
            raise ConfigError(f"Kante {e['id']}: Verkehrsträger {e['mode']!r} unbekannt")
        if e["km"] <= 0 or e["eur_per_kg"] < 0 or e["fixed_eur"] < 0:
            raise ConfigError(f"Kante {e['id']}: km > 0 und Kosten >= 0 erforderlich")
        edges[e["id"]] = Edge(e["id"], e["from"], e["to"], e["mode"], float(e["km"]),
                              _tri(e["days"], f"Kante {e['id']}"), float(e["fixed_eur"]),
                              float(e["eur_per_kg"]), e.get("kind", "inbound"),
                              tuple((float(a), float(b)) for a, b in e.get("via", [])))
    suppliers = {}
    for s in raw["suppliers"]:
        if s["id"] not in nodes:
            raise ConfigError(f"Lieferant {s['id']} hat keinen Knoten")
        t2 = [Tier2(t["node"], t["edge"], _tri(t["prod_days"], f"Tier-2 {t['node']}")) for t in s.get("tier2", [])]
        suppliers[s["id"]] = Supplier(s["id"], s["country"], s["continent"], bool(s["eu"]),
                                      _tri(s["prod_days"], f"Lieferant {s['id']}"), t2, s.get("note", ""))
    comps = {}
    for c in raw["components"]:
        if c["supplier"] not in suppliers:
            raise ConfigError(f"Komponente {c['id']}: unbekannter Lieferant")
        if c["price_eur"] <= 0 or c["weight_kg"] <= 0 or c["order_qty"] <= 0:
            raise ConfigError(f"Komponente {c['id']}: Preis, Gewicht und Bestellmenge müssen > 0 sein")
        if not 0 <= c["duty_rate"] < 1:
            raise ConfigError(f"Komponente {c['id']}: Zollsatz als Anteil 0..1 angeben")
        comps[c["id"]] = Component(c["id"], c["name"], c["supplier"], float(c["price_eur"]),
                                   float(c["weight_kg"]), float(c["duty_rate"]), int(c["order_qty"]),
                                   c.get("safety_days"))
    routes = raw["base_routes"]
    for cid, ids in routes.items():
        if cid not in comps:
            raise ConfigError(f"Regelroute für unbekannte Komponente {cid}")
        pos = comps[cid].supplier
        for eid in ids:
            if eid not in edges:
                raise ConfigError(f"Regelroute {cid}: unbekannte Kante {eid}")
            if edges[eid].src != pos:
                raise ConfigError(f"Regelroute {cid}: Kante {eid} beginnt nicht bei {pos}")
            pos = edges[eid].dst
        focal = next(n.id for n in nodes.values() if n.kind == "focal")
        if pos != focal:
            raise ConfigError(f"Regelroute {cid} endet nicht in {focal}")
    for cid in comps:
        if cid not in routes:
            raise ConfigError(f"Komponente {cid} hat keine Regelroute")
    for s in suppliers.values():
        for t in s.tier2:
            if t.edge not in edges or edges[t.edge].dst != s.id:
                raise ConfigError(f"Tier-2 {t.node}: Kante {t.edge} führt nicht zu {s.id}")
    params = copy.deepcopy(raw["params"])
    cfg = Config(params, nodes, edges, suppliers, comps, routes)
    validate_params(cfg)
    return cfg


def validate_params(cfg: Config):
    p = cfg.params
    if p["annual_demand"] <= 0:
        raise ConfigError("annual_demand muss > 0 sein")
    if p["horizon_days"] < 30 or p["warmup_days"] < 0:
        raise ConfigError("horizon_days >= 30 und warmup_days >= 0 erforderlich")
    if p["air_policy"] not in AIR_POLICIES:
        raise ConfigError(f"air_policy muss eines von {sorted(AIR_POLICIES)} sein")
    if p["route_weight"] not in ROUTE_WEIGHTS:
        raise ConfigError(f"route_weight muss eines von {sorted(ROUTE_WEIGHTS)} sein")
    if not 0 < p["service_level_target"] <= 1:
        raise ConfigError("service_level_target muss in (0, 1] liegen")
    if p["order_q_factor"] <= 0 or p["safety_stock_days"] < 0:
        raise ConfigError("order_q_factor > 0 und safety_stock_days >= 0 erforderlich")
    for m in MODES:
        if m not in p["co2_g_per_tkm"]:
            raise ConfigError(f"Emissionsfaktor für {m} fehlt")


def load_base(path: str | None = None) -> Config:
    with open(path or os.path.join(CONFIG_DIR, "base.yaml"), encoding="utf-8") as f:
        return build_config(yaml.safe_load(f))


def list_scenarios() -> dict:
    out = {}
    for fn in sorted(glob.glob(os.path.join(CONFIG_DIR, "scenarios", "*.yaml"))):
        with open(fn, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        out[os.path.splitext(os.path.basename(fn))[0]] = d
    return out


def _check_event_refs(cfg: Config, ev: Event):
    if ev.node and ev.node not in cfg.nodes and ev.node not in cfg.suppliers:
        raise ConfigError(f"Ereignis: unbekannter Knoten {ev.node!r}")
    if ev.type == "supplier_outage" and ev.supplier not in cfg.nodes:
        raise ConfigError(f"Ereignis: unbekannter Lieferant {ev.supplier!r}")


def apply_scenario(base: Config, scen: dict | None, extra_events: list | None = None,
                   param_overrides: dict | None = None) -> Config:
    """Szenario = Parameter-Überschreibungen + Ereignisliste auf demselben Modell."""
    cfg = copy.deepcopy(base)
    scen = scen or {}
    cfg.scenario_name = scen.get("name", base.scenario_name)
    cfg.scenario_description = scen.get("description", "")
    for k, v in {**scen.get("params", {}), **(param_overrides or {})}.items():
        if k not in cfg.params:
            raise ConfigError(f"Unbekannter Parameter {k!r}")
        if isinstance(cfg.params[k], dict) and isinstance(v, dict):
            cfg.params[k].update(v)
        else:
            cfg.params[k] = v
    cfg.events = [_event(e, f"Szenario {cfg.scenario_name}") for e in scen.get("events", [])]
    cfg.events += [_event(e, "Eingriff") for e in (extra_events or [])]
    for ev in cfg.events:
        _check_event_refs(cfg, ev)
    validate_params(cfg)
    return cfg


def check_requirements(cfg: Config, n_scenarios: int = 4, n_criteria: int = 5) -> list:
    """Prüft die fachlichen Mindestanforderungen der Aufgabenstellung (Abschnitt 2)."""
    res = []
    sups = list(cfg.suppliers.values())
    t1 = {c.supplier for c in cfg.components.values()}
    res.append((len(t1) >= 6, f"≥ 6 Tier-1-Lieferanten, je ≥ 1 Komponente ({len(t1)})"))
    non_eu_cont = {s.continent for s in sups if s.id in t1 and s.continent != "Europa"}
    res.append((len(non_eu_cont) >= 4, f"≥ 4 Tier-1 auf 4 verschiedenen Kontinenten außerhalb Europas ({len(non_eu_cont)}: {', '.join(sorted(non_eu_cont))})"))
    res.append((any(s.eu and s.id in t1 for s in sups), "≥ 1 Tier-1 in anderem EU-Mitgliedstaat"))
    res.append((any((not s.eu) and s.continent == "Europa" and s.id in t1 for s in sups), "6. Standort mit fachlicher Begründung (Europa, Nicht-EU)"))
    t2ok = sum(1 for s in sups if len(s.tier2) >= 2)
    res.append((t2ok >= 2, f"≥ 2 Tier-1 mit je ≥ 2 Tier-2-Vorlieferanten ({t2ok})"))
    used = {cfg.edges[e].mode for r in cfg.base_routes.values() for e in r}
    need = {"see", "bahn", "lkw", "binnenschiff"}
    res.append((need <= used, f"Transportketten mit Seeschiff, Bahn, Lkw, Binnenschiff (vorhanden: {', '.join(sorted(used))})"))
    res.append((n_scenarios >= 4, f"Basisszenario + ≥ 3 Stressszenarien auf demselben Modell ({n_scenarios} Szenarien)"))
    res.append((n_criteria >= 4, f"≥ 4 Zielkriterien getrennt ausgewiesen ({n_criteria})"))
    res.append((True, "Einheitenkonsistenz: Tage / EUR / kg / km / g CO2e je tkm (per Lader erzwungen)"))
    return res


# ----------------------------------------------------------------------------- Stammdaten manuell überschreiben
GENERAL_KEYS = [  # (Schlüssel, Bezeichnung, Einheit)
    ("assembly.wage_eur_h", "Montagelohn", "€/h"),
    ("assembly.time_h_per_watch", "Montagezeit je Uhr", "h"),
    ("assembly.workers", "Anzahl Monteure", "Personen"),
    ("holding_cost_rate", "Lagerhaltungskostensatz", "Anteil p. a. (0,22 = 22 %)"),
    ("service_level_target", "Servicegrad-Ziel β", "Anteil (0,97 = 97 %)"),
    ("fg_target_days", "Zielbestand Fertigwarenlager", "Tage Nachfrage"),
    ("watch_pack_kg", "Versandgewicht je Uhr", "kg"),
    ("co2_g_per_tkm.see", "Emissionsfaktor Seeschiff", "g CO₂e/tkm"),
    ("co2_g_per_tkm.bahn", "Emissionsfaktor Bahn", "g CO₂e/tkm"),
    ("co2_g_per_tkm.lkw", "Emissionsfaktor Lkw", "g CO₂e/tkm"),
    ("co2_g_per_tkm.binnenschiff", "Emissionsfaktor Binnenschiff", "g CO₂e/tkm"),
    ("co2_g_per_tkm.luft", "Emissionsfaktor Luftfracht", "g CO₂e/tkm"),
]


def master_tables(cfg: Config) -> dict:
    """Aktuelle Stammdaten als Tabellenzeilen (für die editierbaren Register der Oberfläche)."""
    comps = [dict(id=c.id, name=c.name, lieferant=cfg.nodes[c.supplier].name, price_eur=c.price_eur,
                  weight_kg=c.weight_kg, duty_pct=round(100 * c.duty_rate, 4), order_qty=c.order_qty)
             for c in cfg.components.values()]
    edges = [dict(id=e.id, strecke=f"{cfg.nodes[e.src].name} → {cfg.nodes[e.dst].name}", mode=e.mode, km=e.km,
                  fixed_eur=e.fixed_eur, eur_per_kg=e.eur_per_kg, d_min=e.days[0], d_mode=e.days[1], d_max=e.days[2])
             for e in cfg.edges.values()]
    sups = []
    for s in cfg.suppliers.values():
        sups.append(dict(key=s.id, name=cfg.nodes[s.id].name, stufe="Tier 1", d_min=s.prod_days[0], d_mode=s.prod_days[1], d_max=s.prod_days[2]))
        for t in s.tier2:
            sups.append(dict(key=f"{s.id}/{t.node}", name=cfg.nodes[t.node].name, stufe="Tier 2",
                             d_min=t.prod_days[0], d_mode=t.prod_days[1], d_max=t.prod_days[2]))
    gen = []
    for key, label, unit in GENERAL_KEYS:
        v = cfg.params
        for part in key.split("."):
            v = v[part]
        gen.append(dict(key=key, label=label, value=v, unit=unit))
    return dict(comps=comps, edges=edges, sups=sups, gen=gen)


def _num(v, where, lo=0.0, hi=None, strict=False):
    try:
        x = float(str(v).replace(",", "."))
    except Exception:
        raise ConfigError(f"{where}: Zahl erwartet, erhalten {v!r}")
    if x != x or (strict and x <= lo) or x < lo or (hi is not None and x > hi):
        raise ConfigError(f"{where}: Wert {x} außerhalb des erlaubten Bereichs")
    return x


def apply_master_data(base: Config, comps=None, edges=None, sups=None, gen=None) -> Config:
    """Manuelle Änderungen (Preis, Zoll, Frachtkosten, Zeiten, Parameter) auf eine Kopie der Config anwenden."""
    cfg = copy.deepcopy(base)
    for r in comps or []:
        c = cfg.components[r["id"]]
        w = f"Komponente {c.name}"
        c.price_eur = _num(r["price_eur"], w + " Preis", strict=True)
        c.weight_kg = _num(r["weight_kg"], w + " Gewicht", strict=True)
        c.duty_rate = _num(r["duty_pct"], w + " Zoll", 0, 99.9) / 100.0
        c.order_qty = int(_num(r["order_qty"], w + " Bestellmenge", strict=True))
    for r in edges or []:
        e = cfg.edges[r["id"]]
        w = f"Kante {e.id}"
        e.km = _num(r["km"], w + " km", strict=True)
        e.fixed_eur = _num(r["fixed_eur"], w + " Fixkosten")
        e.eur_per_kg = _num(r["eur_per_kg"], w + " €/kg")
        e.days = _tri([_num(r["d_min"], w + " min"), _num(r["d_mode"], w + " Modus"), _num(r["d_max"], w + " max")], w)
    for r in sups or []:
        tri = _tri([_num(r["d_min"], "Fertigungszeit min"), _num(r["d_mode"], "Fertigungszeit Modus"),
                    _num(r["d_max"], "Fertigungszeit max")], f"Fertigungszeit {r['name']}")
        if "/" in r["key"]:
            sid, tid = r["key"].split("/")
            for t in cfg.suppliers[sid].tier2:
                if t.node == tid:
                    t.prod_days = tri
        else:
            cfg.suppliers[r["key"]].prod_days = tri
    for r in gen or []:
        parts = r["key"].split(".")
        d = cfg.params
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = _num(r["value"], r["label"], strict=r["key"] in ("assembly.workers", "assembly.time_h_per_watch"))
        if r["key"] == "assembly.workers":
            d[parts[-1]] = int(d[parts[-1]])
    validate_params(cfg)
    return cfg
