from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.delay import scenario_definitions

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
    project_id="exp1_controlled_identifiability_contextual",
    project_name="EXP1: Contextual source-binding identifiability simulation",
    scenarios=tuple(scenario_definitions().keys()),
    conditions=("labelled", "mixture_labelled", "unlabelled"),
    methods=("oracle", "naive", "naive_ewma", "delayed_ucb", "delayed_exp3", "sliding_window_W250", "anonymous_delayed", "causal_labeled", "causal_em", "causal_em_misspecified", "proxy"),
    estimand="Excess conditional risk relative to the decision-time context-information oracle.",
)
