"""Stammdaten (CSV) und Szenarien (YAML) laden.

Kennzeichen: KI (Referenz) | nachprogrammieren: Leon
"""
import copy
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def lade_stammdaten() -> dict:
    """Alle CSV-Dateien aus data/ als Tabellen, Index = ID."""
    d = ROOT / "data"
    return {
        "lieferanten": pd.read_csv(d / "lieferanten.csv").set_index("lieferant_id", drop=False),
        "tier2": pd.read_csv(d / "tier2.csv").set_index("tier2_id", drop=False),
        "knoten": pd.read_csv(d / "knoten.csv").set_index("knoten_id", drop=False),
        "kanten": pd.read_csv(d / "kanten.csv", keep_default_na=False).set_index("kante_id", drop=False),
    }


def szenario_liste() -> list[str]:
    return sorted(p.stem for p in (ROOT / "config" / "szenarien").glob("*.yaml"))


def lade_szenario(key: str) -> dict:
    """base.yaml + Szenario-Datei. Störungen ohne Zeitangabe gelten ab Tag 0 das ganze Jahr."""
    cfg = _yaml(ROOT / "config" / "base.yaml")
    cfg.update(_yaml(ROOT / "config" / "szenarien" / f"{key}.yaml"))
    cfg.setdefault("stoerungen", [])
    for s in cfg["stoerungen"]:
        s.setdefault("start_tag", 0)
        s.setdefault("dauer_tage", cfg["tage"])
    cfg["key"] = key
    return copy.deepcopy(cfg)


def _yaml(pfad: Path) -> dict:
    with open(pfad, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
