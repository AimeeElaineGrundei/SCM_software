"""Kennzeichen: KI – Plausibilitätstests der einfachen Version."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scm_lite.daten import lade_stammdaten, lade_szenario, szenario_liste  # noqa: E402
from scm_lite.netz import Netz  # noqa: E402
from scm_lite.rechnung import berechne  # noqa: E402

S = lade_stammdaten()


def kpi(key, **aend):
    cfg = lade_szenario(key)
    cfg.update(aend)
    return berechne(cfg, S)[1]


def test_alle_szenarien_rechnen():
    assert len(szenario_liste()) >= 4
    for k in szenario_liste():
        assert kpi(k)["Kosten [€/Uhr]"] > 0


def test_basis_voll_lieferfaehig():
    assert kpi("s0_basis")["Lieferfähigkeit [%]"] == 100


def test_saphirglas_posterroute_45_tage():
    n = Netz(S)
    assert sum(n.kanten[k]["tage_modus"] for k in n.standardroute("S_GLT_A")) == 45


def test_suez_sperre_fuehrt_ueber_kap():
    n = Netz(S)
    n.sperren([{"typ": "engpass", "ziel": "suez", "dauer_tage": 100}])
    assert any(n.kanten[k]["route"] == "kap" for k in n.route("U_SEIKO"))


def test_ausfall_senkt_lieferfaehigkeit_und_sicherheitsbestand_hilft():
    ohne = kpi("s2_seiko_ausfall")["Lieferfähigkeit [%]"]
    assert ohne < 95
    assert kpi("s2_seiko_ausfall", sicherheitstage=60)["Lieferfähigkeit [%]"] == 100


def test_nachfrage_erhoeht_kapital():
    assert kpi("s4_nachfrage_q4")["Kapitalbindung [€]"] > kpi("s0_basis")["Kapitalbindung [€]"]
