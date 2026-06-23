"""Lightweight experiment metadata retained for compatibility with importers."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAST_SEEDS = (0, 1, 2)
FULL_SEEDS = tuple(range(30))

BASE_SPEC = {
    "project_id": "toy",
    "project_name": "Toy delayed-feedback diagnostic",
    "scenarios": ("zero", "geometric", "piecewise", "mixture"),
    "methods": ("oracle", "naive", "causal_labelled"),
}


def resolve_experiment_spec(mode: str) -> dict:
    from config import resolve_experiment_spec as _resolve
    return _resolve(mode)


def normalized_design_hash(mode: str) -> str:
    payload = json.dumps(resolve_experiment_spec(mode), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
