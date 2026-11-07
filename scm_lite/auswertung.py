"""Kennzahlen, Szenariovergleich, Pareto-Vergleich von Maßnahmen, Sensitivitätsanalyse.

Kennzeichen: KI (Referenz) | nachprogrammieren: Elaine
"""
import copy

import pandas as pd

from .daten import lade_szenario, szenario_liste
from .simulation import simuliere

# Zielkriterien und ob niedrig ("min") oder hoch ("max") besser ist
KENNZAHLEN = {"Kosten [€/Uhr]": "min", "Lieferzeit [Tage]": "min", "Kapitalbindung [€]": "min",
              "CO₂e [kg/Uhr]": "min", "Lieferfähigkeit [%]": "max"}


def rechne(cfg: dict, stamm: dict) -> dict:
    """Simulation + Kennzahlen in einem Schritt."""
    roh = simuliere(cfg, stamm)
    s, tage, L = roh["sendungen"], roh["tage"], stamm["lieferanten"]

    teile = []
    for b, lid in cfg["lieferanten"].items():
        g = s[s.bauteil == b]
        status = [f"{roh['ausfall_tage'][b]} T Lieferant ausgefallen" if roh["ausfall_tage"][b] else "",
                  f"{roh['kein_weg'][b]} T kein offener Weg" if roh["kein_weg"][b] else "",
                  f"Ersatz {g[g.lieferant != lid].lieferant.iloc[0]}" if (g.lieferant != lid).any() else "",
                  f"umgeleitet ({g.umgeleitet.sum()} von {len(g)})" if g.umgeleitet.any() else ""]
        teile.append({"bauteil": b, "lieferant": ", ".join(g.lieferant.unique()), "bestellungen": len(g),
                      "kosten_stk": (g.kosten_stk * g.menge).sum() / g.menge.sum(),
                      "lieferzeit": (g.ankunft - g.bestellt).mean(),
                      "co2_g_stk": (g.co2_g_stk * g.menge).sum() / g.menge.sum(),
                      "status": "; ".join(x for x in status if x) or "normal"})
    teile = pd.DataFrame(teile)

    preis = {b: L.loc[l, "preis_eur"] * cfg["preis_faktor"] for b, l in cfg["lieferanten"].items()}
    wert = sum((tage[f"lager_{b}"] + tage[f"unterwegs_{b}"]) * p for b, p in preis.items())
    uhren = max(1, tage.montage.sum())
    kpi = {
        "Kosten [€/Uhr]": teile.kosten_stk.sum() + wert.mean() * cfg["kapitalzins_pa"] / uhren
                          + cfg["montage_kosten_pro_uhr"] + cfg["versand_pro_paket"],
        "Lieferzeit [Tage]": teile.lieferzeit.max(),
        "Kapitalbindung [€]": wert.mean(),
        "CO₂e [kg/Uhr]": teile.co2_g_stk.sum() / 1000 + cfg["co2e_kg_pro_paket"],
        "Lieferfähigkeit [%]": tage.sofort.sum() / max(1, tage.nachfrage.sum()) * 100,
    }
    return {"kpi": kpi, "teile": teile, **roh}


def vergleich(stamm: dict) -> pd.DataFrame:
    """Alle Szenario-Dateien → eine Zeile je Szenario."""
    zeilen = []
    for key in szenario_liste():
        cfg = lade_szenario(key)
        r = rechne(cfg, stamm)
        was = "; ".join(f"{t.bauteil}: {t.status}" for t in r["teile"].itertuples() if t.status != "normal")
        zeilen.append({"Szenario": cfg["name"], **r["kpi"], "Was passiert": was or "–"})
    return pd.DataFrame(zeilen)


def massnahmen(cfg: dict, stamm: dict) -> pd.DataFrame:
    """Handlungsalternativen: Sicherheitsbestand × Zweitlieferant, mit Pareto-Markierung."""
    zeilen = []
    for sb in (0, 7, 14, 28, 42):
        for zweit in (False, True):
            c = copy.deepcopy(cfg)
            c["sicherheitstage"], c["zweitlieferant"] = sb, zweit
            zeilen.append({"Maßnahme": f"Lager {sb} T" + (" + Zweitlieferant" if zweit else ""),
                           "Zweitlieferant": zweit, **rechne(c, stamm)["kpi"]})
    df = pd.DataFrame(zeilen)
    df["Pareto-optimal"] = ist_pareto(df, ["Kosten [€/Uhr]", "Lieferfähigkeit [%]", "Kapitalbindung [€]"])
    return df


def ist_pareto(df: pd.DataFrame, spalten: list[str]) -> list[bool]:
    """True, wenn keine andere Zeile überall mindestens gleich gut und irgendwo besser ist."""
    w = [[r[s] if KENNZAHLEN[s] == "min" else -r[s] for s in spalten] for _, r in df.iterrows()]
    return [not any(all(b <= a for a, b in zip(x, y)) and any(b < a for a, b in zip(x, y)) for y in w) for x in w]


def sensitivitaet(cfg: dict, stamm: dict, delta: float = 0.10) -> pd.DataFrame:
    """Parameter um ±10 % ändern → Abweichung von Kosten und Lieferfähigkeit zur Ausgangslage."""
    basis = rechne(cfg, stamm)["kpi"]
    zeilen = []
    for name, feld in {"Nachfrage": "uhren_pro_jahr", "Einkaufspreise": "preis_faktor",
                       "Transportzeiten": "transport_faktor", "Sicherheitstage": "sicherheitstage"}.items():
        for vz in (-1, 1):
            c = copy.deepcopy(cfg)
            c[feld] = cfg[feld] * (1 + vz * delta)
            k = rechne(c, stamm)["kpi"]
            zeilen.append({"Parameter": name, "Änderung": f"{vz * delta:+.0%}",
                           "Δ Kosten [€/Uhr]": k["Kosten [€/Uhr]"] - basis["Kosten [€/Uhr]"],
                           "Δ Lieferfähigkeit [%-Pkt]": k["Lieferfähigkeit [%]"] - basis["Lieferfähigkeit [%]"]})
    return pd.DataFrame(zeilen)
