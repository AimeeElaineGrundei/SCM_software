"""Stammdaten (CSV) und Konfiguration (YAML) laden.

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"


def lade_stammdaten() -> dict[str, pd.DataFrame]:
    return {
        "lieferanten": pd.read_csv(DATA / "lieferanten.csv").set_index("lieferant_id", drop=False),
        "knoten": pd.read_csv(DATA / "knoten.csv").set_index("knoten_id", drop=False),
        "kanten": pd.read_csv(DATA / "kanten.csv", keep_default_na=False).set_index("kante_id", drop=False),
    }


def _yaml(pfad: Path) -> dict:
    with open(pfad, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def szenario_liste() -> list[str]:
    return sorted(p.stem for p in (CONFIG / "szenarien").glob("*.yaml"))


def lade_szenario(key: str) -> dict:
    """Basis + Szenario zusammenführen (Szenario überschreibt)."""
    cfg = _yaml(CONFIG / "base.yaml")
    sz = _yaml(CONFIG / "szenarien" / f"{key}.yaml")
    for k, v in sz.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    cfg["key"] = key
    cfg.setdefault("name", key)
    cfg.setdefault("stoerungen", [])
    cfg.setdefault("nachfrage_faktor", 1.0)
    return cfg
