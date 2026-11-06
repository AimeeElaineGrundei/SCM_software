"""Oberfläche der einfachen Version.  Start:  python -m streamlit run app.py

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
import plotly.express as px
import streamlit as st

from scm_lite.daten import lade_stammdaten, lade_szenario, szenario_liste
from scm_lite.karte import karte
from scm_lite.netz import Netz
from scm_lite.rechnung import berechne, vergleiche_alle

st.set_page_config(page_title="SCM Uhren-Lieferkette", page_icon="⌚", layout="wide")


@st.cache_resource
def stamm():
    return lade_stammdaten()


S = stamm()
LIEF = S["lieferanten"]
keys = szenario_liste()
namen = {k: lade_szenario(k)["name"] for k in keys}

# ------------------------------------------------------------ Seitenleiste
with st.sidebar:
    st.header("Szenario")
    key = st.selectbox("Szenario-Datei", keys, format_func=lambda k: namen[k])
    cfg = lade_szenario(key)
    st.caption(cfg.get("beschreibung", ""))

    with st.expander("Zusätzliche Störungen auslösen"):
        engp = st.multiselect("Engpass sperren", ["suez", "panama", "rhein", "seidenstrasse", "luftraum"])
        haefen = st.multiselect("Hafen sperren", ["RTM", "HAM"])
        aus = st.multiselect("Lieferant fällt aus", list(cfg["lieferanten"].values()))
        dauer = st.slider("Dauer der Störungen [Tage]", 7, 365, 56)

    with st.expander("Stellschrauben"):
        cfg["reaktion"]["zweitlieferant"] = st.toggle("Zweitlieferant bei Ausfall", cfg["reaktion"]["zweitlieferant"])
        cfg["luftfracht_erlaubt"] = st.toggle("Luftfracht als Umleitung erlauben", cfg["luftfracht_erlaubt"])
        cfg["sicherheitstage"] = st.slider("Sicherheitsbestand [Tage]", 0, 60, cfg["sicherheitstage"])
        cfg["nachfrage_faktor"] = st.slider("Nachfrage-Faktor", 0.5, 2.0, float(cfg["nachfrage_faktor"]), 0.1)
        cfg["routing_kriterium"] = st.selectbox("Umleitung optimieren nach", ["zeit", "kosten", "co2e"])

    with st.expander("Lieferanten wählen"):
        for komp in list(cfg["lieferanten"]):
            opts = LIEF[LIEF.komponente == komp]
            if komp == "uhrwerk":
                opts = opts[opts.uhrwerk_typ == cfg["uhrwerk_typ"]]
            ids = list(opts.index)
            cfg["lieferanten"][komp] = st.selectbox(
                komp.capitalize(), ids, index=ids.index(cfg["lieferanten"][komp]),
                format_func=lambda i: f"{LIEF.loc[i, 'name']} ({LIEF.loc[i, 'land']}, {LIEF.loc[i, 'poster']})")

cfg["stoerungen"] = list(cfg["stoerungen"]) \
    + [{"typ": "engpass", "ziel": e, "dauer_tage": dauer} for e in engp] \
    + [{"typ": "knoten", "ziel": h, "dauer_tage": dauer} for h in haefen] \
    + [{"typ": "lieferant", "ziel": l, "dauer_tage": dauer} for l in aus]

# ------------------------------------------------------------ Berechnung
teile, kpi = berechne(cfg, S)
_, kpi_basis = berechne(lade_szenario("s0_basis"), S)
netz = Netz(S)
netz.sperren(cfg["stoerungen"])

st.title("⌚ Uhren-Lieferkette – Montage Heilbronn")
st.caption("Einfache, deterministische Version: keine Zufallseinflüsse, Störungen wirken über ihre Dauer.")

cols = st.columns(len(kpi))
for c, (k, v) in zip(cols, kpi.items()):
    diff = v - kpi_basis[k]
    fmt = "{:,.0f}" if "€]" in k and "Uhr" not in k else "{:,.2f}" if "CO" in k else "{:,.1f}"
    c.metric(k, fmt.format(v), None if abs(diff) < 1e-9 else fmt.format(diff) + " ggü. Basis",
             delta_color="normal" if "Lieferfähigkeit" in k else "inverse")
if kpi["Lieferfähigkeit [%]"] < cfg["beta_min"] * 100:
    st.error(f"Lieferfähigkeit unter Ziel ({cfg['beta_min']:.0%}) – Sicherheitsbestand oder Zweitlieferant prüfen.")

tab1, tab2, tab3 = st.tabs(["🗺️ Karte & Lieferwege", "📊 Szenariovergleich", "📋 Daten"])

with tab1:
    st.plotly_chart(karte(teile, netz, S), width="stretch")
    zeige = teile[["bauteil", "lieferant", "land", "status", "route", "tage", "preis", "fracht", "zoll",
                   "co2e_g", "fehltage"]].rename(columns={
        "bauteil": "Bauteil", "lieferant": "Lieferant", "land": "Land", "status": "Status", "route": "Route",
        "tage": "Lieferzeit [T]", "preis": "Einkauf [€]", "fracht": "Fracht [€]", "zoll": "Zoll [€]",
        "co2e_g": "CO₂e [g]", "fehltage": "Fehltage"})
    st.dataframe(zeige.round(2), hide_index=True, width="stretch")

with tab2:
    vgl = vergleiche_alle(S)
    kz = st.selectbox("Kennzahl", [c for c in vgl.columns if c != "Szenario"])
    st.plotly_chart(px.bar(vgl, x="Szenario", y=kz, text_auto=".1f"), width="stretch")
    st.dataframe(vgl.round(2), hide_index=True, width="stretch")
    st.caption("Vergleich aller Szenario-Dateien mit den Standardwerten aus base.yaml.")

with tab3:
    st.subheader("Lieferanten")
    st.dataframe(LIEF.drop(columns=["standardroute"]), hide_index=True, width="stretch")
    st.subheader("Transportkanten")
    st.dataframe(S["kanten"], hide_index=True, width="stretch")
