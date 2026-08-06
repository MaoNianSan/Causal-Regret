"""Reusable reconstruction helpers for the independent Exp3 self-check."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bootstrap_intervals import interval_audit, metric_bounds
from bootstrap_metric_registry import CANONICAL_ROUTE_METRICS, ROUTE_METRICS
from config import DEFAULT_CONFIG
from construct_delayed_targets import _target_one_user
from route_diagnostics import summarize_route_selection
from self_check_common import add_check, frames_equal, load_json
from self_check_figure_helpers import (
    arrival_figure_data_matches,
    dependence_figure_data_matches,
    figure_metadata_hashes_match,
    full_preflight_figure_data_matches,
)
from self_check_redesign import (
    main_figure_data_matches,
    ridge_selection_contract_matches,
    target_component_audit_matches,
    two_fold_contract_matches,
)
from utilities import read_frame


def target_contract_matches(frame: pd.DataFrame, split_end_ms: int) -> tuple[bool, str]:
    cfg = DEFAULT_CONFIG
    checked = 0
    for _, group in frame.groupby(cfg.user_col, sort=False):
        actual = group.sort_values(cfg.time_col, kind="stable").reset_index(drop=True)
        expected = _target_one_user(group, split_end_ms, cfg).reset_index(drop=True)
        same = (
            np.array_equal(actual["is_target_eligible"].to_numpy(bool), expected["is_target_eligible"].to_numpy(bool))
            and np.allclose(
                actual["future_engagement_value_6h"].to_numpy(float),
                expected["future_engagement_value_6h"].to_numpy(float),
                equal_nan=True,
            )
            and np.array_equal(
                actual["source_windows_per_outcome_event"].to_numpy(int),
                expected["source_windows_per_outcome_event"].to_numpy(int),
            )
        )
        if not same:
            return False, f"first mismatch after {checked} source events"
        checked += len(actual)
    return True, f"verified_events={checked}; window=[t,t+6h)"


def target_reuse_summary_matches(output_dir: Path) -> tuple[bool, str]:
    actual = pd.read_csv(output_dir / "tables" / "exp3_target_reuse_audit.csv")
    expected_rows: list[dict[str, object]] = []
    cfg = DEFAULT_CONFIG
    for split_id in ("history", "evaluation"):
        frame = read_frame(output_dir / "processed" / f"exp3_{split_id}_events_with_targets.parquet")
        engagement = sum(
            float(weight) * frame[column].astype(float)
            for column, weight in (
                (cfg.long_view_col, cfg.future_value_weights["long_view"]),
                (cfg.like_col, cfg.future_value_weights["like"]),
                (cfg.comment_col, cfg.future_value_weights["comment"]),
                (cfg.forward_col, cfg.future_value_weights["forward"]),
                (cfg.follow_col, cfg.future_value_weights["follow"]),
            )
        )
        reuse = frame.loc[engagement > 0, "source_windows_per_outcome_event"].to_numpy(float)
        events_per_user = frame.groupby(cfg.user_col, observed=True).size().to_numpy(float)
        expected_rows.append(
            {
                "split_id": split_id,
                "unique_user_count": int(frame[cfg.user_col].nunique()),
                "source_event_count": int(len(frame)),
                "eligible_source_event_count": int(frame["is_target_eligible"].sum()),
                "positive_outcome_event_count": int(reuse.size),
                "right_censoring_rate": float(1.0 - frame["is_target_eligible"].mean()),
                "outcome_event_reuse_rate": float(np.mean(reuse > 1)) if reuse.size else 0.0,
                "mean_source_windows_per_outcome_event": float(np.mean(reuse)) if reuse.size else 0.0,
                "median_source_windows_per_outcome_event": float(np.median(reuse)) if reuse.size else 0.0,
                "p90_source_windows_per_outcome_event": float(np.quantile(reuse, 0.90)) if reuse.size else 0.0,
                "maximum_source_windows_per_outcome_event": float(np.max(reuse)) if reuse.size else 0.0,
                "mean_source_events_per_user": float(np.mean(events_per_user)) if events_per_user.size else 0.0,
                "p90_source_events_per_user": float(np.quantile(events_per_user, 0.90)) if events_per_user.size else 0.0,
            }
        )
    columns = list(expected_rows[0])
    passed = frames_equal(actual[columns], pd.DataFrame(expected_rows), ["split_id"])
    return passed, "data-dependence table reconstructs user counts, target reuse, and events-per-user summaries"


def dependence_structure_matches(output_dir: Path) -> tuple[bool, str]:
    structure = pd.read_csv(output_dir / "tables" / "exp3_data_dependence_structure.csv")
    reuse_table = pd.read_csv(output_dir / "tables" / "exp3_target_reuse_audit.csv")
    common = [column for column in structure.columns if column in reuse_table.columns]
    structure_ok = frames_equal(structure[common], reuse_table[common], ["split_id"])
    quantiles = pd.read_csv(output_dir / "derived" / "exp3_outcome_reuse_quantiles.csv")
    quantile_ok = (
        set(quantiles["split_id"].astype(str)) == {"history", "evaluation"}
        and quantiles["quantile"].between(0, 1).all()
        and (quantiles["source_windows_per_outcome_event"] >= 0).all()
    )
    selection = pd.read_csv(output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv")
    rate_columns = [column for column in selection.columns if column.endswith("_rate_mean") or column.endswith("_rate_median") or column.endswith("_rate_p90")]
    selection_ok = bool(rate_columns) and selection[rate_columns].apply(lambda col: col.between(0, 1).all()).all()
    return bool(structure_ok and quantile_ok and selection_ok), "dependence quantiles and resampling selection-switch diagnostics are bounded and disclosed"

def boundary_quarantine_summary_matches(output_dir: Path) -> tuple[bool, str]:
    split = load_json(output_dir / "design" / "exp3_split_manifest.json")
    actual = pd.read_csv(output_dir / "tables" / "exp3_boundary_quarantine_audit.csv")
    expected = pd.DataFrame(
        [
            {
                "split_id": "history",
                "excluded_event_count": split.get("history_events_excluded_before_start", 0),
                "excluded_event_fraction": split.get("history_prestart_fraction", 0.0),
                "frozen_tolerance": split.get("max_prestart_history_fraction"),
                "tolerance_source": "run_config.max_prestart_history_fraction",
            },
            {
                "split_id": "evaluation",
                "excluded_event_count": split.get("evaluation_events_excluded_before_boundary", 0),
                "excluded_event_fraction": split.get("evaluation_preboundary_fraction", 0.0),
                "frozen_tolerance": split.get("max_preboundary_evaluation_fraction"),
                "tolerance_source": "run_config.max_preboundary_evaluation_fraction",
            },
        ]
    )
    columns = list(expected.columns)
    passed = frames_equal(actual[columns], expected, ["split_id"])
    retained = actual["retained_strict_event_time_nonoverlap"].astype(str).str.lower().isin({"true", "1"})
    passed = bool(
        passed
        and actual["timezone_rule"].astype(str).eq(str(split.get("timezone_rule"))).all()
        and actual["boundary_policy"].astype(str).eq(str(split.get("boundary_policy"))).all()
        and retained.all()
    )
    return passed, "boundary quarantine table reconstructs counts, fractions, policy, and frozen tolerances"


def bootstrap_interval_audit_matches(output_dir: Path) -> tuple[bool, str]:
    primary = pd.read_csv(output_dir / "derived" / "exp3_route_metrics_point.csv")
    draws = read_frame(output_dir / "derived" / "exp3_bootstrap_route_draws.parquet")
    audit = pd.read_csv(output_dir / "checks" / "exp3_resampling_sensitivity_audit.csv")
    route_audit = audit[audit["object_type"] == "route_metric"].copy()
    metrics = (
        CANONICAL_ROUTE_METRICS
        if set(CANONICAL_ROUTE_METRICS).issubset(primary.columns)
        and set(CANONICAL_ROUTE_METRICS).issubset(draws.columns)
        else ROUTE_METRICS
    )
    expected_rows: list[dict[str, object]] = []
    for point in primary.itertuples():
        route_draws = draws[draws["route_id"] == point.route_id]
        for metric in metrics:
            expected = interval_audit(
                metric_id=metric,
                point_estimate=float(getattr(point, metric)),
                values=route_draws[metric].to_numpy(float),
                range_level=DEFAULT_CONFIG.resampling_range_level,
                bounds=metric_bounds(metric),
            )
            expected.update({"object_type": "route_metric", "object_id": point.route_id})
            expected_rows.append(expected)
    expected = pd.DataFrame(expected_rows)[route_audit.columns]
    passed = frames_equal(route_audit, expected, ["object_id", "metric_id"])
    return passed, "route resampling bias, percentile sensitivity ranges, and legacy basic audit reconstruct exactly"

def route_selection_diagnostics_match(output_dir: Path) -> tuple[bool, str]:
    units = read_frame(output_dir / "derived" / "exp3_audit_unit_metrics.parquet")
    expected_summary, expected_contrast = summarize_route_selection(units)
    actual_summary = pd.read_csv(output_dir / "diagnostics" / "exp3_route_selection_diagnostics.csv")
    actual_contrast = load_json(output_dir / "diagnostics" / "exp3_ridge_history_selection_overlap.json")
    summary_ok = frames_equal(actual_summary[expected_summary.columns], expected_summary, ["route_id"])
    contrast_ok = all(
        (
            np.isclose(float(actual_contrast[key]), float(value))
            if isinstance(value, float) and np.isfinite(value)
            else actual_contrast.get(key) == value
        )
        for key, value in expected_contrast.items()
    )
    return summary_ok and contrast_ok, "route selection diversity and Ridge–History overlap reconstruct exactly"
