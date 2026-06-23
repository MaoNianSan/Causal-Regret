from __future__ import annotations

from pathlib import Path

from src.experiment_spec import FAST_BOOTSTRAP_REPLICATES, FULL_BOOTSTRAP_REPLICATES, PROJECT_ROOT, resolve_experiment_spec

INPUT_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

__all__ = [
    "FAST_BOOTSTRAP_REPLICATES",
    "FULL_BOOTSTRAP_REPLICATES",
    "INPUT_DIR",
    "OUTPUT_DIR",
    "Path",
    "resolve_experiment_spec",
]
