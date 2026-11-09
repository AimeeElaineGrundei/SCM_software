"""Experiment-Runner: Replikationen, Konfidenzintervalle, Szenariovergleich, Rastersuche, Pareto."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from scipy import stats

from .config import Config, apply_scenario, list_scenarios
from .engine import SimulationEngine, RunResult

CRITERIA = [  # Schlüssel, Anzeigename, Einheit, Richtung
    ("landed_cost", "Landed Cost", "€/Uhr", "min"),
    ("lieferzeit", "Lieferzeit (langsamste Komponente)", "Tage", "min"),
    ("servicegrad", "Servicegrad β", "%", "max"),
    ("co2", "CO₂e", "kg/Uhr", "min"),
    ("lagerwert", "Ø Lagerwert", "€", "min"),
]
KEYS = [c[0] for c in CRITERIA]


def run_once(cfg: Config, seed: int | None = None, rep: int = 0) -> RunResult:
    return SimulationEngine(cfg, seed=seed, rep=rep).run()


def run_replications(cfg: Config, n: int, seed: int | None = None) -> list[RunResult]:
    """n Replikationen; Replikation i nutzt Seed-Strom (seed, i) – in allen Szenarien identisch."""
    if not cfg.p("stochastic"):
        n = 1
    return [run_once(cfg, seed, i) for i in range(n)]


def summarize(results: list[RunResult]) -> pd.DataFrame:
    """Mittelwert, Standardabweichung und 95-%-Konfidenzintervall je Kriterium."""
    rows = []
    for key in KEYS + ["lagerhaltungskosten"]:
        x = np.array([r.kpis[key] for r in results], dtype=float)
        n = len(x)
        mean = float(np.nanmean(x))
        sd = float(np.nanstd(x, ddof=1)) if n > 1 else 0.0
        h = float(stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)) if n > 1 else 0.0
        rows.append(dict(kriterium=key, mean=mean, sd=sd, ci_low=mean - h, ci_high=mean + h, n=n))
    return pd.DataFrame(rows).set_index("kriterium")


def compare_scenarios(base: Config, reps: int = 30, seed: int | None = None,
                      scenarios: dict | None = None, param_overrides: dict | None = None):
    """Alle Szenarien auf demselben Modell. Liefert (Kennzahlentabelle, Rohergebnisse je Szenario)."""
    scenarios = scenarios or list_scenarios()
    raw, rows = {}, []
    for key, sc in scenarios.items():
        cfg = apply_scenario(base, sc, param_overrides=param_overrides)
        res = run_replications(cfg, reps, seed)
        raw[key] = res
        s = summarize(res)
        row = dict(szenario=cfg.scenario_name, key=key, n=int(s["n"].iloc[0]))
        for k in KEYS + ["lagerhaltungskosten"]:
            row[k] = s.loc[k, "mean"]
            row[k + "_ci"] = (s.loc[k, "ci_high"] - s.loc[k, "ci_low"]) / 2
        row["beta_ok"] = s.loc["servicegrad", "ci_low"] >= base.p("service_level_target")
        rows.append(row)
    return pd.DataFrame(rows), raw


def pareto_front(df: pd.DataFrame, feasible_col: str | None = None) -> pd.Series:
    """Nicht dominierte Varianten (Minimierung von Kosten, Lieferzeit, CO2e, Lagerwert).
    Varianten ohne eingehaltenen Servicegrad werden vorher ausgeschlossen."""
    cols = ["landed_cost", "lieferzeit", "co2", "lagerwert"]
    ok = df[feasible_col] if feasible_col else pd.Series(True, index=df.index)
    nd = pd.Series(False, index=df.index)
    cand = df[ok]
    for i, r in cand.iterrows():
        dominated = False
        for j, o in cand.iterrows():
            if i != j and all(o[c] <= r[c] for c in cols) and any(o[c] < r[c] for c in cols):
                dominated = True
                break
        nd[i] = not dominated
    return nd


def grid_search(base: Config, scenario: dict | None, reps: int = 5, seed: int | None = None,
                sb_grid=(0, 10, 20, 30, 45), air_grid=("off", "on_disruption"), q_grid=(0.5, 1.0, 2.0)):
    """Rastersuche über Sicherheitsbestand × Luftfracht-Politik × Bestellmengenfaktor
    im gewählten Szenario; markiert die Pareto-Front unter β >= Zielwert."""
    rows = []
    for sb, air, qf in itertools.product(sb_grid, air_grid, q_grid):
        cfg = apply_scenario(base, scenario, param_overrides=dict(
            safety_stock_days=sb, air_policy=air, order_q_factor=qf))
        res = run_replications(cfg, reps, seed)
        s = summarize(res)
        rows.append(dict(safety_stock_days=sb, air_policy=air, order_q_factor=qf,
                         **{k: s.loc[k, "mean"] for k in KEYS},
                         beta_low=s.loc["servicegrad", "ci_low"]))
    df = pd.DataFrame(rows)
    df["beta_ok"] = df["servicegrad"] >= base.p("service_level_target")
    df["pareto"] = pareto_front(df, "beta_ok")
    return df
