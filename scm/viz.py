"""Darstellung: drei Sichten (animierte Karte, Diagramme, Kennzahlen) aus demselben RunResult."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import Config
from .runner import CRITERIA

PALETTE = {"uhrwerk": "#1f6f8b", "zifferblatt": "#c8553d", "gehaeuse": "#6a4c93", "saphir": "#2a9d8f",
           "perlmutt": "#e09f3e", "armband": "#8c5a2b", "uhr": "#555555"}
LABEL = {"uhrwerk": "Uhrwerk", "zifferblatt": "Zifferblatt+Zeiger", "gehaeuse": "Gehäuse", "saphir": "Saphirglas",
         "perlmutt": "Perlmutt-Platte", "armband": "Lederarmband", "uhr": "Fertige Uhr"}
MODE_COLOR = {"see": "#4a90c2", "bahn": "#444444", "lkw": "#b08a3e", "binnenschiff": "#2e8b57", "luft": "#bdbdbd"}
MODE_LABEL = {"see": "Seeschiff", "bahn": "Güterzug", "lkw": "Lkw", "binnenschiff": "Binnenschiff", "luft": "Luftfracht"}
FONT = dict(family="Inter, Segoe UI, Arial, sans-serif", size=12)


def polyline(cfg: Config, edge):
    a, b = cfg.nodes[edge.src], cfg.nodes[edge.dst]
    pts = [(a.lat, a.lon)] + list(edge.via) + [(b.lat, b.lon)]
    return pts


def _interp(pts, f):
    seg = [math.hypot(pts[i + 1][0] - pts[i][0], (pts[i + 1][1] - pts[i][1]) * math.cos(math.radians(pts[i][0])))
           for i in range(len(pts) - 1)]
    tot = sum(seg) or 1e-9
    target, acc = f * tot, 0.0
    for i, s in enumerate(seg):
        if acc + s >= target or i == len(seg) - 1:
            r = 0 if s == 0 else min(1, (target - acc) / s)
            return (pts[i][0] + r * (pts[i + 1][0] - pts[i][0]), pts[i][1] + r * (pts[i + 1][1] - pts[i][1]))
        acc += s


def _blocked_edges(cfg, intervals, day):
    out = set()
    for kind, obj, a, b in intervals:
        if not (a <= day < b):
            continue
        for e in cfg.edges.values():
            if (kind == "node" and obj in (e.src, e.dst)) or (kind == "mode" and obj == e.mode):
                if e.kind != "outbound":
                    out.add(e.id)
    return out


def _blocked_nodes(intervals, day):
    return {o for k, o, a, b in intervals if k == "node" and a <= day < b}


def network_map(res, step: int = 3, speed_ms: int = 60) -> go.Figure:
    cfg: Config = res.cfg
    legs = res.legs.copy()
    fig = go.Figure()
    # --- statische Kanten je Verkehrsträger
    for mode in ["see", "binnenschiff", "bahn", "lkw", "luft"]:
        lat, lon = [], []
        for e in cfg.edges.values():
            if e.mode == mode:
                for la, lo in polyline(cfg, e):
                    lat.append(la); lon.append(lo)
                lat.append(None); lon.append(None)
        if lat:
            fig.add_trace(go.Scattergeo(lat=lat, lon=lon, mode="lines", name=MODE_LABEL[mode],
                                        line=dict(width=1.2 if mode != "luft" else 0.8, color=MODE_COLOR[mode],
                                                  dash="dot" if mode == "luft" else "solid"),
                                        opacity=0.75, hoverinfo="skip", legendgroup="mode"))
    # --- Knoten (klickbar: Eingriff)
    kinds = {"supplier": ("circle", 9, "#1b4965", "Lieferant (Tier 1/2)"), "port": ("square", 8, "#2e8b57", "Hafen/Terminal"),
             "waypoint": ("diamond", 9, "#4a90c2", "Passage"), "airport": ("triangle-up", 8, "#999999", "Flughafen"),
             "focal": ("star", 16, "#c0392b", "Heilbronn"), "customer": ("circle-open", 8, "#555555", "Kundenregion")}
    for kind, (sym, size, col, nm) in kinds.items():
        ns = [n for n in cfg.nodes.values() if n.kind == kind]
        fig.add_trace(go.Scattergeo(lat=[n.lat for n in ns], lon=[n.lon for n in ns], mode="markers",
                                    marker=dict(symbol=sym, size=size, color=col, line=dict(width=1, color="white")),
                                    text=[n.name for n in ns], customdata=[n.id for n in ns],
                                    hovertemplate="%{text}<br>Klick: Eingriff setzen<extra></extra>", name=nm))
    n_static = len(fig.data)
    # --- dynamische Spuren: Sendungen + gesperrte Kanten + gesperrte Knoten
    fig.add_trace(go.Scattergeo(lat=[], lon=[], mode="lines", line=dict(width=3, color="#d62828", dash="dash"),
                                name="gesperrt", hoverinfo="skip"))
    fig.add_trace(go.Scattergeo(lat=[], lon=[], mode="markers", marker=dict(symbol="x", size=14, color="#d62828",
                                line=dict(width=2)), name="Knoten gesperrt/ausgefallen", hoverinfo="skip"))
    fig.add_trace(go.Scattergeo(lat=[], lon=[], mode="markers", name="Sendungen", showlegend=False))
    i_blk, i_node, i_ship = n_static, n_static + 1, n_static + 2
    days = list(range(0, res.cfg.p("horizon_days"), step))
    frames = []

    def frame_data(d):
        bl, bo = [], []
        for eid in _blocked_edges(cfg, res.intervals, d):
            for la, lo in polyline(cfg, cfg.edges[eid]):
                bl.append(la); bo.append(lo)
            bl.append(None); bo.append(None)
        bn = [cfg.nodes[n] for n in _blocked_nodes(res.intervals, d) if n in cfg.nodes]
        act = legs[(legs.t0 <= d) & (legs.t1 > d)] if len(legs) else legs
        la, lo, sz, co, tx = [], [], [], [], []
        for r in act.itertuples():
            e = cfg.edges[r.edge]
            f = (d - r.t0) / max(1e-9, r.t1 - r.t0)
            p = _interp(polyline(cfg, e), min(1, max(0, f)))
            la.append(p[0]); lo.append(p[1])
            sz.append(7 + 4 * math.log10(max(1, r.qty)))
            co.append(PALETTE.get(r.comp, "#555"))
            tx.append(f"{LABEL.get(r.comp, r.comp)}: {r.qty} Stk · {MODE_LABEL[r.mode]} · {cfg.nodes[r.src].name} → {cfg.nodes[r.dst].name}")
        return (go.Scattergeo(lat=bl, lon=bo), go.Scattergeo(lat=[n.lat for n in bn], lon=[n.lon for n in bn]),
                go.Scattergeo(lat=la, lon=lo, marker=dict(size=sz, color=co, line=dict(width=1, color="white")),
                              text=tx, hovertemplate="%{text}<extra></extra>", mode="markers"))
    for d in days:
        a, b, c = frame_data(d)
        frames.append(go.Frame(data=[a, b, c], traces=[i_blk, i_node, i_ship], name=str(d)))
    a, b, c = frame_data(0)
    fig.data[i_blk].update(lat=a.lat, lon=a.lon)
    fig.data[i_node].update(lat=b.lat, lon=b.lon)
    fig.data[i_ship].update(lat=c.lat, lon=c.lon, marker=c.marker, text=c.text, mode="markers",
                            hovertemplate="%{text}<extra></extra>")
    fig.frames = frames
    # Legende der Komponentenfarben (Dummy-Spuren)
    for k, col in PALETTE.items():
        fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="markers", marker=dict(size=9, color=col),
                                    name=LABEL[k], legendgroup="comp"))
    fig.update_layout(
        font=FONT, height=700, margin=dict(l=0, r=0, t=70, b=90), legend=dict(orientation="h", y=1.0, yanchor="bottom", font=dict(size=11)),
        geo=dict(projection_type="natural earth", showland=True, landcolor="#f2efe9", showocean=True,
                 oceancolor="#e3eef7", showcountries=True, countrycolor="#c9c9c9", coastlinecolor="#9a9a9a",
                 lonaxis=dict(range=[-130, 170]), lataxis=dict(range=[-45, 70])),
        updatemenus=[
            dict(type="buttons", direction="left", x=0.0, y=0.0, yanchor="top", xanchor="left", pad=dict(r=6, t=4),
                 buttons=[dict(label="▶ Abspielen", method="animate",
                               args=[None, dict(frame=dict(duration=speed_ms, redraw=True), fromcurrent=True, transition=dict(duration=0))]),
                          dict(label="❚❚ Pause", method="animate",
                               args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate", transition=dict(duration=0))])]),
            dict(type="buttons", direction="left", x=1.0, y=0.0, yanchor="top", xanchor="right", pad=dict(r=6, t=4),
                 buttons=[dict(label="Welt", method="relayout", args=[{"geo.lonaxis.range": [-130, 170], "geo.lataxis.range": [-45, 70]}]),
                          dict(label="Europa", method="relayout", args=[{"geo.lonaxis.range": [-12, 30], "geo.lataxis.range": [34, 62]}])])],
        sliders=[dict(active=0, x=0.17, len=0.66, y=0.0, yanchor="top", pad=dict(t=0),
                      currentvalue=dict(prefix="Tag ", font=dict(size=13)),
                      steps=[dict(method="animate", label=str(d),
                                  args=[[str(d)], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
                             for d in days])])
    return fig


# ---------------------------------------------------------------- Diagramme (Einzellauf)
def charts(res):
    cfg, d = res.cfg, res.daily
    dm = cfg.p("annual_demand") / 365.0
    f1 = go.Figure()
    for c in cfg.components:
        f1.add_trace(go.Scatter(x=d.day, y=d[f"stock_{c}"] / dm, mode="lines", name=LABEL[c],
                                line=dict(color=PALETTE[c], width=1.8)))
    f1.add_trace(go.Scatter(x=d.day, y=d.fg / dm, mode="lines", name="Fertigwarenlager", line=dict(color="#555", dash="dash")))
    for k, o, a, b in res.intervals:
        f1.add_vrect(x0=a, x1=min(b, cfg.p("horizon_days")), fillcolor="#d62828", opacity=0.08, line_width=0)
    f1.update_layout(title="Bestandsreichweite je Komponente (Tage der Ø-Nachfrage; rot = Störung)", yaxis_title="Reichweite [Tage]",
                     xaxis_title="Tag", font=FONT, height=360, margin=dict(t=50, b=40), legend=dict(orientation="h", y=-0.25))
    # Nachfrage je Woche (Tageswerte sind zu klein/verrauscht): geliefert + Fehlmenge gestapelt, Servicegrad als Linie
    w = d.assign(woche=d.day // 7).groupby("woche").agg(demand=("demand", "sum"), sold=("sold", "sum"), lost=("lost", "sum")).reset_index()
    w["beta"] = (100 * w.sold / w.demand.where(w.demand > 0)).fillna(100)
    f2 = make_subplots(specs=[[{"secondary_y": True}]])
    f2.add_trace(go.Bar(x=w.woche, y=w.sold, name="geliefert", marker_color="#2a9d8f"), secondary_y=False)
    f2.add_trace(go.Bar(x=w.woche, y=w.lost, name="Fehlmenge", marker_color="#d62828"), secondary_y=False)
    f2.add_trace(go.Scatter(x=w.woche, y=w.beta, name="Servicegrad (rot gestrichelt = Ziel)", mode="lines+markers",
                            line=dict(color="#1b2a34", width=1.5), marker=dict(size=4)), secondary_y=True)
    f2.add_hline(y=cfg.p("service_level_target") * 100, line_dash="dash", line_color="#d62828", secondary_y=True, opacity=0.6)
    f2.update_yaxes(title_text="Uhren pro Woche", secondary_y=False, rangemode="tozero")
    f2.update_yaxes(title_text="Servicegrad [%]", secondary_y=True, range=[max(0, float(w.beta.min()) - 5), 101], showgrid=False, tickformat=".0f", nticks=5)
    f2.update_layout(barmode="stack", title="Nachfrage je Woche: geliefert vs. Fehlmenge",
                     xaxis_title="Woche (ab Auswertungsstart)", font=FONT, height=330, margin=dict(t=50, b=40),
                     legend=dict(orientation="h", y=-0.3))
    f3 = go.Figure(go.Scatter(x=d.day, y=d.inventory_value, mode="lines", fill="tozeroy", line=dict(color="#1f6f8b")))
    f3.update_layout(title="Lagerwert (Komponenten + Fertigwaren)", yaxis_title="€", xaxis_title="Tag",
                     font=FONT, height=300, margin=dict(t=50, b=40))
    lead = pd.Series(res.lead_by_comp).dropna()
    f4 = go.Figure(go.Bar(x=[LABEL[c] for c in lead.index], y=lead.values, marker_color=[PALETTE[c] for c in lead.index]))
    f4.update_layout(title="Ø Wiederbeschaffungszeit je Komponente", yaxis_title="Tage",
                     font=FONT, height=300, margin=dict(t=50, b=40))
    b = res.cost_breakdown
    labels = [("einkauf", "Einkauf", "#1f6f8b"), ("fracht", "Fracht", "#e09f3e"), ("zoll", "Zoll", "#c8553d"),
              ("montage", "Montage", "#6a4c93")]
    f5 = go.Figure()
    for k, nm, col in labels:
        f5.add_trace(go.Bar(x=["Landed Cost"], y=[b[k]], name=nm, marker_color=col, text=[f"{b[k]:.1f}"], textposition="inside"))
    f5.update_layout(barmode="stack", title="Aufbau der Landed Cost [€/Uhr]", font=FONT, height=300, margin=dict(t=50, b=40),
                     legend=dict(orientation="h", y=-0.25))
    return [f1, f2, f3, f4, f5]


def kpi_table(res) -> pd.DataFrame:
    k = res.kpis
    rows = [
        ("Landed Cost", f"{k['landed_cost']:.2f}", "€/Uhr"),
        ("Lieferzeit (langsamste Komponente, Ø)", f"{k['lieferzeit']:.1f}", "Tage"),
        ("Servicegrad β", f"{100 * k['servicegrad']:.2f}", "%"),
        ("CO₂e", f"{k['co2']:.4f}", "kg/Uhr"),
        ("Ø Lagerwert", f"{k['lagerwert']:,.0f}".replace(",", "."), "€"),
        ("— Zusatz: Lagerhaltungskosten", f"{k['lagerhaltungskosten']:.2f}", "€/Uhr"),
        ("— Zusatz: längste einzelne Lieferung", f"{k['lieferzeit_max']:.1f}", "Tage"),
        ("— Zusatz: montierte Uhren / Nachfrage / Fehlmenge", f"{k['uhren_montiert']} / {k['nachfrage']} / {k['fehlmenge']}", "Stück"),
    ]
    return pd.DataFrame(rows, columns=["Kriterium", "Wert", "Einheit"])


# ---------------------------------------------------------------- Auswertung (Replikationen, Szenarien)
def scenario_bars(tab: pd.DataFrame, target: float) -> go.Figure:
    fig = make_subplots(rows=1, cols=5, subplot_titles=[f"{c[1].split(' (')[0]} [{c[2]}]" for c in CRITERIA], horizontal_spacing=0.06)
    names = [s.split(" ")[0] if len(s) < 40 else s[:12] for s in tab.szenario]
    cols = ["#2a9d8f", "#c8553d", "#6a4c93", "#e09f3e", "#4a90c2", "#555555"]
    for i, (key, nm, unit, _) in enumerate(CRITERIA, start=1):
        y = tab[key] * (100 if key == "servicegrad" else 1)
        err = tab[key + "_ci"] * (100 if key == "servicegrad" else 1)
        fig.add_trace(go.Bar(x=names, y=y, error_y=dict(type="data", array=err, visible=True),
                             marker_color=cols[: len(tab)], showlegend=False,
                             hovertext=tab.szenario, hovertemplate="%{hovertext}<br>%{y:.3f}<extra></extra>"), row=1, col=i)
        if key == "servicegrad":
            fig.add_hline(y=target * 100, line_dash="dash", line_color="#d62828", row=1, col=i)
            fig.update_yaxes(range=[max(0, float(y.min()) - 8), 101], row=1, col=i)
    fig.update_layout(font=dict(FONT, size=11), height=400, margin=dict(t=110, b=40), title=dict(text="Szenarien im Vergleich (Mittelwert ± 95-%-Konfidenzintervall; rot = β-Ziel)", y=0.97))
    return fig


def scenario_table(tab: pd.DataFrame, target: float) -> pd.DataFrame:
    rows = []
    for r in tab.itertuples():
        rows.append({
            "Szenario": r.szenario, "n": r.n,
            "Landed Cost [€/Uhr]": f"{r.landed_cost:.2f} ± {r.landed_cost_ci:.2f}",
            "Lieferzeit [d]": f"{r.lieferzeit:.1f} ± {r.lieferzeit_ci:.1f}",
            "Servicegrad β [%]": f"{100 * r.servicegrad:.1f} ± {100 * r.servicegrad_ci:.1f}",
            "CO₂e [kg/Uhr]": f"{r.co2:.4f} ± {r.co2_ci:.4f}",
            "Ø Lagerwert [€]": f"{r.lagerwert:,.0f} ± {r.lagerwert_ci:,.0f}".replace(",", "."),
            f"β ≥ {target * 100:.0f} %": "ja" if r.beta_ok else "NEIN"})
    return pd.DataFrame(rows)


def pareto_fig(df: pd.DataFrame, x: str, y: str, target: float) -> go.Figure:
    names = {c[0]: f"{c[1]} [{c[2]}]" for c in CRITERIA}
    fig = go.Figure()
    for flag, nm, col, sym in [(False, "dominiert / β verfehlt", "#b0b0b0", "circle"), (True, "Pareto-Front (β erfüllt)", "#c8553d", "diamond")]:
        s = df[df.pareto == flag]
        fig.add_trace(go.Scatter(x=s[x], y=s[y], mode="markers", name=nm,
                                 marker=dict(color=col, size=11 if flag else 8, symbol=sym, line=dict(width=1, color="white")),
                                 text=[f"SB {r.safety_stock_days} d · Luft {r.air_policy} · Q×{r.order_q_factor}<br>β {100*r.servicegrad:.1f} %"
                                       for r in s.itertuples()], hovertemplate="%{text}<br>x=%{x:.4g}, y=%{y:.4g}<extra></extra>"))
    fig.update_layout(font=FONT, height=480, xaxis_title=names[x], yaxis_title=names[y], margin=dict(t=50),
                      title="Varianten im gewählten Szenario – Pareto-Front unter β-Nebenbedingung")
    return fig
