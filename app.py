"""Oberfläche „Uhren-Leitstand“.  Start:  python -m streamlit run app.py

① Ereignisse auslösen → ② reagieren → ③ Ergebnis: Kennzahlen, animierte Karte, Diagramme.
Unten im Aufklapper: Szenariovergleich, Pareto, Sensitivität, Daten.

Kennzeichen: KI (Referenz) | nachprogrammieren: Merle
"""
import plotly.express as px
import streamlit as st

from scm_lite.auswertung import KENNZAHLEN, massnahmen, rechne, sensitivitaet, vergleich
from scm_lite.daten import lade_stammdaten, lade_szenario, szenario_liste
from scm_lite.karte import karte

st.set_page_config(page_title="Uhren-Leitstand", page_icon="⌚", layout="wide")
S = st.cache_resource(lade_stammdaten)()
SYMBOL = {"s1": "🚢", "s2": "🏭", "s3": "💧", "s4": "🎄", "s5": "⚓", "s6": "🔩"}
KARTEN = {k: lade_szenario(k) for k in szenario_liste() if k[:2] in SYMBOL}


@st.cache_data
def basis():
    return rechne(lade_szenario("s0_basis"), S)["kpi"]


@st.cache_data
def alle_szenarien():
    return vergleich(S)


st.title("⌚ Uhren-Leitstand Heilbronn")
st.caption("Löse Störungen aus und versuche, trotzdem alle Kunden pünktlich zu beliefern.")

# ① + ② Spielfeld
cfg = lade_szenario("s0_basis")
links, rechts = st.columns([3, 2], gap="large")
with links:
    st.subheader("① Was passiert in der Welt?")
    for k in st.pills("Ereignisse", list(KARTEN), selection_mode="multi", label_visibility="collapsed",
                      format_func=lambda k: f"{SYMBOL[k[:2]]} {KARTEN[k]['name']}"):
        cfg["stoerungen"] += KARTEN[k]["stoerungen"]
        st.caption(f"{SYMBOL[k[:2]]} {KARTEN[k]['beschreibung']}")
with rechts:
    st.subheader("② Wie reagierst du?")
    cfg["zweitlieferant"] = st.toggle("🔁 Zweitlieferant einspringen lassen")
    cfg["sicherheitstage"] = st.slider("📦 Sicherheitslager (Tage Vorrat)", 0, 60, cfg["sicherheitstage"], 7)

# ③ Ergebnis – Kennzahlensicht
erg, b = rechne(cfg, S), basis()
kpi, tage = erg["kpi"], erg["tage"]
zu_spaet = int((tage.nachfrage - tage.sofort).sum())
ok = kpi["Lieferfähigkeit [%]"] >= cfg["beta_min"] * 100

st.subheader("③ Ergebnis nach einem Jahr")
for spalte, (name, wert) in zip(st.columns(len(KENNZAHLEN)), kpi.items()):
    diff = wert - b[name]
    gut = abs(diff) < 1e-6 or (diff > 0) == (KENNZAHLEN[name] == "max")
    fmt = "{:,.0f}" if name.startswith("Kapital") else "{:,.2f}"
    spalte.metric(f"{'🟢' if gut else '🔴'} {name}", fmt.format(wert),
                  None if abs(diff) < 1e-6 else fmt.format(diff) + " ggü. Basis",
                  delta_color="normal" if KENNZAHLEN[name] == "max" else "inverse")

was = "  \n".join(f"**{t.bauteil.capitalize()}:** {t.status}" for t in erg["teile"].itertuples() if t.status != "normal")
if ok:
    st.success(f"✅ Geschafft – die Kunden wurden zuverlässig beliefert.  \n{was or 'Alles lief nach Plan.'}")
else:
    st.error(f"⚠️ {zu_spaet} Uhren kamen zu spät (Ziel {cfg['beta_min']:.0%}).  \n{was}  \n"
             "💡 Zweitlieferant einschalten oder Sicherheitslager erhöhen.")

# Netzwerksicht (animiert) + Diagrammsicht
k_sp, d_sp = st.columns([3, 2], gap="large")
with k_sp:
    st.plotly_chart(karte(erg, cfg, S), width="stretch")
    st.caption("▶ drücken: Sendungen fahren Woche für Woche nach Heilbronn. Rot gepunktet = gesperrt.")
with d_sp:
    lager = tage.melt("tag", [c for c in tage if c.startswith("lager_")], "Bauteil", "Stück")
    lager["Bauteil"] = lager.Bauteil.str.removeprefix("lager_")
    fig = px.line(lager, x="tag", y="Stück", color="Bauteil", title="📦 Lager je Bauteil")
    fig.update_layout(height=300, margin=dict(t=40, b=0), legend_title=None)
    st.plotly_chart(fig, width="stretch")
    fig = px.area(tage, x="tag", y="rueckstand", title="⏳ Wartende Kunden", color_discrete_sequence=["#d62728"])
    fig.update_layout(height=250, margin=dict(t=40, b=0), yaxis_title="Uhren")
    st.plotly_chart(fig, width="stretch")

# Auswertung für Bericht und Präsentation
with st.expander("🔍 Auswertung: Szenariovergleich, Maßnahmen (Pareto), Sensitivität, Daten"):
    t1, t2, t3, t4 = st.tabs(["Szenariovergleich", "Maßnahmen (Pareto)", "Sensitivität ±10 %", "Daten"])
    with t1:
        st.dataframe(alle_szenarien().set_index("Szenario").round(2), width="stretch")
    with t2:
        m = massnahmen(cfg, S)
        fig = px.scatter(m, x="Kosten [€/Uhr]", y="Lieferfähigkeit [%]", size="Kapitalbindung [€]",
                         color="Pareto-optimal", symbol="Zweitlieferant", hover_name="Maßnahme",
                         color_discrete_map={True: "#2ca02c", False: "#9e9e9e"})
        fig.add_hline(y=cfg["beta_min"] * 100, line_color="red", annotation_text="Ziel")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(m.round(2), hide_index=True, width="stretch")
    with t3:
        sens = sensitivitaet(cfg, S)
        st.plotly_chart(px.bar(sens, x="Δ Lieferfähigkeit [%-Pkt]", y="Parameter", color="Änderung",
                               barmode="group", orientation="h"), width="stretch")
        st.dataframe(sens.round(2), hide_index=True, width="stretch")
    with t4:
        st.dataframe(erg["teile"].round(2), hide_index=True, width="stretch")
        for name in ("lieferanten", "tier2", "kanten"):
            st.caption(f"data/{name}.csv")
            st.dataframe(S[name], hide_index=True, width="stretch")
