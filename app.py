"""Dash-Oberfläche: Simulation steuern (Szenario, Parameter, Klick-Eingriffe auf der Karte) und
Ergebnisse in drei konsistenten Sichten zeigen (animierte Karte, Diagramme, Kennzahlen).

Start:  python app.py   ->  http://127.0.0.1:8050
"""
from __future__ import annotations
import dash
from dash import Dash, dcc, html, dash_table, Input, Output, State, ctx, no_update, Patch
import io
import pandas as pd

from scm.config import (load_base, list_scenarios, apply_scenario, check_requirements, ConfigError, MODES,
                        master_tables, apply_master_data)
from scm.runner import run_once, compare_scenarios, grid_search, CRITERIA
from scm import viz

BASE = load_base()
SCEN = list_scenarios()
SCEN_OPTS = [{"label": v["name"], "value": k} for k, v in SCEN.items()]
EV_TYPES = [("block_node", "Knoten sperren (Hafen, Passage, Flughafen)"), ("supplier_outage", "Lieferant fällt aus"),
            ("block_mode", "Verkehrsträger sperren"), ("demand_factor", "Nachfrage × Faktor"),
            ("transit_factor", "Transportzeit × Faktor (Verspätung)")]
EV_LABEL = dict(EV_TYPES)
MODE_OPTS = [{"label": viz.MODE_LABEL[m], "value": m} for m in ["see", "bahn", "lkw", "binnenschiff", "luft"]]
TARGET = BASE.p("service_level_target")

app = Dash(__name__, title="SCM-Simulation Heilbronn")
server = app.server

CSS = """
body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:#f6f4ef;color:#222}
.hdr{background:#1b2a34;color:#fff;padding:14px 22px}.hdr h1{margin:0;font-size:20px}.hdr p{margin:2px 0 0;font-size:12px;opacity:.75}
.wrap{display:grid;grid-template-columns:340px 1fr;gap:16px;padding:16px;align-items:start}
.panel{background:#fff;border:1px solid #e1ddd2;border-radius:8px;padding:14px}
.panel h3{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:#6b6252}
label{font-size:12px;color:#555;display:block;margin:10px 0 3px}
.btn{width:100%;margin-top:8px;padding:9px;border:0;border-radius:6px;font-weight:600;cursor:pointer;color:#fff;background:#1f6f8b}
.btn.sec{background:#6b6252}.btn.add{background:#2a9d8f}
.note{font-size:11px;color:#777;margin-top:6px;line-height:1.4}
.kpi{display:inline-block;margin:0 10px 10px 0;padding:10px 14px;background:#fff;border:1px solid #e1ddd2;border-radius:8px;min-width:150px}
.kpi b{display:block;font-size:20px}.kpi span{font-size:11px;color:#777}
.bad{color:#d62828}.good{color:#2a9d8f}
@media(max-width:1000px){.wrap{grid-template-columns:1fr}}
"""
app.index_string = app.index_string.replace("</head>", f"<style>{CSS}</style></head>")


def slider(id_, lo, hi, step, val, marks=None):
    return dcc.Slider(id=id_, min=lo, max=hi, step=step, value=val, marks=marks,
                      tooltip={"placement": "bottom", "always_visible": True})


# ----------------------------------------------------------------------------- Stammdaten-Register
EDIT_BG = [{"if": {"column_editable": True}, "backgroundColor": "#fff8e1"}]
TBL_STYLE = dict(style_cell={"fontSize": 12, "padding": "5px", "textAlign": "left", "whiteSpace": "normal", "height": "auto"},
                 style_header={"fontWeight": "700", "backgroundColor": "#efe9dc"}, style_data_conditional=EDIT_BG)
M0 = master_tables(BASE)


def _cols(spec):
    return [dict(name=n, id=i, editable=e, type="numeric" if e else "text") for i, n, e in spec]


def master_layout():
    return html.Div([
        html.Div([html.B("Stammdaten manuell ändern. "), "Gelbe Zellen sind editierbar (Preis, Zoll, Frachtkosten, Transport- und Fertigungszeiten, Parameter). "
                  "Die Änderungen gelten sofort für alle Läufe (Einzellauf, Auswertung, Rastersuche) – die Datei config/base.yaml bleibt unverändert; "
                  "zum dauerhaften Speichern den Wert in der YAML-Datei ändern."], className="note", style={"fontSize": "13px"}),
        html.Div(id="master-status", style={"margin": "8px 0", "fontSize": "13px"}),
        html.Button("Alle Stammdaten auf config/base.yaml zurücksetzen", id="master-reset", className="btn sec", style={"width": "auto", "padding": "7px 14px"}),
        html.H3("Komponenten (Einkaufspreis, Gewicht, Zollsatz, Bestellmenge)", style={"marginTop": "16px"}),
        dash_table.DataTable(id="m-comp", data=M0["comps"], editable=True, **TBL_STYLE, columns=_cols([
            ("id", "ID", False), ("name", "Komponente", False), ("lieferant", "Lieferant", False), ("price_eur", "Preis [€/Stk]", True),
            ("weight_kg", "Gewicht [kg/Stk]", True), ("duty_pct", "Zoll [% vom Warenwert + Fracht]", True), ("order_qty", "Bestellmenge Q [Stk]", True)])),
        html.H3("Transportkanten (Kosten und Zeiten je Strecke)", style={"marginTop": "16px"}),
        dash_table.DataTable(id="m-edge", data=M0["edges"], editable=True, page_size=12, filter_action="native", sort_action="native", **TBL_STYLE,
                             columns=_cols([("id", "ID", False), ("strecke", "Strecke", False), ("mode", "Verkehrsträger", False), ("km", "km", True),
                                            ("fixed_eur", "Fixkosten je Sendung [€]", True), ("eur_per_kg", "Fracht [€/kg]", True),
                                            ("d_min", "Dauer min [d]", True), ("d_mode", "Dauer Modus [d]", True), ("d_max", "Dauer max [d]", True)])),
        html.H3("Lieferanten (Fertigungszeit je Auftrag)", style={"marginTop": "16px"}),
        dash_table.DataTable(id="m-sup", data=M0["sups"], editable=True, **TBL_STYLE,
                             columns=_cols([("key", "Schlüssel", False), ("name", "Lieferant", False), ("stufe", "Stufe", False),
                                            ("d_min", "Fertigung min [d]", True), ("d_mode", "Modus [d]", True), ("d_max", "max [d]", True)])),
        html.H3("Allgemeine Parameter", style={"marginTop": "16px"}),
        dash_table.DataTable(id="m-gen", data=M0["gen"], editable=True, **TBL_STYLE,
                             columns=[dict(name="Schlüssel", id="key", editable=False), dict(name="Parameter", id="label", editable=False),
                                      dict(name="Wert", id="value", editable=True, type="numeric"), dict(name="Einheit", id="unit", editable=False)]),
    ], style={"padding": "12px"})


MASTER_STATES = [State("m-comp", "data"), State("m-edge", "data"), State("m-sup", "data"), State("m-gen", "data")]


def get_base(comps, edges, sups, gen):
    """BASE mit den im Register geänderten Stammdaten (wirft ConfigError bei ungültigen Werten)."""
    return apply_master_data(BASE, comps, edges, sups, gen)


@app.callback(Output("master-status", "children"), Input("m-comp", "data"), Input("m-edge", "data"), Input("m-sup", "data"), Input("m-gen", "data"))
def _master_status(comps, edges, sups, gen):
    try:
        b = get_base(comps, edges, sups, gen)
    except (ConfigError, ValueError, KeyError, TypeError) as e:
        return html.Span(f"✘ Ungültiger Wert: {e}", className="bad")
    from scm.engine import reference_landed_cost
    return html.Span(f"✔ Stammdaten gültig · Handrechnung Landed Cost (ohne Simulation): {reference_landed_cost(b):.2f} €/Uhr", className="good")


@app.callback(Output("m-comp", "data"), Output("m-edge", "data"), Output("m-sup", "data"), Output("m-gen", "data"),
              Input("master-reset", "n_clicks"), prevent_initial_call=True)
def _master_reset(_):
    m = master_tables(BASE)
    return m["comps"], m["edges"], m["sups"], m["gen"]


@app.callback(Output("map", "figure", allow_duplicate=True), Input("speed", "value"), prevent_initial_call=True)
def _speed(ms):
    p = Patch()
    p["layout"]["updatemenus"][0]["buttons"][0]["args"][1]["frame"]["duration"] = int(ms)
    return p



sidebar = html.Div([
    html.Div([
        html.H3("1 · Szenario & Parameter"),
        html.Label("Szenario (Basis + Stressszenarien, gleiches Modell)"),
        dcc.Dropdown(id="scen", options=SCEN_OPTS, value="S0_basis", clearable=False),
        html.Label("Sicherheitsbestand [Tage Nachfrage]"),
        dcc.Input(id="sb", type="number", min=0, max=90, step=1, value=BASE.p("safety_stock_days"), style={"width": "100%"}),
        html.Label("Bestellmenge Q (Faktor auf Basis-Q)"),
        dcc.Input(id="qf", type="number", min=0.25, max=4, step=0.25, value=1.0, style={"width": "100%"}),
        html.Label("Jahresnachfrage [Uhren]"),
        dcc.Input(id="demand", type="number", min=1000, max=100000, step=500, value=BASE.p("annual_demand"), style={"width": "100%"}),
        html.Label("Luftfracht-Politik"),
        dcc.Dropdown(id="air", clearable=False, value=BASE.p("air_policy"),
                     options=[{"label": "aus", "value": "off"}, {"label": "nur bei Störung (Umleitung)", "value": "on_disruption"},
                              {"label": "immer", "value": "always"}]),
        html.Label("Umleitung nach"),
        dcc.Dropdown(id="rw", clearable=False, value=BASE.p("route_weight"),
                     options=[{"label": "Zeit", "value": "time"}, {"label": "Kosten", "value": "cost"}, {"label": "CO₂e", "value": "co2"}]),
        html.Label("Zufall"),
        dcc.RadioItems(id="stoch", value=1, options=[{"label": " stochastisch", "value": 1}, {"label": " deterministisch (Handrechnung)", "value": 0}]),
        html.Div([html.Div([html.Label("Seed"), dcc.Input(id="seed", type="number", value=BASE.p("seed"), style={"width": "100%"})]),
                  html.Div([html.Label("Replikationen (Auswertung)"), dcc.Input(id="reps", type="number", min=1, max=100, value=10, style={"width": "100%"})])],
                 style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px"}),
    ], className="panel"),
    html.Div([
        html.H3("2 · Eingriffe (auch per Karten-Klick)"),
        html.Label("Art"),
        dcc.Dropdown(id="ev-type", options=[{"label": l, "value": k} for k, l in EV_TYPES], value="block_node", clearable=False),
        html.Label("Objekt"),
        dcc.Dropdown(id="ev-target", clearable=False),
        html.Div([html.Div([html.Label("Start (Tag)"), dcc.Input(id="ev-start", type="number", value=60, min=0, max=364, style={"width": "100%"})]),
                  html.Div([html.Label("Dauer [Tage]"), dcc.Input(id="ev-dur", type="number", value=90, min=1, max=365, style={"width": "100%"})]),
                  html.Div([html.Label("Faktor"), dcc.Input(id="ev-fac", type="number", value=1.3, min=0, step=0.1, style={"width": "100%"})])],
                 style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "8px"}),
        html.Button("Eingriff hinzufügen", id="ev-add", className="btn add"),
        html.Div("Tipp: Auf der Karte einen Knoten anklicken – Häfen/Passagen werden gesperrt, Lieferanten fallen aus (mit Start/Dauer von oben).", className="note"),
        dash_table.DataTable(id="ev-table", columns=[{"name": "Art", "id": "label"}, {"name": "Objekt", "id": "target"},
                                                     {"name": "Start", "id": "start"}, {"name": "Ende", "id": "end"},
                                                     {"name": "Faktor", "id": "factor"}],
                             data=[], row_deletable=True, style_cell={"fontSize": 11, "padding": "4px", "textAlign": "left"},
                             style_table={"marginTop": "8px"}),
    ], className="panel", style={"marginTop": "12px"}),
    html.Div([
        html.H3("3 · Läufe"),
        html.Button("▶ Einzellauf (Animation)", id="run1", className="btn"),
        html.Button("Σ Auswertung: alle Szenarien × Replikationen", id="run2", className="btn sec"),
        html.Button("◆ Rastersuche & Pareto im gewählten Szenario", id="run3", className="btn sec"),
        html.Div("Pareto: erst ein Stressszenario (z. B. S1 Suez) wählen, dann starten – dort entstehen die Zielkonflikte (Lagerwert ↔ Servicegrad, Luftfracht ↔ CO₂e). Einzellauf = 1 Replikation (Seed s, Nr. 0). Auswertung = n Replikationen je Szenario mit gleichen Zufallszahlen (Common Random Numbers).", className="note"),
    ], className="panel", style={"marginTop": "12px"}),
])

main = html.Div([
    html.Div(id="kpi-cards"),
    dcc.Tabs(id="tabs", value="map", children=[
        dcc.Tab(label="Karte (animiert)", value="map", children=[
            html.Div([html.Span("Animationsgeschwindigkeit: ", style={"fontSize": "12px", "color": "#555"}),
                      dcc.RadioItems(id="speed", value=60, inline=True, inputStyle={"marginLeft": "12px"},
                                     options=[{"label": " sehr langsam", "value": 250}, {"label": " langsam", "value": 120},
                                              {"label": " normal", "value": 60}, {"label": " schnell", "value": 25},
                                              {"label": " sehr schnell", "value": 8}],
                                     style={"display": "inline-block", "fontSize": "12px"})], style={"padding": "8px 12px 0"}),
            dcc.Loading(dcc.Graph(id="map", config={"scrollZoom": True}))]),
        dcc.Tab(label="Diagramme", value="charts", children=[dcc.Loading(html.Div(id="charts-box"))]),
        dcc.Tab(label="Kennzahlen", value="kpi", children=[html.Div([
            html.H3("Einzellauf"), html.Div(id="kpi-single"),
            html.H3("Szenariovergleich (Auswertung)"), dcc.Loading(html.Div(id="kpi-eval")),
            dcc.Graph(id="eval-fig", style={"display": "none"})], style={"padding": "12px"})]),
        dcc.Tab(label="Pareto / Rastersuche", value="pareto", children=[html.Div([
            html.Div([html.Div([html.Label("x-Achse"), dcc.Dropdown(id="px", options=[{"label": c[1], "value": c[0]} for c in CRITERIA], value="lagerwert", clearable=False)]),
                      html.Div([html.Label("y-Achse"), dcc.Dropdown(id="py", options=[{"label": c[1], "value": c[0]} for c in CRITERIA], value="servicegrad", clearable=False)])],
                     style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px"}),
            dcc.Loading(dcc.Graph(id="pareto-fig")), html.Div(id="pareto-table"),
            dcc.Store(id="grid-store")], style={"padding": "12px"})]),
        dcc.Tab(label="Stammdaten (editierbar)", value="master", children=[master_layout()]),
        dcc.Tab(label="Prüfung & Annahmen", value="check", children=[html.Div(id="check-box", style={"padding": "12px"})]),
    ]),
])

app.layout = html.Div([
    html.Div([html.H1("Supply-Chain-Simulation · Premium-Armbanduhr Heilbronn"),
              html.P("Ereignisdiskrete Simulation (SimPy) · 6 Tier-1, Tier-2, Transportketten See/Bahn/Lkw/Binnenschiff · Zeit in Tagen, Geld in €, Masse in kg")], className="hdr"),
    html.Div([html.Div(sidebar), main], className="wrap"),
])


# ----------------------------------------------------------------------------- Hilfsfunktionen
def target_options(ev_type):
    if ev_type == "block_node":
        return [{"label": n.name, "value": n.id} for n in BASE.nodes.values() if n.kind in ("port", "waypoint", "airport")], "n_suez"
    if ev_type == "supplier_outage":
        return [{"label": n.name, "value": n.id} for n in BASE.nodes.values() if n.kind == "supplier"], "sup_uhrwerk"
    if ev_type in ("block_mode", "transit_factor"):
        opts = MODE_OPTS if ev_type == "block_mode" else [{"label": "alle Verkehrsträger", "value": "*"}] + MODE_OPTS
        return opts, ("binnenschiff" if ev_type == "block_mode" else "see")
    return [{"label": "–", "value": "-"}], "-"


@app.callback(Output("ev-target", "options"), Output("ev-target", "value"), Input("ev-type", "value"))
def _targets(t):
    return target_options(t)


def row_to_event(r):
    t = r["type"]
    ev = dict(type=t, start=float(r["start"]), end=float(r["end"]))
    if t == "block_node":
        ev["node"] = r["target"]
    elif t == "supplier_outage":
        ev["supplier"] = r["target"]
    elif t == "block_mode":
        ev["mode"] = r["target"]
    elif t == "transit_factor":
        ev["factor"] = float(r["factor"])
        ev["mode"] = None if r["target"] == "*" else r["target"]
    elif t == "demand_factor":
        ev["factor"] = float(r["factor"])
    return ev


@app.callback(Output("ev-table", "data"),
              Input("ev-add", "n_clicks"), Input("map", "clickData"),
              State("ev-type", "value"), State("ev-target", "value"), State("ev-start", "value"),
              State("ev-dur", "value"), State("ev-fac", "value"), State("ev-table", "data"),
              prevent_initial_call=True)
def _add_event(n, click, typ, target, start, dur, fac, data):
    data = list(data or [])
    start, dur = float(start or 0), float(dur or 30)
    if ctx.triggered_id == "map" and click:
        pt = click["points"][0]
        nid = pt.get("customdata")
        if not nid or nid not in BASE.nodes or BASE.nodes[nid].kind in ("customer", "focal"):
            return no_update
        typ = "supplier_outage" if BASE.nodes[nid].kind == "supplier" else "block_node"
        target = nid
    data.append(dict(type=typ, label=EV_LABEL[typ].split(" (")[0], target=target if typ not in ("demand_factor",) else "–",
                     start=start, end=start + dur, factor=fac if typ in ("demand_factor", "transit_factor") else ""))
    return data


def make_cfg(scen_key, sb, qf, demand, air, rw, stoch, table, seed, base=None):
    base = base or BASE
    sc = dict(SCEN[scen_key])
    sc["events"] = list(sc.get("events", [])) + [row_to_event(r) for r in (table or [])]
    return apply_scenario(base, sc, param_overrides=dict(
        safety_stock_days=float(sb), order_q_factor=float(qf), annual_demand=float(demand or base.p("annual_demand")),
        air_policy=air, route_weight=rw, stochastic=bool(stoch), seed=int(seed or 0)))


def cards(kpis):
    ok = kpis["servicegrad"] >= TARGET
    items = [("Landed Cost", f"{kpis['landed_cost']:.2f} €/Uhr", ""), ("Lieferzeit", f"{kpis['lieferzeit']:.1f} Tage", ""),
             ("Servicegrad β", f"{100 * kpis['servicegrad']:.1f} %", "good" if ok else "bad"),
             ("CO₂e", f"{kpis['co2']:.4f} kg/Uhr", ""), ("Ø Lagerwert", f"{kpis['lagerwert']:,.0f} €".replace(",", "."), "")]
    return [html.Div([html.Span(n), html.B(v, className=c)], className="kpi") for n, v, c in items]


def df_table(df, id_=None):
    return dash_table.DataTable(data=df.to_dict("records"), columns=[{"name": c, "id": c} for c in df.columns], id=id_ or {},
                                style_cell={"fontSize": 12, "padding": "6px", "textAlign": "left", "whiteSpace": "normal", "height": "auto"},
                                style_header={"fontWeight": "700", "backgroundColor": "#efe9dc"},
                                style_data_conditional=[{"if": {"filter_query": '{β ≥ 97 %} = "NEIN"'}, "color": "#d62828"}])


# ----------------------------------------------------------------------------- Einzellauf
@app.callback(Output("map", "figure"), Output("charts-box", "children"), Output("kpi-single", "children"), Output("kpi-cards", "children"),
              Input("run1", "n_clicks"),
              State("scen", "value"), State("sb", "value"), State("qf", "value"), State("demand", "value"), State("air", "value"),
              State("rw", "value"), State("stoch", "value"), State("ev-table", "data"), State("seed", "value"), State("speed", "value"),
              *MASTER_STATES)
def _run_single(_, scen, sb, qf, demand, air, rw, stoch, table, seed, speed, mc, me, ms, mg):
    try:
        cfg = make_cfg(scen, sb, qf, demand, air, rw, stoch, table, seed, get_base(mc, me, ms, mg))
    except (ConfigError, ValueError, KeyError, TypeError) as e:
        return no_update, html.Div(f"Konfigurationsfehler: {e}", className="bad"), no_update, no_update
    res = run_once(cfg, cfg.p("seed"), 0)
    figs = viz.charts(res)
    box = html.Div([html.Div(dcc.Graph(figure=figs[0]), style={"gridColumn": "1 / span 2"}),
                    dcc.Graph(figure=figs[1]), dcc.Graph(figure=figs[2]), dcc.Graph(figure=figs[3]), dcc.Graph(figure=figs[4])],
                   style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px"})
    return viz.network_map(res, speed_ms=int(speed or 60)), box, df_table(viz.kpi_table(res)), cards(res.kpis)


# ----------------------------------------------------------------------------- Auswertung
@app.callback(Output("kpi-eval", "children"), Output("eval-fig", "figure"), Output("eval-fig", "style"),
              Input("run2", "n_clicks"),
              State("scen", "value"), State("sb", "value"), State("qf", "value"), State("demand", "value"), State("air", "value"),
              State("rw", "value"), State("stoch", "value"), State("ev-table", "data"), State("seed", "value"), State("reps", "value"),
              *MASTER_STATES, prevent_initial_call=True)
def _run_eval(_, scen, sb, qf, demand, air, rw, stoch, table, seed, reps, mc, me, ms, mg):
    scenarios = dict(SCEN)
    if table:
        sc = dict(SCEN[scen])
        sc["name"] = f"Eigener Lauf ({SCEN[scen]['name']} + Eingriffe)"
        sc["events"] = list(sc.get("events", [])) + [row_to_event(r) for r in table]
        scenarios["_custom"] = sc
    try:
        base = apply_scenario(get_base(mc, me, ms, mg), None, param_overrides=dict(stochastic=bool(stoch), seed=int(seed or 0)))
        tab, _ = compare_scenarios(base, int(reps or 10), int(seed or 0), scenarios,
                                   param_overrides=dict(safety_stock_days=float(sb), order_q_factor=float(qf),
                                                        annual_demand=float(demand), air_policy=air, route_weight=rw))
    except (ConfigError, ValueError, KeyError, TypeError) as e:
        return html.Div(f"Fehler: {e}", className="bad"), no_update, no_update
    return df_table(viz.scenario_table(tab, TARGET)), viz.scenario_bars(tab, TARGET), {"display": "block"}


# ----------------------------------------------------------------------------- Pareto
@app.callback(Output("grid-store", "data"), Output("pareto-table", "children"),
              Input("run3", "n_clicks"), State("scen", "value"), State("reps", "value"), State("seed", "value"),
              State("demand", "value"), State("rw", "value"), *MASTER_STATES, prevent_initial_call=True)
def _run_grid(_, scen, reps, seed, demand, rw, mc, me, ms, mg):
    base = apply_scenario(get_base(mc, me, ms, mg), None, param_overrides=dict(annual_demand=float(demand), route_weight=rw, seed=int(seed or 0)))
    g = grid_search(base, SCEN[scen], reps=min(int(reps or 5), 8), seed=int(seed or 0))
    show = g[g.pareto].copy()
    show["servicegrad"] = (100 * show.servicegrad).round(1)
    show = show.rename(columns=dict(safety_stock_days="SB [d]", air_policy="Luft", order_q_factor="Q-Faktor", landed_cost="Landed Cost [€]",
                                    lieferzeit="Lieferzeit [d]", servicegrad="β [%]", co2="CO₂e [kg]", lagerwert="Lagerwert [€]"))
    show = show[["SB [d]", "Luft", "Q-Faktor", "Landed Cost [€]", "Lieferzeit [d]", "β [%]", "CO₂e [kg]", "Lagerwert [€]"]].round(3)
    show["Lagerwert [€]"] = show["Lagerwert [€]"].round(0).astype(int)
    return g.to_json(orient="split"), html.Div([html.H3("Pareto-optimale Varianten (β erfüllt)"), df_table(show)])


@app.callback(Output("pareto-fig", "figure"), Input("grid-store", "data"), Input("px", "value"), Input("py", "value"))
def _pareto(js, x, y):
    if not js:
        return viz.go.Figure().update_layout(title="Noch keine Rastersuche – links „Rastersuche & Pareto“ starten", height=300)
    return viz.pareto_fig(pd.read_json(io.StringIO(js), orient="split"), x, y, TARGET)


# ----------------------------------------------------------------------------- Prüfung & Annahmen
@app.callback(Output("check-box", "children"), Input("tabs", "value"))
def _check(_):
    items = [html.Li(("✔ " if ok else "✘ ") + t, className="good" if ok else "bad") for ok, t in check_requirements(BASE, len(SCEN), len(CRITERIA))]
    comp = pd.DataFrame([dict(Komponente=c.name, Lieferant=BASE.nodes[c.supplier].name, Land=BASE.suppliers[c.supplier].country,
                              **{"Preis [€]": c.price_eur, "Gewicht [kg]": c.weight_kg, "Zoll [%]": 100 * c.duty_rate, "Q [Stk]": c.order_qty})
                         for c in BASE.components.values()])
    return html.Div([html.H3("Mindestanforderungen der Aufgabenstellung (automatisch geprüft)"), html.Ul(items),
                     html.H3("Stammdaten (config/base.yaml, Quellen siehe ANNAHMEN.md)"), df_table(comp),
                     html.Div("Werte teils quellengestützt (Q), teils begründete Annahmen (A) – Herleitung und Quellen in ANNAHMEN.md.", className="note")])


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
