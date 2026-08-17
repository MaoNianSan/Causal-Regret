from __future__ import annotations

"""Deterministic stored-artifact replay for execution-contract migrations."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.runner import RunMetadata
from src.scientific_execution import (
    build_primary_bundle,
    resolve_run_spec,
    run_primary_bundle,
)


DEFAULT_REPLAY_SEEDS = (0, 1)
DEFAULT_REPLAY_MECHANISMS = (
    "zero_delay",
    "exact_valid_shift",
    "geometric_delay",
    "systematic_misbinding",
)


def _normalized(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _normalized(value.item())
    if isinstance(value, np.ndarray):
        return [_normalized(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        normalized = {
            str(key): _normalized(item) for key, item in sorted(value.items())
        }
        # Parquet stores heterogeneous dict columns as a union struct, adding
        # null fields that were absent from the original per-mechanism payload.
        return {
            key: item
            for key, item in normalized.items()
            if item is not None and item != "__NA__"
        }
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if np.isnan(value):
            return "__NAN__"
        if np.isfinite(value) and value.is_integer():
            return int(value)
        return value
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return "__NA__"
    except (TypeError, ValueError):
        pass
    return value


def _compare_frames(
    actual: pd.DataFrame,
    stored: pd.DataFrame,
    *,
    sort_by: tuple[str, ...] = (),
) -> dict[str, Any]:
    actual = actual.copy()
    stored = stored.copy()
    if sort_by:
        actual = actual.sort_values(list(sort_by), kind="stable")
        stored = stored.sort_values(list(sort_by), kind="stable")
    actual = actual.reset_index(drop=True)
    stored = stored.reset_index(drop=True)
    missing = [column for column in stored.columns if column not in actual.columns]
    extra = [column for column in actual.columns if column not in stored.columns]
    mismatches: list[str] = []
    max_abs_error = 0.0
    if len(actual) != len(stored):
        mismatches.append("__row_count__")
    for column in stored.columns:
        if column not in actual.columns:
            continue
        left = actual[column]
        right = stored[column]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            left_values = left.to_numpy(dtype=float)
            right_values = right.to_numpy(dtype=float)
            if left_values.shape != right_values.shape:
                mismatches.append(column)
                continue
            finite = np.isfinite(left_values) & np.isfinite(right_values)
            if np.any(finite):
                max_abs_error = max(
                    max_abs_error,
                    float(np.max(np.abs(left_values[finite] - right_values[finite]))),
                )
            if not np.allclose(
                left_values,
                right_values,
                rtol=1e-12,
                atol=1e-12,
                equal_nan=True,
            ):
                mismatches.append(column)
        else:
            left_values = [
                json.dumps(_normalized(value), sort_keys=True, separators=(",", ":"))
                for value in left.tolist()
            ]
            right_values = [
                json.dumps(_normalized(value), sort_keys=True, separators=(",", ":"))
                for value in right.tolist()
            ]
            if left_values != right_values:
                mismatches.append(column)
    passed = not missing and not extra and not mismatches
    return {
        "status": "PASS" if passed else "FAIL",
        "rows": len(stored),
        "missing_columns": missing,
        "extra_columns": extra,
        "mismatched_columns": mismatches,
        "max_abs_error": max_abs_error,
        "tolerance": {"rtol": 1e-12, "atol": 1e-12},
    }


def replay_scientific_execution_contract(
    run_dir: Path,
    frozen_calibration: dict[str, Any],
    *,
    seeds: tuple[int, ...] = DEFAULT_REPLAY_SEEDS,
    mechanisms: tuple[str, ...] = DEFAULT_REPLAY_MECHANISMS,
) -> dict[str, Any]:
    """Recompute a fixed primary subset and compare it with stored raw outputs."""
    run_dir = run_dir.resolve()
    spec = resolve_run_spec("full", frozen_calibration)
    if any(seed not in spec.seeds for seed in seeds):
        raise ValueError("Replay seeds must be members of the frozen full seed set")
    if any(mechanism not in spec.mechanisms for mechanism in mechanisms):
        raise ValueError("Replay mechanisms must be members of MECHANISM_ORDER")
    filters = [
        ("seed", "in", list(seeds)),
        ("mechanism_id", "in", list(mechanisms)),
    ]
    stored_frames = {
        "path_manifest": pd.read_parquet(
            run_dir / "raw" / "exp1_path_manifest.parquet", filters=filters
        ),
        "delay_round": pd.read_parquet(
            run_dir / "raw" / "exp1_delay_source_rounds.parquet", filters=filters
        ),
        "route_round": pd.read_parquet(
            run_dir / "raw" / "exp1_route_diagnostic_rounds.parquet", filters=filters
        ),
        "route_seed": pd.read_parquet(
            run_dir / "seed_metrics" / "exp1_route_seed_metrics.parquet",
            filters=filters,
        ),
        "learner_round": pd.read_parquet(
            run_dir / "raw" / "exp1_learner_consequence_rounds.parquet",
            filters=filters,
        ),
        "learner_seed": pd.read_parquet(
            run_dir / "seed_metrics" / "exp1_learner_seed_metrics.parquet",
            filters=filters,
        ),
    }
    comparisons: list[dict[str, Any]] = []
    sort_keys = {
        "path_manifest": (),
        "delay_round": ("source_round",),
        "route_round": ("route_id", "t"),
        "route_seed": ("route_id",),
        "learner_round": ("feedback_binding_id", "t"),
        "learner_seed": ("feedback_binding_id",),
    }
    for seed in seeds:
        for mechanism_id in mechanisms:
            selector = (
                (stored_frames["path_manifest"].seed.astype(int) == int(seed))
                & (stored_frames["path_manifest"].mechanism_id == mechanism_id)
            )
            stored_path = stored_frames["path_manifest"].loc[selector].copy()
            if len(stored_path) != 1:
                comparisons.append(
                    {
                        "seed": int(seed),
                        "mechanism_id": mechanism_id,
                        "status": "FAIL",
                        "failure_reason": f"stored path rows={len(stored_path)}",
                    }
                )
                continue
            row = stored_path.iloc[0]
            metadata = RunMetadata(
                run_id=str(row.run_id),
                run_tier=str(row.run_tier),
                paper_result=bool(row.paper_result),
                analysis_tier=str(row.analysis_tier),
                configuration_id=str(row.configuration_id),
                code_commit=str(row.code_commit),
                config_hash=str(row.config_hash),
                input_manifest_hash=str(row.input_manifest_hash),
                calibration_manifest_hash=str(row.calibration_manifest_hash),
                generated_at=str(row.generated_at),
            )
            bundle = build_primary_bundle(
                spec, frozen_calibration, int(seed), mechanism_id
            )
            replayed = run_primary_bundle(bundle, metadata, spec, frozen_calibration)
            actual_frames = {
                "path_manifest": pd.DataFrame([replayed.path_manifest_row]),
                "delay_round": replayed.delay_round,
                "route_round": replayed.route_round,
                "route_seed": replayed.route_seed,
                "learner_round": replayed.learner_round,
                "learner_seed": replayed.learner_seed,
            }
            component_results: dict[str, Any] = {}
            for component, actual in actual_frames.items():
                stored = stored_frames[component]
                stored = stored[
                    (stored.seed.astype(int) == int(seed))
                    & (stored.mechanism_id == mechanism_id)
                ].copy()
                component_results[component] = _compare_frames(
                    actual, stored, sort_by=sort_keys[component]
                )
            passed = all(
                result["status"] == "PASS" for result in component_results.values()
            )
            comparisons.append(
                {
                    "seed": int(seed),
                    "mechanism_id": mechanism_id,
                    "structural_path_hash": bundle.structural_path.path_hash,
                    "delay_path_hash": bundle.delay_path.delay_path_hash,
                    "bundle_hash": bundle.bundle_hash,
                    "components": component_results,
                    "status": "PASS" if passed else "FAIL",
                }
            )
    passed = len(comparisons) == len(seeds) * len(mechanisms) and all(
        comparison.get("status") == "PASS" for comparison in comparisons
    )
    return {
        "replay_type": "TARGETED_DETERMINISTIC_STORED_ARTIFACT_REPLAY",
        "run_dir": str(run_dir),
        "run_tier": "full",
        "replay_seeds": list(seeds),
        "replay_mechanisms": list(mechanisms),
        "comparisons": comparisons,
        "scientific_equivalence": "PASS" if passed else "FAIL",
        "scientific_full_rerun_executed": False,
    }


__all__ = [
    "DEFAULT_REPLAY_MECHANISMS",
    "DEFAULT_REPLAY_SEEDS",
    "replay_scientific_execution_contract",
]
