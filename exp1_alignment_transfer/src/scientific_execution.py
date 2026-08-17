from __future__ import annotations

"""Authoritative scientific execution contract for primary Exp1 observations."""

from dataclasses import dataclass, replace
from typing import Any, Iterator

import numpy as np
import pandas as pd

from config import (
    DELAY,
    EXPERIMENT_ID,
    FAST_LEARNER,
    FAST_STRUCTURAL,
    LEARNER,
    MECHANISM_ORDER,
    RUN,
    STRUCTURAL,
    LearnerConfig,
    StructuralConfig,
    config_hash,
)
from src.contracts import LEARNER_ROUND_COLUMNS, ROUTE_ROUND_COLUMNS
from src.path_generator import SharedPathBundle, build_shared_path_bundle
from src.runner import RunMetadata, run_paired_learner_consequence, run_route_map_diagnostic


@dataclass(frozen=True)
class ScientificRunSpec:
    run_tier: str
    structural_config: StructuralConfig
    learner_config: LearnerConfig
    seeds: tuple[int, ...]
    mechanisms: tuple[str, ...]
    bootstrap_repetitions: int
    ci_level: float
    effective_config_hash: str


@dataclass(frozen=True)
class ScientificBundleResult:
    path_manifest_row: dict[str, Any]
    delay_round: pd.DataFrame
    route_round: pd.DataFrame
    route_seed: pd.DataFrame
    learner_round: pd.DataFrame
    learner_seed: pd.DataFrame


def resolve_run_spec(
    run_tier: str, frozen_calibration: dict[str, Any]
) -> ScientificRunSpec:
    """Resolve every ex-ante choice that controls primary observation generation."""
    if run_tier not in {"fast", "full"}:
        raise ValueError("run_tier must be 'fast' or 'full'")
    selected = frozen_calibration["structural"]["selected_value"]
    base_structural = FAST_STRUCTURAL if run_tier == "fast" else STRUCTURAL
    structural_config = replace(
        base_structural,
        ar_coefficient=float(selected["ar_coefficient"]),
        innovation_sd=float(selected["innovation_sd"]),
    )
    learner_config = FAST_LEARNER if run_tier == "fast" else LEARNER
    seeds = tuple(RUN.fast_seeds if run_tier == "fast" else RUN.evaluation_seeds)
    repetitions = (
        RUN.bootstrap_repetitions_fast
        if run_tier == "fast"
        else RUN.bootstrap_repetitions_full
    )
    return ScientificRunSpec(
        run_tier=run_tier,
        structural_config=structural_config,
        learner_config=learner_config,
        seeds=seeds,
        mechanisms=tuple(MECHANISM_ORDER),
        bootstrap_repetitions=repetitions,
        ci_level=RUN.ci_level,
        effective_config_hash=config_hash(
            structural=structural_config, learner=learner_config
        ),
    )


def build_primary_bundle(
    spec: ScientificRunSpec,
    frozen_calibration: dict[str, Any],
    seed: int,
    mechanism_id: str,
) -> SharedPathBundle:
    if int(seed) not in spec.seeds:
        raise ValueError(f"seed {seed} is outside the resolved {spec.run_tier} contract")
    if mechanism_id not in spec.mechanisms:
        raise ValueError(f"mechanism {mechanism_id!r} is outside the primary contract")
    return build_shared_path_bundle(
        seed=int(seed),
        mechanism_id=mechanism_id,
        frozen_calibration=frozen_calibration,
        structural_config=spec.structural_config,
        delay_config=DELAY,
    )


def iter_primary_bundles(
    spec: ScientificRunSpec, frozen_calibration: dict[str, Any]
) -> Iterator[SharedPathBundle]:
    """Yield the complete seed-by-mechanism matrix without result filtering."""
    for seed in spec.seeds:
        for mechanism_id in spec.mechanisms:
            yield build_primary_bundle(spec, frozen_calibration, seed, mechanism_id)


def _path_manifest_row(
    bundle: SharedPathBundle, metadata: RunMetadata, structural_config: StructuralConfig
) -> dict[str, Any]:
    delay = bundle.delay_path.delays
    arrivals = bundle.delay_path.arrival_clocks
    eval_mask = bundle.delay_path.source_rounds >= 0
    eval_delays = delay[eval_mask]
    eval_arrivals = arrivals[eval_mask]
    observed = eval_arrivals < structural_config.horizon
    terminal_unobserved = int(np.sum(~observed))
    all_arrivals = arrivals[(arrivals >= 0) & (arrivals < structural_config.horizon)]
    batch_counts = np.bincount(
        all_arrivals.astype(int), minlength=structural_config.horizon
    )
    losses = bundle.structural_path.structural_loss_matrix
    return {
        "run_id": metadata.run_id,
        "run_tier": metadata.run_tier,
        "paper_result": metadata.paper_result,
        "analysis_tier": metadata.analysis_tier,
        "experiment_id": EXPERIMENT_ID,
        "configuration_id": metadata.configuration_id,
        "seed": bundle.seed,
        "mechanism_id": bundle.mechanism_id,
        "structural_family_id": bundle.structural_path.structural_family_id,
        "horizon": structural_config.horizon,
        "prehistory_length": structural_config.prehistory_length,
        "state_burn_in": structural_config.state_burn_in,
        "k_actions": structural_config.k_actions,
        "d_max": DELAY.d_max,
        "structural_path_id": bundle.structural_path.path_id,
        "structural_path_hash": bundle.structural_path.path_hash,
        "delay_path_id": bundle.delay_path.delay_path_id,
        "delay_path_hash": bundle.delay_path.delay_path_hash,
        "learner_uniform_tape_id": bundle.learner_uniform_tape_id,
        "learner_uniform_tape_hash": bundle.learner_uniform_tape_hash,
        "bundle_id": bundle.bundle_id,
        "bundle_hash": bundle.bundle_hash,
        "generated_mean_delay": float(np.mean(eval_delays)),
        "observed_mean_delay": (
            float(np.mean(eval_delays[observed])) if np.any(observed) else float("nan")
        ),
        "right_censoring_rate": float(np.mean(~observed)),
        "empty_arrival_clock_rate": float(np.mean(batch_counts == 0)),
        "multiarrival_clock_rate": float(np.mean(batch_counts > 1)),
        "max_arrival_batch_size": int(np.max(batch_counts)),
        "structural_loss_min": float(np.min(losses)),
        "structural_loss_max": float(np.max(losses)),
        "loss_clipping_count": 0,
        "learner_prehistory_policy": "cold_start_empty_queue",
        "delay_sd": float(np.std(delay)),
        "delay_q50": float(np.quantile(delay, 0.50)),
        "delay_q90": float(np.quantile(delay, 0.90)),
        "delay_q99": float(np.quantile(delay, 0.99)),
        "terminal_unobserved_source_events": terminal_unobserved,
        "arrival_batch_aggregation": DELAY.batch_aggregation,
        "empty_arrival_rule": DELAY.empty_clock_rule,
        "delay_parameter_payload": bundle.delay_path.delay_parameter_payload,
        "structural_parameter_payload": bundle.structural_path.parameter_payload,
        "code_commit": metadata.code_commit,
        "config_hash": metadata.config_hash,
        "input_manifest_hash": metadata.input_manifest_hash,
        "calibration_manifest_hash": metadata.calibration_manifest_hash,
        "generated_at": metadata.generated_at,
    }


def _delay_source_rounds(
    bundle: SharedPathBundle, metadata: RunMetadata
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_id": metadata.run_id,
            "run_tier": metadata.run_tier,
            "paper_result": metadata.paper_result,
            "analysis_tier": metadata.analysis_tier,
            "experiment_id": EXPERIMENT_ID,
            "configuration_id": metadata.configuration_id,
            "seed": bundle.seed,
            "mechanism_id": bundle.mechanism_id,
            "source_round": bundle.delay_path.source_rounds,
            "delay": bundle.delay_path.delays,
            "arrival_clock": bundle.delay_path.arrival_clocks,
            "structural_state": bundle.structural_path.structural_state,
            "is_evaluation_source": bundle.delay_path.source_rounds >= 0,
            "structural_path_hash": bundle.structural_path.path_hash,
            "delay_path_hash": bundle.delay_path.delay_path_hash,
            "code_commit": metadata.code_commit,
            "config_hash": metadata.config_hash,
            "input_manifest_hash": metadata.input_manifest_hash,
            "calibration_manifest_hash": metadata.calibration_manifest_hash,
            "generated_at": metadata.generated_at,
        }
    )


def run_primary_bundle(
    bundle: SharedPathBundle,
    metadata: RunMetadata,
    spec: ScientificRunSpec,
    frozen_calibration: dict[str, Any],
) -> ScientificBundleResult:
    """Execute every raw scientific output for one predeclared primary bundle."""
    route_round, route_seed = run_route_map_diagnostic(bundle, metadata)
    learner_round, learner_seed = run_paired_learner_consequence(
        bundle,
        metadata,
        learner_config=spec.learner_config,
        context_partition=frozen_calibration["context"],
    )
    missing_route = [
        column for column in ROUTE_ROUND_COLUMNS if column not in route_round.columns
    ]
    missing_learner = [
        column for column in LEARNER_ROUND_COLUMNS if column not in learner_round.columns
    ]
    if missing_route or missing_learner:
        raise RuntimeError(
            f"Schema construction failed: route missing={missing_route}, "
            f"learner missing={missing_learner}"
        )
    return ScientificBundleResult(
        path_manifest_row=_path_manifest_row(
            bundle, metadata, spec.structural_config
        ),
        delay_round=_delay_source_rounds(bundle, metadata),
        route_round=route_round,
        route_seed=route_seed,
        learner_round=learner_round,
        learner_seed=learner_seed,
    )


__all__ = [
    "ScientificBundleResult",
    "ScientificRunSpec",
    "build_primary_bundle",
    "iter_primary_bundles",
    "resolve_run_spec",
    "run_primary_bundle",
]
