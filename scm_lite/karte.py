"""Animierte Netzwerkkarte (Plotly): Routen, Tier-2, Distribution, Sendungen je Woche.

Kennzeichen: KI (Referenz) | nachprogrammieren: Merle
"""
import numpy as np
import plotly.graph_objects as go

FARBEN = {"see": "#1f77b4", "bahn": "#2ca02c", "bahn_cn": "#17becf", "lkw": "#ff7f0e",
          "binnen": "#9467bd", "luft": "#d62728"}
NAMEN = {"see": "Seeschiff", "bahn": "Bahn", "bahn_cn": "Bahn Seidenstraße", "lkw": "Lkw",
         "binnen": "Binnenschiff", "luft": "Luftfracht"}

# schematische Wegpunkte (lat, lon) für Seewege
SINGAPUR, SUNDA, SRI_LANKA = (1.3, 103.8), (-7.5, 105.0), (5.8, 80.6)
BAB, SUEZ, GIBRALTAR, FINISTERRE, KANAL = (12.6, 43.4), (29.9, 32.6), (35.9, -5.7), (43.8, -9.8), (49.8, -3.5)
KAP, DAKAR, PANAMA, KARIBIK, NATAL = (-35.0, 20.0), (14.5, -18.5), (8.9, -79.5), (18.5, -68.0), (-5.5, -34.0)


def _wegpunkte(lat, lon, tags, kap):
    w = []
    if "suez" in tags or kap:
        if lon > 95:
            w.append(SINGAPUR if lat > -10 else SUNDA)
        if lon > 75:
            w.append(SRI_LANKA)
        w += [KAP, DAKAR] if kap else [BAB, SUEZ, GIBRALTAR]
        w.append(FINISTERRE)
    elif "panama" in tags:
        w += [(15.0, -100.0), PANAMA, KARIBIK]
    elif lat < -15 and 15 < lon < 35:      # Südafrika
        w += [(-34.5, 18.0), DAKAR, FINISTERRE]
    elif lat < 0 and lon < -30:            # Brasilien
        w += [NATAL, DAKAR, FINISTERRE]
    elif lat < 40 and 0 < lon < 15:        # Tunesien → Genua
        w.append((38.5, 9.5))
    return w


def linie(stamm, kante: dict) -> tuple[list, list]:
    kn = stamm["knoten"]
    a, b = kn.loc[kante["von"]], kn.loc[kante["nach"]]
    pts = [(a.lat, a.lon)]
    if kante["modus"] == "see":
        pts += _wegpunkte(a.lat, a.lon, kante["tags"], kante["route"] == "kap")
        if kante["nach"] in ("RTM", "HAM"):
            pts.append(KANAL)
    pts.append((b.lat, b.lon))
    return [p[0] for p in pts], [p[1] for p in pts]


def _punkt(lat, lon, f):
    """Position bei Anteil f (0–1) entlang einer Linie aus mehreren Punkten."""
    p = np.column_stack([lat, lon])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    ziel, cum = f * seg.sum(), np.concatenate([[0], np.cumsum(seg)])
    i = min(np.searchsorted(cum, ziel, side="right") - 1, len(seg) - 1)
    t = (ziel - cum[i]) / seg[i] if seg[i] else 0
    return p[i] + t * (p[i + 1] - p[i])


def _linien(fig, name, farbe, stuecke, dash=None, breite=2.5):
    la, lo = [], []
    for a, b in stuecke:
        la += list(a) + [None]
        lo += list(b) + [None]
    if la:
        fig.add_trace(go.Scattergeo(lat=la, lon=lo, mode="lines", name=name, hoverinfo="skip",
                                    line=dict(width=breite, color=farbe, dash=dash)))


def karte(ergebnis: dict, cfg: dict, stamm: dict, schritt: int = 7) -> go.Figure:
    from .netz import Netz
    netz, kn, t2 = Netz(stamm), stamm["knoten"], stamm["tier2"]
    send = ergebnis["sendungen"]
    genutzt = {k for et in send.etappen for k, _, _ in et}
    fig = go.Figure()

    for m in sorted({netz.kanten[k]["modus"] for k in genutzt}):          # genutzte Routen
        _linien(fig, NAMEN.get(m, m), FARBEN.get(m, "grey"),
                [linie(stamm, netz.kanten[k]) for k in genutzt if netz.kanten[k]["modus"] == m])
    aktive_lief = set(send.lieferant)                                     # Tier-2 → Tier-1
    _linien(fig, "Tier-2 → Tier-1", "#8c564b", [
        ((r.lat, kn.loc[r.liefert_an, "lat"]), (r.lon, kn.loc[r.liefert_an, "lon"]))
        for r in t2[t2.liefert_an.isin(aktive_lief)].itertuples()], dash="dash", breite=1.5)
    _linien(fig, "Distribution → Kunde", "black",                          # Distribution
            [linie(stamm, netz.kanten[k]) for k in ("D01", "D02")], breite=2)
    netz.setze_sperren(cfg["stoerungen"])                                 # gesperrte Kanten (rot)
    _linien(fig, "zeitweise gesperrt", "red", [linie(stamm, d) for k, d in netz.kanten.items()
                                               if not netz.offen(k) and d["route"] != "distribution"],
            dash="dot", breite=2)

    orte = {netz.kanten[k][s] for k in genutzt | {"D01", "D02"} for s in ("von", "nach")}
    o = kn.loc[sorted(orte)]
    fig.add_trace(go.Scattergeo(lat=o.lat, lon=o.lon, mode="markers", name="Standorte", text=o.name,
                                hoverinfo="text", marker=dict(size=7, color="dimgray")))
    t2a = t2[t2.liefert_an.isin(aktive_lief)]
    fig.add_trace(go.Scattergeo(lat=t2a.lat, lon=t2a.lon, mode="markers", name="Tier-2", text=t2a.name,
                                hoverinfo="text", marker=dict(size=7, color="#8c564b", symbol="diamond")))
    fig.add_trace(go.Scattergeo(lat=[kn.loc["HN", "lat"]], lon=[kn.loc["HN", "lon"]], mode="markers",
                                name="Montage Heilbronn", marker=dict(size=16, color="black", symbol="star")))

    # Animation: Sendungen unterwegs, ein Bild je `schritt` Tage
    etappen = [(k, a, b, r.bauteil) for r in send.itertuples() for k, a, b in r.etappen]
    wege = {k: linie(stamm, netz.kanten[k]) for k in genutzt}

    def positionen(t):
        la, lo, txt, col = [], [], [], []
        for k, a, b, bt in etappen:
            if a <= t < b:
                p = _punkt(*wege[k], (t - a) / (b - a))
                la.append(p[0]); lo.append(p[1]); txt.append(bt)
                col.append(FARBEN.get(netz.kanten[k]["modus"], "grey"))
        return dict(lat=la, lon=lo, text=txt, marker=dict(size=10, color=col, line=dict(width=1, color="white")))

    fig.add_trace(go.Scattergeo(mode="markers", name="Sendungen", hoverinfo="text", **positionen(0)))
    tage = list(range(0, cfg["tage"], schritt))
    fig.frames = [go.Frame(name=str(t), traces=[len(fig.data) - 1], data=[go.Scattergeo(**positionen(t))])
                  for t in tage]
    fig.update_layout(
        height=600, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.05),
        geo=dict(projection_type="natural earth", showland=True, landcolor="#f2f2f2", showcountries=True,
                 countrycolor="#d0d0d0", showocean=True, oceancolor="#eaf2fb"),
        updatemenus=[dict(type="buttons", x=0.01, y=0.02, xanchor="left", yanchor="bottom", buttons=[
            dict(label="▶", method="animate", args=[None, dict(frame=dict(duration=300), fromcurrent=True)]),
            dict(label="⏸", method="animate", args=[[None], dict(frame=dict(duration=0), mode="immediate")])])],
        sliders=[dict(x=0.1, len=0.88, y=0.02, currentvalue=dict(prefix="Tag "), steps=[
            dict(label=str(t), method="animate", args=[[str(t)], dict(mode="immediate", frame=dict(duration=0))])
            for t in tage])])
    return fig
