from __future__ import annotations

"""Compatibility project specification for the current EXP1 contract.

The authoritative output and manuscript mappings live in
:mod:`src.experiment_contract`.  This module is retained for lightweight
third-party inspection scripts that import a project specification.
"""

from dataclasses import dataclass
from pathlib import Path

from src.delay import scenario_definitions
from src.experiment_contract import EXPERIMENT_ID

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProjectSpec:
    project_id: str
    project_name: str
    scenarios: tuple[str, ...]
    conditions: tuple[str, ...]
    methods: tuple[str, ...]
    estimand: str


BASE_SPEC = ProjectSpec(
    project_id=EXPERIMENT_ID,
    project_name="EXP1: Controlled source-binding validity simulation",
    scenarios=tuple(scenario_definitions().keys()),
    conditions=("labelled", "mixture_labelled", "unlabelled"),
    methods=(
        "oracle", "naive", "naive_ewma", "delayed_ucb", "delayed_exp3",
        "sliding_window_W250", "anonymous_delayed", "causal_labeled",
        "causal_em", "causal_em_misspecified", "proxy",
    ),
    estimand="Context-information-oracle excess conditional risk under delayed feedback.",
)
