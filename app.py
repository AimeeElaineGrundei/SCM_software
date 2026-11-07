"""Oberfläche der einfachen Version.  Start:  python -m streamlit run app.py

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from scm_lite.daten import lade_stammdaten, lade_szenario, szenario_liste
from scm_lite.karte import karte
from scm_lite.netz import Netz
from scm_lite.rechnung import KENNZAHLEN, MODUS_NAME, berechne, vergleiche_alle

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

tab1, tab2, tab3 = st.tabs(["🗺️ Karte & Lieferwege", "📊 Szenariovergleich", "📋 Stammdaten"])

with tab1:
    st.plotly_chart(karte(teile, netz, S), width="stretch")
    zeige = teile[["bauteil", "lieferant", "land", "status", "route", "tage", "preis", "fracht", "zoll",
                   "co2e_g", "fehltage"]].rename(columns={
        "bauteil": "Bauteil", "lieferant": "Lieferant", "land": "Land", "status": "Status", "route": "Route",
        "tage": "Lieferzeit [T]", "preis": "Einkauf [€]", "fracht": "Fracht [€]", "zoll": "Zoll [€]",
        "co2e_g": "CO₂e [g]", "fehltage": "Fehltage"})
    st.dataframe(zeige.round(2), hide_index=True, width="stretch")

with tab2:
    st.subheader("Alle Szenarien auf einen Blick")
    st.caption("Farbe = Vergleich mit S0 Basis: 🟩 besser · 🟥 schlechter · weiß = gleich. "
               "Gerechnet mit den Standardwerten aus base.yaml (ohne die Eingriffe links).")
    vgl = vergleiche_alle(S)
    basis = vgl[vgl.key == "s0_basis"].iloc[0]

    def faerben(spalte):
        if spalte.name not in KENNZAHLEN:
            return [""] * len(spalte)
        besser_hoch = KENNZAHLEN[spalte.name] == "max"
        farben = []
        for v in spalte:
            diff = v - basis[spalte.name]
            if abs(diff) < 1e-6:
                farben.append("")
            elif (diff > 0) == besser_hoch:
                farben.append("background-color: #d9f2d9")
            else:
                farben.append("background-color: #f8d7da")
        return farben

    formate = {"Kosten [€/Uhr]": "{:,.2f}", "Lieferzeit [Tage]": "{:,.1f}", "Kapitalbindung [€]": "{:,.0f}",
               "CO₂e [kg/Uhr]": "{:,.3f}", "Lieferfähigkeit [%]": "{:,.1f}", "Auslastung Montage [%]": "{:,.1f}"}
    tabelle = vgl.drop(columns="key").set_index("Szenario")
    st.dataframe(tabelle.style.apply(faerben).format(formate), width="stretch",
                 column_config={"Was passiert": st.column_config.TextColumn(width="large")})

    st.subheader("Eine Kennzahl im Detail")
    kz = st.radio("Kennzahl", list(KENNZAHLEN), horizontal=True, label_visibility="collapsed")
    d = vgl[["Szenario", kz]].copy()
    diff = d[kz] - basis[kz]
    besser = diff > 0 if KENNZAHLEN[kz] == "max" else diff < 0
    d["Bewertung"] = ["gleich wie Basis" if abs(x) < 1e-6 else "besser" if b else "schlechter"
                      for x, b in zip(diff, besser)]
    d = d.sort_values(kz, ascending=KENNZAHLEN[kz] == "max")
    fig = px.bar(d, x=kz, y="Szenario", orientation="h", color="Bewertung", text_auto=".1f",
                 color_discrete_map={"besser": "#2ca02c", "schlechter": "#d62728", "gleich wie Basis": "#9e9e9e"})
    fig.add_vline(x=basis[kz], line_dash="dash", annotation_text="Basis")
    if kz == "Lieferfähigkeit [%]":
        fig.add_vline(x=cfg["beta_min"] * 100, line_color="red", annotation_text="Ziel")
    fig.update_layout(height=380, yaxis_title=None, legend_title=None)
    st.plotly_chart(fig, width="stretch")

with tab3:
    st.caption("Stammdaten aus dem Ordner data/. Änderungen bitte in den CSV-Dateien vornehmen.")
    d_lief, d_wege, d_orte, d_cfg = st.tabs(["Lieferanten", "Transportwege", "Standorte", "Konfiguration"])

    with d_lief:
        bt = st.selectbox("Bauteil", ["alle"] + sorted(LIEF.komponente.unique()))
        l = LIEF if bt == "alle" else LIEF[LIEF.komponente == bt]
        aktiv = set(cfg["lieferanten"].values())
        st.dataframe(pd.DataFrame({
            "aktiv": ["✅" if i in aktiv else "" for i in l.index],
            "Bauteil": l.komponente, "Lieferant": l["name"], "Land": l.land, "Ort": l.ort,
            "Poster": l.poster, "Preis [€]": l.preis_eur, "Vorlauf [T]": l.vorlaufzeit_tage,
            "Gewicht [g]": l.gewicht_brutto_g, "Zoll [%]": l.zollsatz * 100,
            "Datenstand": l.preis_status, "Bemerkung": l.bemerkung.fillna(""),
        }), hide_index=True, width="stretch")
        st.caption("Datenstand: Poster = vom Poster · abgeleitet = umgerechnet · Annahme = geschätzt")

    with d_wege:
        K, KN = S["kanten"], S["knoten"]
        c1, c2 = st.columns(2)
        modi = c1.multiselect("Verkehrsträger", sorted(K.modus.unique()), format_func=lambda m: MODUS_NAME.get(m, m))
        nur_haupt = c2.toggle("Nur Hauptstrecken (ohne Vorlauf Lieferant → Hafen)", value=True)
        k = K[K.modus.isin(modi)] if modi else K
        if nur_haupt:
            k = k[~k.von.isin(LIEF.index)]
        st.dataframe(pd.DataFrame({
            "Von": KN.loc[k.von, "name"].values, "Nach": KN.loc[k.nach, "name"].values,
            "Verkehrsträger": k.modus.map(lambda m: MODUS_NAME.get(m, m)).values,
            "Route": k.route.replace("", "Standard").values, "km": k.distanz_km.values,
            "Tage (min/typ/max)": [f"{a:g} / {b:g} / {c:g}" for a, b, c in zip(k.tage_min, k.tage_modus, k.tage_max)],
            "€/kg": k.kosten_eur_pro_kg.values, "g CO₂e/tkm": k.co2e_g_pro_tkm.values,
            "Engpass": k.engpaesse.replace("", "–").values,
        }), hide_index=True, width="stretch")

    with d_orte:
        st.dataframe(S["knoten"][["name", "typ", "land", "lat", "lon"]].rename(columns={
            "name": "Name", "typ": "Typ", "land": "Land"}), width="stretch")

    with d_cfg:
        st.write("Aktuelle Einstellungen (Szenario-Datei + Eingriffe links):")
        st.json({k: v for k, v in cfg.items() if k not in ("key",)}, expanded=False)
