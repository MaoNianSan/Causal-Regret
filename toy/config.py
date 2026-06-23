"""Compatibility helpers for the self-contained Toy experiment."""
from __future__ import annotations

from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FAST_SEEDS = (0, 1, 2)
FULL_SEEDS = tuple(range(30))


def resolve_experiment_spec(mode: str) -> dict:
    config_path = PROJECT_ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    seeds = list(config["seeds"][:3]) if mode == "fast" else list(config["seeds"])
    return {**config, "run_mode": mode, "seeds": seeds, "save_raw_trajectories": mode == "fast"}


__all__ = ["FAST_SEEDS", "FULL_SEEDS", "INPUT_DIR", "OUTPUT_DIR", "PROJECT_ROOT", "Path", "resolve_experiment_spec"]
