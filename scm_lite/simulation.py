"""Tagesschleife: Beschaffung → Transport → Lager → Montage → Kunde (deterministisch).

Je Tag:
  1. aktive Störungen setzen (Sperren, Ausfälle, Nachfrage)
  2. eingetroffene Sendungen einbuchen
  3. Nachfrage + Rückstand montieren, soweit alle Teile da sind
  4. je Bauteil bestellen, wenn Lager + Unterwegs ≤ Tagesbedarf · (Wiederbeschaffungszeit + Sicherheitstage)

Kennzeichen: KI (Referenz) | nachprogrammieren: Alex
"""
import math

import pandas as pd

from .netz import Netz


def aktiv(stoerungen: list[dict], t: int) -> list[dict]:
    return [s for s in stoerungen if s["start_tag"] <= t < s["start_tag"] + s["dauer_tage"]]


def faellt_aus(lid: str, t: int, cfg: dict, tier2: pd.DataFrame) -> bool:
    """Direkter Ausfall – oder Tier-2-Ausfall, der länger dauert als der Puffer des Tier-1."""
    for s in aktiv(cfg["stoerungen"], t):
        if s["typ"] == "lieferant" and s["ziel"] == lid:
            return True
        if s["typ"] == "tier2" and tier2.loc[s["ziel"], "liefert_an"] == lid \
                and t >= s["start_tag"] + cfg["tier2_puffer_tage"]:
            return True
    return False


def simuliere(cfg: dict, stamm: dict) -> dict:
    netz, lief = Netz(stamm), stamm["lieferanten"].to_dict("index")
    teile = cfg["lieferanten"]                                    # bauteil -> lieferant_id
    d = cfg["uhren_pro_jahr"] / 365                               # Uhren je Tag
    menge = {b: math.ceil(d * cfg["bestellrhythmus_tage"]) for b in teile}

    def wbz(lid, route):                                          # Wiederbeschaffungszeit [Tage]
        return lief[lid]["vorlaufzeit_tage"] + sum(netz.kanten[k]["tage_modus"] for k in route) * cfg["transport_faktor"]

    lager = {b: d * (wbz(l, netz.standardroute(l)) + cfg["sicherheitstage"]) + menge[b] for b, l in teile.items()}
    unterwegs = {b: 0 for b in teile}
    sendungen, tage, offen = [], [], []
    rueckstand, rest = 0, 0.0
    ausfall_tage, kein_weg = {b: 0 for b in teile}, {b: 0 for b in teile}

    for t in range(cfg["tage"]):
        akt = aktiv(cfg["stoerungen"], t)                         # 1. Störungen
        netz.setze_sperren(akt)
        faktor = math.prod(s["faktor"] for s in akt if s["typ"] == "nachfrage")

        for s in [s for s in offen if s["ankunft"] <= t]:         # 2. Wareneingang
            lager[s["bauteil"]] += s["menge"]
            unterwegs[s["bauteil"]] -= s["menge"]
            offen.remove(s)

        rest += d * faktor                                        # 3. Nachfrage + Montage
        nachfrage = int(rest)
        rest -= nachfrage
        montage = int(min(cfg["montage_kapazitaet_pro_tag"], nachfrage + rueckstand, *lager.values()))
        for b in lager:
            lager[b] -= montage
        aus_rueckstand = min(rueckstand, montage)
        sofort = min(nachfrage, montage - aus_rueckstand)
        rueckstand += nachfrage - sofort - aus_rueckstand

        for b, lid in teile.items():                              # 4. Bestellen
            if faellt_aus(lid, t, cfg, stamm["tier2"]):
                ausfall_tage[b] += 1
                ersatz = cfg["zweitlieferanten"].get(b)
                lid = ersatz if cfg["zweitlieferant"] and ersatz and not faellt_aus(ersatz, t, cfg, stamm["tier2"]) else None
                if lid is None:
                    continue
            route = netz.route(lid)
            if route is None:
                kein_weg[b] += 1
                continue
            while lager[b] + unterwegs[b] <= d * faktor * (wbz(lid, route) + cfg["sicherheitstage"]):
                s = _sendung(b, lid, route, t, menge[b], netz, lief[lid], cfg)
                sendungen.append(s)
                offen.append(s)
                unterwegs[b] += menge[b]

        tage.append({"tag": t, "nachfrage": nachfrage, "montage": montage, "sofort": sofort,
                     "rueckstand": rueckstand, **{f"lager_{b}": lager[b] for b in teile},
                     **{f"unterwegs_{b}": unterwegs[b] for b in teile}})

    return {"tage": pd.DataFrame(tage), "sendungen": pd.DataFrame(sendungen),
            "ausfall_tage": ausfall_tage, "kein_weg": kein_weg, "netz": netz}


def _sendung(bauteil, lid, route, t, menge, netz, l, cfg) -> dict:
    """Bestellung mit Kosten, CO2e und Etappen (für die Animation)."""
    kg = l["gewicht_brutto_g"] / 1000
    preis = l["preis_eur"] * cfg["preis_faktor"]
    fracht = sum(netz.kanten[k]["kosten_eur_pro_kg"] for k in route) * kg
    start, etappen = t + l["vorlaufzeit_tage"], []
    for k in route:
        dauer = netz.kanten[k]["tage_modus"] * cfg["transport_faktor"]
        etappen.append((k, start, start + dauer))
        start += dauer
    return {"bauteil": bauteil, "lieferant": lid, "bestellt": t, "ankunft": start, "menge": menge,
            "kosten_stk": preis + fracht + l["zollsatz"] * (preis + fracht),
            "co2_g_stk": sum(kg / 1000 * netz.kanten[k]["distanz_km"] * netz.kanten[k]["co2e_g_pro_tkm"] for k in route),
            "umgeleitet": route != netz.standardroute(lid), "etappen": etappen}
