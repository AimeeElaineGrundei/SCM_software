"""Statische Netzwerkkarte (Plotly): aktive Routen je Verkehrsträger, gesperrte Kanten rot.

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
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


def karte(teile, netz, stamm) -> go.Figure:
    fig = go.Figure()
    # aktive Routen, je Verkehrsträger eine Spur
    je_modus: dict[str, tuple[list, list]] = {}
    for route in teile.kanten:
        for k in route:
            d = netz.kanten[k]
            la, lo = linie(stamm, d)
            x = je_modus.setdefault(d["modus"], ([], []))
            x[0].extend(la + [None])
            x[1].extend(lo + [None])
    for m, (la, lo) in je_modus.items():
        fig.add_trace(go.Scattergeo(lat=la, lon=lo, mode="lines", name=NAMEN.get(m, m),
                                    line=dict(width=2.5, color=FARBEN.get(m, "grey")), hoverinfo="skip"))
    # gesperrte Kanten
    la, lo = [], []
    for k, d in netz.kanten.items():
        if not netz.offen(k):
            a, b = linie(stamm, d)
            la += a + [None]
            lo += b + [None]
    if la:
        fig.add_trace(go.Scattergeo(lat=la, lon=lo, mode="lines", name="gesperrt",
                                    line=dict(width=2, color="red", dash="dot"), hoverinfo="skip"))
    # Standorte
    genutzt = {netz.kanten[k][s] for r in teile.kanten for k in r for s in ("von", "nach")}
    kn = stamm["knoten"].loc[sorted(genutzt)]
    fig.add_trace(go.Scattergeo(
        lat=kn.lat, lon=kn.lon, mode="markers", name="Standorte", text=kn.name, hoverinfo="text",
        marker=dict(size=[16 if i == "HN" else 8 for i in kn.index],
                    color=["black" if i == "HN" else "dimgray" for i in kn.index],
                    symbol=["star" if i == "HN" else "circle" for i in kn.index])))
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.02),
                      geo=dict(projection_type="natural earth", showland=True, landcolor="#f2f2f2",
                               showcountries=True, countrycolor="#d0d0d0", showocean=True,
                               oceancolor="#eaf2fb"))
    return fig
