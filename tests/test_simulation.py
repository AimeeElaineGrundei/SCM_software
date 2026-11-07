"""Verifikation und Plausibilität.  Start: python -m pytest

Kennzeichen: KI (Referenz) | nachprogrammieren: Alex (Verifikation), Elaine (Kennzahlen)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scm_lite.auswertung import massnahmen, rechne  # noqa: E402
from scm_lite.daten import lade_stammdaten, lade_szenario, szenario_liste  # noqa: E402
from scm_lite.netz import Netz  # noqa: E402

S = lade_stammdaten()


def kpi(key, **aenderung):
    cfg = lade_szenario(key)
    cfg.update(aenderung)
    return rechne(cfg, S)["kpi"]


def test_mindestanforderungen():
    cfg = lade_szenario("s0_basis")
    L = S["lieferanten"].loc[list(cfg["lieferanten"].values())]
    assert len(L) == 6 and (L.land == "FR").any()                       # 6 Tier-1, davon 1 EU
    anzahl_t2 = S["tier2"].liefert_an.value_counts().reindex(L.index, fill_value=0)
    assert (anzahl_t2 >= 2).sum() >= 2                                   # 2 Tier-1 mit je 2 Tier-2
    assert {"see", "bahn", "lkw", "binnen"} <= set(S["kanten"].modus)    # Pflicht-Verkehrsträger
    assert len(szenario_liste()) >= 4                                    # Basis + ≥ 3 Szenarien
    assert len(kpi("s0_basis")) >= 4                                     # ≥ 4 Zielkriterien


def test_handrechnung_saphirglas():
    """Lieferzeit = Vorlauf 7 + Lkw 1 + See 40 + Binnenschiff 4 = 52 Tage."""
    teile = rechne(lade_szenario("s0_basis"), S)["teile"].set_index("bauteil")
    assert teile.loc["saphirglas", "lieferzeit"] == 52


def test_basis_voll_lieferfaehig():
    assert kpi("s0_basis")["Lieferfähigkeit [%]"] == 100


def test_suez_sperre_fuehrt_ueber_kap():
    n = Netz(S)
    n.setze_sperren([{"typ": "engpass", "ziel": "suez"}])
    assert any(n.kanten[k]["route"] == "kap" for k in n.route("U_SEIKO"))


def test_ausfall_und_gegenmassnahmen():
    ohne = kpi("s2_seiko_ausfall")["Lieferfähigkeit [%]"]
    assert ohne < 95
    assert kpi("s2_seiko_ausfall", zweitlieferant=True)["Lieferfähigkeit [%]"] > ohne
    assert kpi("s2_seiko_ausfall", sicherheitstage=60)["Lieferfähigkeit [%]"] == 100


def test_tier2_ausfall_wirkt_erst_nach_puffer():
    assert kpi("s6_tier2_ausfall")["Lieferfähigkeit [%]"] < 100
    assert kpi("s6_tier2_ausfall", tier2_puffer_tage=60)["Lieferfähigkeit [%]"] == 100


def test_pareto():
    assert massnahmen(lade_szenario("s2_seiko_ausfall"), S)["Pareto-optimal"].any()
