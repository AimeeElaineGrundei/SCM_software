"""Deterministische Berechnung eines Szenarios (ohne Zufall, ohne Zeitverlauf).

Je Bauteil: aktiver Lieferant → Route (Standard oder Umleitung) → Kosten, Zeit, CO2e,
Kapitalbindung und Fehltage. Daraus die Kennzahlen je Uhr.

Kosten, CO2e und Kapital werden zeitanteilig gemittelt: Während der Störungsdauer gilt der
Ersatzlieferant bzw. die Umleitung, im Rest des Jahres der Normalzustand.

Lieferfähigkeit (Näherung): Ein Bauteil fehlt an so vielen Tagen, wie eine Störung
länger dauert als der Sicherheitsbestand reicht. Da jede Uhr alle Bauteile braucht,
zählt das Bauteil mit den meisten Fehltagen.  β = 1 − Fehltage / 365.

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
import pandas as pd

from .daten import lade_szenario, szenario_liste
from .netz import Netz

# Kennzahlen: Einheit für die Anzeige und ob niedrig oder hoch besser ist
KENNZAHLEN = {
    "Kosten [€/Uhr]": "min",
    "Lieferzeit [Tage]": "min",
    "Kapitalbindung [€]": "min",
    "CO₂e [kg/Uhr]": "min",
    "Lieferfähigkeit [%]": "max",
    "Auslastung Montage [%]": "min",
}

MODUS_NAME = {"see": "See", "bahn": "Bahn", "bahn_cn": "Bahn (Seidenstraße)", "lkw": "Lkw",
              "binnen": "Binnenschiff", "luft": "Luft"}


def routentext(netz: Netz, lid: str, route: list[str]) -> str:
    teile = [lid]
    for k in route:
        d = netz.kanten[k]
        via = " (Kap)" if d["route"] == "kap" else " (Suez)" if "suez" in d["tags"] else \
              " (Panama)" if "panama" in d["tags"] else ""
        teile.append(f"→ {MODUS_NAME.get(d['modus'], d['modus'])}{via} → {d['nach']}")
    return " ".join(teile)


def _teil(netz, lief, lid, route, cfg, d):
    l = lief.loc[lid]
    kg = l.gewicht_brutto_g / 1000
    kanten = [netz.kanten[k] for k in route]
    transport = sum(k["tage_modus"] for k in kanten)
    fracht = sum(k["kosten_eur_pro_kg"] for k in kanten) * kg
    zoll = l.zollsatz * (l.preis_eur + fracht)
    co2_g = sum(kg / 1000 * k["distanz_km"] * k["co2e_g_pro_tkm"] for k in kanten)
    kapital = l.preis_eur * d * (cfg["sicherheitstage"] + cfg["bestellrhythmus_tage"] / 2 + transport)
    return dict(lieferant=lid, name=l["name"], land=l.land, preis=l.preis_eur, fracht=fracht, zoll=zoll,
                vorlauf=l.vorlaufzeit_tage, transport=transport, tage=l.vorlaufzeit_tage + transport,
                co2e_g=co2_g, kapital=kapital)


def berechne(cfg: dict, stamm: dict) -> tuple[pd.DataFrame, dict]:
    lief = stamm["lieferanten"]
    basis = Netz(stamm)
    netz = Netz(stamm)
    netz.sperren(cfg["stoerungen"])
    ausfall = {s["ziel"]: s["dauer_tage"] for s in cfg["stoerungen"] if s["typ"] == "lieferant"}
    sperrdauer = max([s["dauer_tage"] for s in cfg["stoerungen"] if s["typ"] in ("engpass", "knoten")], default=0)
    d = cfg["uhren_pro_jahr"] * cfg["nachfrage_faktor"] / 365
    sb, krit, luft = cfg["sicherheitstage"], cfg["routing_kriterium"], cfg["luftfracht_erlaubt"]

    zeilen = []
    for komp, lid in cfg["lieferanten"].items():
        l_basis = lief.loc[lid, "vorlaufzeit_tage"] + sum(basis.kanten[k]["tage_modus"] for k in basis.standardroute(lid))
        aktiv, status, fehltage, dauer_rel = lid, "normal", 0.0, 0.0

        if lid in ausfall:                                   # Lieferantenausfall
            dauer = dauer_rel = ausfall[lid]
            zweit = (cfg.get("zweitlieferanten") or {}).get(komp)
            if cfg["reaktion"]["zweitlieferant"] and zweit and zweit not in ausfall:
                aktiv = zweit
                r2 = netz.route(zweit, krit, luft) or []
                l2 = lief.loc[zweit, "vorlaufzeit_tage"] + sum(netz.kanten[k]["tage_modus"] for k in r2)
                fehltage = max(0.0, min(dauer, l2) - sb)
                status = f"Ersatz: {zweit}"
            else:
                fehltage = max(0.0, dauer - sb)
                status = "Ausfall ohne Ersatz"

        route = netz.route(aktiv, krit, luft)
        if route is None:                                    # kein offener Weg
            route = basis.standardroute(aktiv)
            fehltage = max(fehltage, max(0.0, sperrdauer - sb))
            status = "kein offener Weg"
            if aktiv == lid:
                dauer_rel = max(dauer_rel, sperrdauer)
        elif route != basis.standardroute(aktiv):
            l_neu = lief.loc[aktiv, "vorlaufzeit_tage"] + sum(netz.kanten[k]["tage_modus"] for k in route)
            delta = l_neu - l_basis
            if aktiv == lid:
                fehltage = max(fehltage, max(0.0, delta - sb))
            status = (status + ", " if status != "normal" else "") + f"umgeleitet ({delta:+.0f} T)"
            if aktiv == lid:      # beim Ersatzlieferanten zählt die Ausfalldauer
                dauer_rel = max(dauer_rel, sperrdauer)

        t = _teil(netz, lief, aktiv, route, cfg, d)
        if dauer_rel > 0:   # zeitanteilig mit Normalzustand mitteln
            normal = _teil(basis, lief, lid, basis.standardroute(lid), cfg, d)
            a = min(1.0, dauer_rel / 365)
            for f in ("preis", "fracht", "zoll", "co2e_g", "kapital"):
                t[f] = (1 - a) * normal[f] + a * t[f]
            if aktiv != lid:
                t["lieferant"] = f"{lid} → {aktiv} ({dauer_rel:.0f} T)"
        t.update(bauteil=komp, status=status, fehltage=fehltage, route=routentext(netz, aktiv, route),
                 kanten=route)
        zeilen.append(t)

    teile = pd.DataFrame(zeilen)
    menge = cfg["uhren_pro_jahr"] * cfg["nachfrage_faktor"]
    kapital = teile.kapital.sum()
    kpi = {
        "Kosten [€/Uhr]": (teile.preis + teile.fracht + teile.zoll).sum()
                          + kapital * cfg["kapitalzins_pa"] / menge
                          + cfg["montage_kosten_pro_uhr"] + cfg["versand_pro_paket"],
        "Lieferzeit [Tage]": teile.tage.max(),
        "Kapitalbindung [€]": kapital,
        "CO₂e [kg/Uhr]": teile.co2e_g.sum() / 1000 + cfg["co2e_kg_pro_paket"],
        "Lieferfähigkeit [%]": max(0.0, 1 - teile.fehltage.max() / 365) * 100,
        "Auslastung Montage [%]": d / cfg["montage_kapazitaet_pro_tag"] * 100,
    }
    return teile, kpi


def vergleiche_alle(stamm: dict) -> pd.DataFrame:
    """Alle Szenario-Dateien rechnen → eine Zeile je Szenario (inkl. betroffener Bauteile)."""
    zeilen = []
    for key in szenario_liste():
        cfg = lade_szenario(key)
        teile, kpi = berechne(cfg, stamm)
        betroffen = teile[teile.status != "normal"]
        zeilen.append({"key": key, "Szenario": cfg["name"], **kpi,
                       "Was passiert": "; ".join(f"{r.bauteil}: {r.status}" for r in betroffen.itertuples()) or "–"})
    return pd.DataFrame(zeilen)
