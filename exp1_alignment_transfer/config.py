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
CONFIG_VERSION = "1.2"
STAGE_CONFIG_HASH_ALGORITHM_VERSION = "exp1-stage-config-v1"


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
    def from_dimensions(
        k_actions: int, n_context_cells: int, horizon: int
    ) -> "LearnerConfig":
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


@dataclass(frozen=True)
class TheorySweepConfig:
    """Frozen theorem-targeted sweep configuration (v1.2).

    These are theorem-targeted diagnostics, NOT new delay mechanisms. They
    must never be added to MECHANISM_ORDER. Values are fixed ex ante and
    MUST NOT be changed after viewing results:

    - exact_shift_scales test action-invariant offset magnitude;
    - margin_distortion_ratios directly bracket the theorem threshold
      delta/mu = 1 (strict inequality at 1 is required).
    """

    exact_shift_scales = (
        0.00,
        0.05,
        0.10,
        0.20,
    )

    margin_distortion_ratios = (
        0.00,
        0.25,
        0.50,
        0.75,
        0.90,
        0.99,
        1.00,
        1.01,
        1.10,
        1.25,
        1.50,
        2.00,
    )


STRUCTURAL = StructuralConfig()
DELAY = DelayConfig()
RUN = RunConfig()
THEORY_SWEEP = TheorySweepConfig()
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
    "exact_valid_shift": "Exact-cardinal-valid shift",
    "geometric_delay": "Geometric delay",
    "mixture_delay": "Mixture delay",
    "state_coupled_delay": "State-coupled delay",
    "systematic_misbinding": "Systematic misbinding",
    "arrival_assigned": "Arrival-time assignment",
    "source_bound": "Source-bound assignment",
    "arrival_clock": "Arrival-clock binding",
    "source_round": "Source-round binding",
}


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def scientific_generation_config_payload(
    run_tier: str = "full",
    *,
    structural: StructuralConfig | None = None,
    delay: DelayConfig = DELAY,
    learner: LearnerConfig | None = None,
    run: RunConfig = RUN,
    mechanism_order: tuple[str, ...] = MECHANISM_ORDER,
) -> dict[str, Any]:
    """Configuration capable of changing primary raw or seed-level outputs."""
    if run_tier not in {"fast", "full"}:
        raise ValueError("run_tier must be 'fast' or 'full'")
    selected_structural = structural or (
        FAST_STRUCTURAL if run_tier == "fast" else STRUCTURAL
    )
    selected_learner = learner or (FAST_LEARNER if run_tier == "fast" else LEARNER)
    selected_seeds = run.fast_seeds if run_tier == "fast" else run.evaluation_seeds
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "scientific_generation",
        "run_tier": run_tier,
        "structural": asdict(selected_structural),
        "delay": asdict(delay),
        "learner": asdict(selected_learner),
        "execution": {
            "seeds": list(selected_seeds),
            "mechanism_order": list(mechanism_order),
        },
    }


def scientific_generation_config_hash(
    run_tier: str = "full", **kwargs: Any
) -> str:
    return _payload_hash(scientific_generation_config_payload(run_tier, **kwargs))


def calibration_config_payload(
    *,
    structural: StructuralConfig = STRUCTURAL,
    delay: DelayConfig = DELAY,
    run: RunConfig = RUN,
) -> dict[str, Any]:
    """Only configuration consumed by the frozen calibration procedure."""
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "calibration",
        "structural": asdict(structural),
        "delay": asdict(delay),
        "calibration_seeds": list(run.calibration_seeds),
        "evaluation_seeds_for_overlap_gate": list(run.evaluation_seeds),
    }


def calibration_config_hash(**kwargs: Any) -> str:
    return _payload_hash(calibration_config_payload(**kwargs))


def aggregation_config_payload(
    run_tier: str = "full", *, run: RunConfig = RUN
) -> dict[str, Any]:
    if run_tier not in {"fast", "full"}:
        raise ValueError("run_tier must be 'fast' or 'full'")
    repetitions = (
        run.bootstrap_repetitions_fast
        if run_tier == "fast"
        else run.bootstrap_repetitions_full
    )
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "aggregation",
        "run_tier": run_tier,
        "bootstrap_repetitions": repetitions,
        "ci_level": run.ci_level,
    }


def aggregation_config_hash(run_tier: str = "full", **kwargs: Any) -> str:
    return _payload_hash(aggregation_config_payload(run_tier, **kwargs))


def validation_config_payload(
    *, theory_sweep: TheorySweepConfig = THEORY_SWEEP
) -> dict[str, Any]:
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "validation",
        "exact_shift_scales": list(theory_sweep.exact_shift_scales),
        "margin_distortion_ratios": list(theory_sweep.margin_distortion_ratios),
    }


def validation_config_hash(**kwargs: Any) -> str:
    return _payload_hash(validation_config_payload(**kwargs))


def reporting_config_payload(
    *, display_names: dict[str, str] = DISPLAY_NAMES
) -> dict[str, Any]:
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "reporting",
        "display_names": dict(display_names),
    }


def reporting_config_hash(**kwargs: Any) -> str:
    return _payload_hash(reporting_config_payload(**kwargs))


def stage_config_hashes(
    run_tier: str = "full",
    *,
    structural: StructuralConfig | None = None,
    learner: LearnerConfig | None = None,
) -> dict[str, str]:
    return {
        "scientific_generation_config_hash": scientific_generation_config_hash(
            run_tier, structural=structural, learner=learner
        ),
        "calibration_config_hash": calibration_config_hash(),
        "aggregation_config_hash": aggregation_config_hash(run_tier),
        "validation_config_hash": validation_config_hash(),
        "reporting_config_hash": reporting_config_hash(),
    }


def canonical_payload(
    structural: StructuralConfig = STRUCTURAL,
    delay: DelayConfig = DELAY,
    learner: LearnerConfig = LEARNER,
    run: RunConfig = RUN,
    theory_sweep: TheorySweepConfig = THEORY_SWEEP,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "config_version": CONFIG_VERSION,
        "structural": asdict(structural),
        "delay": asdict(delay),
        "learner": asdict(learner),
        "run": asdict(run),
        "theory_sweep": asdict(theory_sweep),
        "mechanism_order": list(MECHANISM_ORDER),
    }


def config_hash(
    structural: StructuralConfig = STRUCTURAL,
    delay: DelayConfig = DELAY,
    learner: LearnerConfig = LEARNER,
    run: RunConfig = RUN,
    theory_sweep: TheorySweepConfig = THEORY_SWEEP,
) -> str:
    raw = json.dumps(
        canonical_payload(structural, delay, learner, run, theory_sweep),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
