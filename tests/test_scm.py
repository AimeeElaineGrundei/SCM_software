import copy, math, os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import yaml
from scm.config import (load_base, list_scenarios, apply_scenario, build_config, check_requirements,
                        ConfigError, CONFIG_DIR)
from scm.engine import SimulationEngine, reference_landed_cost, plan_lead_days, plan_unit_costs
from scm.network import SupplyNetwork, Disruptions
from scm.runner import run_replications, summarize, compare_scenarios, pareto_front

BASE = load_base()
SC = list_scenarios()


def max_lead(res, comp):
    ev = res.events[(res.events.type == "receipt") & (res.events.comp == comp) & (res.events.day >= 0)]
    return max(float(i.split()[1]) for i in ev["info"])


def cfg(name="S0_basis", **ov):
    return apply_scenario(BASE, SC[name], param_overrides=ov or None)


def raw():
    with open(os.path.join(CONFIG_DIR, "base.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- Konfiguration
def test_requirements_all_met():
    assert all(ok for ok, _ in check_requirements(BASE, len(SC), 5))


@pytest.mark.parametrize("mut,msg", [
    (lambda r: r["edges"][0].update(days=[5, 2, 1]), "min <= Modus"),
    (lambda r: r["edges"][0].update(mode="rakete"), "unbekannt"),
    (lambda r: r["components"][0].update(duty_rate=4.5), "Zollsatz"),
    (lambda r: r["base_routes"].update(uhrwerk=["e_zb_hn"]), "beginnt nicht"),
    (lambda r: r["params"].update(air_policy="x"), "air_policy"),
])
def test_invalid_config_rejected(mut, msg):
    r = raw()
    mut(r)
    with pytest.raises(ConfigError, match=msg):
        build_config(r)


def test_unknown_param_and_event_rejected():
    with pytest.raises(ConfigError):
        apply_scenario(BASE, {"params": {"gibt_es_nicht": 1}})
    with pytest.raises(ConfigError):
        apply_scenario(BASE, {"events": [{"type": "meteor", "start": 1}]})


# ---------------------------------------------------------------- Verifikation (Handrechnung)
def test_deterministic_matches_hand_calculation():
    c = cfg(stochastic=False)
    r = SimulationEngine(c).run()
    assert r.kpis["landed_cost"] == pytest.approx(reference_landed_cost(c), rel=1e-6)
    assert r.kpis["servicegrad"] == pytest.approx(1.0)
    expected_lead = max(plan_lead_days(c, k) for k in c.components)
    # Lieferzeit = Bestellung -> Wareneingang der langsamsten Komponente
    assert r.kpis["lieferzeit"] == pytest.approx(expected_lead, abs=1.0)


def test_unit_costs_by_hand():
    c = cfg()
    u = plan_unit_costs(c, "gehaeuse")
    assert u["goods"] == pytest.approx(25.0)
    assert u["duty"] == pytest.approx(0.027 * (25.0 + u["freight"]), rel=1e-9)


def test_conservation_of_flows():
    eng = SimulationEngine(cfg(), seed=7, rep=1)
    r = eng.run()
    d = pd.DataFrame(eng.daily_rows)
    assert (d["demand"] == d["sold"] + d["lost"]).all()
    ev = r.events
    for c in BASE.components:
        init = eng.s[c] + eng.qty(c)
        received = ev[(ev.type == "receipt") & (ev.comp == c)].qty.sum()
        assembled = d["assembled"].sum()
        assert d[f"stock_{c}"].iloc[-1] == init + received - assembled
    assert (d[[f"stock_{c}" for c in BASE.components]] >= 0).all().all()


def test_reproducible_and_seed_sensitive():
    a = SimulationEngine(cfg(), seed=1, rep=0).run().kpis
    b = SimulationEngine(cfg(), seed=1, rep=0).run().kpis
    c = SimulationEngine(cfg(), seed=2, rep=0).run().kpis
    assert a == b and a != c


def test_common_random_numbers_same_demand_across_scenarios():
    a = SimulationEngine(cfg("S0_basis"), seed=3, rep=0).run().daily["demand"]
    b = SimulationEngine(cfg("S1_suez"), seed=3, rep=0).run().daily["demand"]
    assert (a == b).all()


# ---------------------------------------------------------------- Szenarien
def test_suez_blocks_route_and_lengthens_lead_time():
    base = SimulationEngine(cfg("S0_basis"), seed=5).run()
    s1 = SimulationEngine(cfg("S1_suez"), seed=5).run()
    assert (s1.events.type == "reroute").any()
    assert max_lead(s1, "gehaeuse") > max_lead(base, "gehaeuse") + 10
    assert s1.kpis["servicegrad"] < base.kpis["servicegrad"]
    used = set(s1.legs[(s1.legs.t0 > 70) & (s1.legs.t0 < 170) & (s1.legs.kind == "inbound")].dst)
    assert "n_suez" not in used


def test_supplier_outage_delays_orders_and_hits_service():
    base = SimulationEngine(cfg("S0_basis"), seed=5).run()
    s2 = SimulationEngine(cfg("S2_uhrwerk_ausfall"), seed=5).run()
    assert (s2.events.type == "supplier_wait").any()
    assert s2.kpis["servicegrad"] < base.kpis["servicegrad"]


def test_demand_spike_and_rhine_mode_block():
    s3 = SimulationEngine(cfg("S3_nachfrage"), seed=5).run()
    q4 = s3.daily[s3.daily.day >= 274].demand.mean()
    q1 = s3.daily[s3.daily.day < 90].demand.mean()
    assert q4 > 1.15 * q1
    s4 = SimulationEngine(cfg("S4_rhein"), seed=5).run()
    late = s4.legs[(s4.legs.t0 > 205) & (s4.legs.t0 < 255) & (s4.legs.kind == "inbound")]
    assert "binnenschiff" not in set(late["mode"])


def test_air_policy_on_disruption_faster_but_more_co2():
    slow = SimulationEngine(cfg("S1_suez"), seed=5).run()
    air = SimulationEngine(cfg("S1_suez", air_policy="on_disruption"), seed=5).run()
    assert max_lead(air, "gehaeuse") < max_lead(slow, "gehaeuse")
    assert air.kpis["co2"] > slow.kpis["co2"]


def test_scenarios_use_same_model_only_params_events_differ():
    for k, sc in SC.items():
        c = apply_scenario(BASE, sc)
        assert c.nodes.keys() == BASE.nodes.keys() and c.edges.keys() == BASE.edges.keys()


# ---------------------------------------------------------------- Netz / Routing
def test_dijkstra_avoids_blocked_node_and_returns_none_if_unreachable():
    c = cfg("S1_suez")
    net, dis = SupplyNetwork(c), Disruptions(c)
    path = net.dijkstra("sup_gehaeuse", c.focal, 100, dis, 100, "time", False)
    nodes = {c.edges[e].dst for e in path}
    assert "n_suez" not in nodes and "n_kap" in nodes
    c2 = apply_scenario(BASE, {"events": [{"type": "block_node", "node": "n_suez", "start": 0, "end": 99},
                                          {"type": "block_node", "node": "n_kap", "start": 0, "end": 99}]})
    assert SupplyNetwork(c2).dijkstra("sup_gehaeuse", c2.focal, 5, Disruptions(c2), 100, "time", False) is None


def test_route_weight_changes_choice():
    c = cfg(route_weight="cost")
    net, dis = SupplyNetwork(c), Disruptions(c)
    by_cost = net.dijkstra("p_rotterdam", c.focal, 0, dis, 1000, "cost", False)
    by_time = net.dijkstra("p_rotterdam", c.focal, 0, dis, 1000, "time", False)
    assert c.edges[by_cost[0]].mode == "binnenschiff" and c.edges[by_time[0]].mode == "lkw"


# ---------------------------------------------------------------- Auswertung
def test_summary_ci_and_pareto():
    res = run_replications(cfg(), 6, seed=11)
    s = summarize(res)
    assert (s["ci_low"] <= s["mean"]).all() and (s["mean"] <= s["ci_high"]).all()
    df = pd.DataFrame(dict(landed_cost=[1, 2, 3], lieferzeit=[1, 1, 1], co2=[1, 1, 0], lagerwert=[1, 1, 1],
                           ok=[True, True, True]))
    nd = pareto_front(df, "ok")
    assert list(nd) == [True, False, True]
    df.loc[0, "ok"] = False
    assert list(pareto_front(df, "ok")) == [False, True, True]


def test_stress_scenarios_worse_than_base_in_service():
    tab, _ = compare_scenarios(BASE, reps=4, seed=21)
    base = tab[tab.key == "S0_basis"].servicegrad.iloc[0]
    for k in ("S1_suez", "S2_uhrwerk_ausfall", "S3_nachfrage"):
        assert tab[tab.key == k].servicegrad.iloc[0] < base


# ---------------------------------------------------------------- Stammdaten-Register
def test_master_data_override_changes_costs_and_rejects_invalid():
    from scm.config import master_tables, apply_master_data
    m = master_tables(BASE)
    assert reference_landed_cost(apply_master_data(BASE, m["comps"], m["edges"], m["sups"], m["gen"])) == pytest.approx(reference_landed_cost(BASE))
    m["comps"][0]["price_eur"] = 200          # Uhrwerk +50 €
    m["comps"][2]["duty_pct"] = 4.6           # Gehäuse-Zoll 4,6 %
    c = apply_master_data(BASE, m["comps"])
    assert reference_landed_cost(c) - reference_landed_cost(BASE) > 50
    r = SimulationEngine(apply_scenario(c, SC["S0_basis"], param_overrides=dict(stochastic=False))).run()
    assert r.kpis["landed_cost"] == pytest.approx(reference_landed_cost(c), rel=1e-6)
    m["comps"][0]["price_eur"] = -5
    with pytest.raises(ConfigError):
        apply_master_data(BASE, m["comps"])
    m = master_tables(BASE)
    m["edges"][0]["d_min"], m["edges"][0]["d_max"] = 9, 2
    with pytest.raises(ConfigError):
        apply_master_data(BASE, edges=m["edges"])
    assert BASE.components["uhrwerk"].price_eur == 150   # Original unverändert
