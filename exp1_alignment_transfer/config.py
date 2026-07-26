from __future__ import annotations

"""Frozen configuration for Experiment 1: Controlled Alignment and Regret Transfer.

This module contains constants and immutable configuration objects only.  It
must not read outputs, perform calibration, or inspect evaluation results.
"""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any


EXPERIMENT_ID = "exp1_alignment_transfer"
CONFIG_VERSION = "1.1"


@dataclass(frozen=True)
class StructuralConfig:
    k_actions: int = 10
    horizon: int = 5000
    prehistory_length: int = 100
    state_burn_in: int = 500
    ar_coefficient: float = 0.98
    innovation_sd: float = 0.25
    context_noise_sd: float = 0.35
    tie_tolerance: float = 1e-12


@dataclass(frozen=True)
class DelayConfig:
    d_max: int = 100
    target_mean_delay: float = 15.0
    fixed_delay: int = 15
    state_coupling_beta: float = 1.0
    batch_aggregation: str = "uniform_mean"
    empty_clock_rule: str = "last_observation_carried_forward"


@dataclass(frozen=True)
class LearnerConfig:
    learner_id: str = "contextual_delayed_exp3"
    n_context_cells: int = 10
    exploration_gamma: float = 0.0
    learning_rate_eta: float = 0.0

    @staticmethod
    def from_dimensions(k_actions: int, n_context_cells: int, horizon: int) -> "LearnerConfig":
        import math

        nominal_cell_horizon = max(1, math.ceil(horizon / n_context_cells))
        gamma = min(
            1.0,
            math.sqrt(
                (k_actions * math.log(k_actions))
                / ((math.e - 1.0) * nominal_cell_horizon)
            ),
        )
        return LearnerConfig(
            n_context_cells=n_context_cells,
            exploration_gamma=float(gamma),
            learning_rate_eta=float(gamma / k_actions),
        )


@dataclass(frozen=True)
class RunConfig:
    evaluation_seeds: tuple[int, ...] = tuple(range(30))
    fast_seeds: tuple[int, ...] = (20000, 20001, 20002)
    calibration_seeds: tuple[int, ...] = tuple(range(10000, 10020))
    bootstrap_repetitions_full: int = 2000
    bootstrap_repetitions_fast: int = 200
    ci_level: float = 0.95


STRUCTURAL = StructuralConfig()
DELAY = DelayConfig()
RUN = RunConfig()
LEARNER = LearnerConfig.from_dimensions(
    k_actions=STRUCTURAL.k_actions,
    n_context_cells=STRUCTURAL.k_actions,
    horizon=STRUCTURAL.horizon,
)

FAST_STRUCTURAL = replace(STRUCTURAL, horizon=500)
FAST_LEARNER = LearnerConfig.from_dimensions(
    k_actions=FAST_STRUCTURAL.k_actions,
    n_context_cells=FAST_STRUCTURAL.k_actions,
    horizon=FAST_STRUCTURAL.horizon,
)

MECHANISM_ORDER = (
    "zero_delay",
    "exact_valid_shift",
    "geometric_delay",
    "mixture_delay",
    "state_coupled_delay",
    "systematic_misbinding",
)

DISPLAY_NAMES = {
    "zero_delay": "Zero delay",
    "exact_valid_shift": "Exact-valid shift",
    "geometric_delay": "Geometric delay",
    "mixture_delay": "Mixture delay",
    "state_coupled_delay": "State-coupled delay",
    "systematic_misbinding": "Systematic misbinding",
    "arrival_assigned": "Arrival-time assignment",
    "source_bound": "Source-bound assignment",
    "arrival_clock": "Arrival-clock binding",
    "source_round": "Source-round binding",
}


def canonical_payload(
    structural: StructuralConfig = STRUCTURAL,
    delay: DelayConfig = DELAY,
    learner: LearnerConfig = LEARNER,
    run: RunConfig = RUN,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "config_version": CONFIG_VERSION,
        "structural": asdict(structural),
        "delay": asdict(delay),
        "learner": asdict(learner),
        "run": asdict(run),
        "mechanism_order": list(MECHANISM_ORDER),
    }


def config_hash(
    structural: StructuralConfig = STRUCTURAL,
    delay: DelayConfig = DELAY,
    learner: LearnerConfig = LEARNER,
    run: RunConfig = RUN,
) -> str:
    raw = json.dumps(
        canonical_payload(structural, delay, learner, run),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
