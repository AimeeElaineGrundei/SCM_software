"""Kommandozeile: reproduzierbare Läufe ohne Oberfläche.

  python -m scm.cli check                     # Mindestanforderungen prüfen
  python -m scm.cli run S1_suez --seed 42     # Einzellauf, Kennzahlen
  python -m scm.cli report --reps 30          # alle Szenarien × 30 Replikationen -> outputs/
  python -m scm.cli pareto S1_suez --reps 5   # Rastersuche, Pareto-Front -> outputs/
"""
from __future__ import annotations
import argparse
import os
import pandas as pd

from .config import load_base, list_scenarios, apply_scenario, check_requirements, ROOT
from .runner import run_once, compare_scenarios, grid_search, CRITERIA
from . import viz

OUT = os.path.join(ROOT, "outputs")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run"); r.add_argument("scenario"); r.add_argument("--seed", type=int, default=42)
    r.add_argument("--deterministic", action="store_true")
    rp = sub.add_parser("report"); rp.add_argument("--reps", type=int, default=30); rp.add_argument("--seed", type=int, default=42)
    pa = sub.add_parser("pareto"); pa.add_argument("scenario"); pa.add_argument("--reps", type=int, default=5)
    pa.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    base, scen = load_base(), list_scenarios()
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)

    if a.cmd == "check":
        for ok, t in check_requirements(base, len(scen), len(CRITERIA)):
            print("OK " if ok else "FEHLT", t)
    elif a.cmd == "run":
        cfg = apply_scenario(base, scen[a.scenario], param_overrides=dict(stochastic=not a.deterministic, seed=a.seed))
        res = run_once(cfg, a.seed, 0)
        print(cfg.scenario_name); print(viz.kpi_table(res).to_string(index=False))
    elif a.cmd == "report":
        tab, _ = compare_scenarios(base, a.reps, a.seed)
        tab.to_csv(os.path.join(OUT, "szenariovergleich.csv"), index=False, encoding="utf-8-sig")
        t = viz.scenario_table(tab, base.p("service_level_target"))
        t.to_csv(os.path.join(OUT, "szenariovergleich_formatiert.csv"), index=False, encoding="utf-8-sig")
        print(t.to_string(index=False)); print(f"\n-> {OUT}")
    elif a.cmd == "pareto":
        g = grid_search(base, scen[a.scenario], reps=a.reps, seed=a.seed)
        g.to_csv(os.path.join(OUT, f"pareto_{a.scenario}.csv"), index=False, encoding="utf-8-sig")
        print(g[g.pareto].round(3).to_string(index=False)); print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
