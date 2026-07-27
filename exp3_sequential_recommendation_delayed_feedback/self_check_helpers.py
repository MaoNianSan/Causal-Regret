"""Reusable reconstruction helpers for the independent Exp3 self-check."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bootstrap_intervals import ROUTE_METRIC_BOUNDS, interval_audit
from bootstrap_summary import ROUTE_METRICS
from config import DEFAULT_CONFIG
from construct_delayed_targets import _target_one_user
from plot_appendix_results import _prepare_full_support_preflight
from route_diagnostics import summarize_route_selection
from utilities import read_frame, sha256_file


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(
    rows: list[dict[str, object]],
    check_id: str,
    passed: bool,
    detail: str,
    category: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def frames_equal(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> bool:
    left = left.sort_values(keys).reset_index(drop=True)
    right = right.sort_values(keys).reset_index(drop=True)
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        return False
    for column in left.columns:
        if left[column].dtype == object or right[column].dtype == object:
            if not left[column].astype(str).equals(right[column].astype(str)):
                return False
        elif not np.allclose(left[column].to_numpy(float), right[column].to_numpy(float), equal_nan=True):
            return False
    return True


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


def main_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    primary = pd.read_csv(output_dir / "tables" / "exp3_primary_route_results.csv")
    calibration = pd.read_csv(output_dir / "tables" / "exp3_decile_calibration.csv")
    figure = pd.read_csv(output_dir / "figures" / "data" / "exp3_main_score_gap_ranking_data.csv")
    distribution_columns = [
        "route_id", "full_sample_estimate", "resampling_median", "sensitivity_lower", "sensitivity_upper"
    ]
    gap = figure[figure["panel_id"] == "panel_b_gap"][distribution_columns]
    gap_expected = primary[[
        "route_id",
        "heldout_gap_defect",
        "heldout_gap_defect_resampling_median",
        "heldout_gap_defect_sensitivity_lower",
        "heldout_gap_defect_sensitivity_upper",
    ]].rename(columns={
        "heldout_gap_defect": "full_sample_estimate",
        "heldout_gap_defect_resampling_median": "resampling_median",
        "heldout_gap_defect_sensitivity_lower": "sensitivity_lower",
        "heldout_gap_defect_sensitivity_upper": "sensitivity_upper",
    })
    rank = figure[figure["panel_id"] == "panel_c_ranking"][distribution_columns]
    rank_expected = primary[[
        "route_id",
        "cross_fitted_ranking_shortfall",
        "cross_fitted_ranking_shortfall_resampling_median",
        "cross_fitted_ranking_shortfall_sensitivity_lower",
        "cross_fitted_ranking_shortfall_sensitivity_upper",
    ]].rename(columns={
        "cross_fitted_ranking_shortfall": "full_sample_estimate",
        "cross_fitted_ranking_shortfall_resampling_median": "resampling_median",
        "cross_fitted_ranking_shortfall_sensitivity_lower": "sensitivity_lower",
        "cross_fitted_ranking_shortfall_sensitivity_upper": "sensitivity_upper",
    })
    score_columns = ["route_id", "calibration_decile", "mean_predicted_target", "mean_observed_target"]
    score = figure[figure["panel_id"] == "panel_a_score"][score_columns]
    score_expected = calibration[calibration["route_id"].isin(["history_mean_control", "ridge_proxy"])][score_columns]
    passed = (
        frames_equal(gap, gap_expected, ["route_id"])
        and frames_equal(rank, rank_expected, ["route_id"])
        and frames_equal(score, score_expected, ["route_id", "calibration_decile"])
    )
    return passed, "main figure separates full-sample points from empirical resampling medians/ranges"

def full_preflight_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    action_path = output_dir / "derived" / "exp3_full_design_support_by_action.csv"
    figure_path = output_dir / "figures" / "data" / "exp3_appendix_full_design_support_preflight_data.csv"
    if not action_path.exists() or pd.read_csv(action_path).empty:
        return (not figure_path.exists()), "full-design support figure correctly omitted when preflight is not evaluable"
    expected_actions, expected_metrics = _prepare_full_support_preflight(
        pd.read_csv(action_path),
        pd.read_csv(output_dir / "tables" / "exp3_full_design_support_preflight.csv"),
        pd.read_csv(output_dir / "tables" / "exp3_action_space_coverage.csv"),
        pd.read_csv(output_dir / "design" / "exp3_full_design_action_vocabulary.csv"),
    )
    figure = pd.read_csv(figure_path)
    action_columns = [
        "action_id",
        "audit_unit_count",
        "supported_unit_rate",
        "minimum_fold_count_min",
        "minimum_fold_count_p10",
        "minimum_fold_count_median",
        "minimum_fold_count_p90",
        "minimum_fold_count_max",
        "action_display_name",
        "action_rank",
    ]
    metric_columns = ["metric_id", "display_name", "value"]
    actual_action_rows = figure[
        figure["panel_id"] == "panel_a_full_design_action_support"
    ].reset_index(drop=True)
    expected_action_rows = expected_actions.reset_index(drop=True)
    actual_actions = actual_action_rows[action_columns]
    actual_metrics = figure[figure["panel_id"] == "panel_b_full_design_readiness"][metric_columns]
    scientific_match = frames_equal(
        actual_actions, expected_actions[action_columns], ["action_rank"]
    ) and frames_equal(
        actual_metrics, expected_metrics[metric_columns], ["metric_id"]
    )
    provenance_match = True
    for column in ("run_id", "run_tier", "paper_result", "analysis_tier", "experiment_id", "config_hash", "input_manifest_hash"):
        if column in expected_actions.columns:
            provenance_match = provenance_match and actual_action_rows[column].astype(str).equals(
                expected_action_rows[column].astype(str)
            )
    provenance_match = bool(
        provenance_match
        and "figure_analysis_tier" in figure.columns
        and set(figure["figure_analysis_tier"].dropna().astype(str)) == {"appendix"}
    )
    passed = scientific_match and provenance_match
    return passed, "full-design figure scientific fields reconstruct and display provenance remains separate"


def arrival_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    figure = pd.read_csv(
        output_dir / "figures" / "data" / "exp3_appendix_arrival_carrier_diagnostic_data.csv"
    )
    expected = {
        "panel_a_carrier_lag": pd.read_csv(
            output_dir / "diagnostics" / "exp3_arrival_carrier_audit.csv"
        ),
        "panel_b_action_match": pd.read_csv(
            output_dir / "diagnostics" / "exp3_arrival_carrier_action_audit.csv"
        ),
    }
    for panel_id, source in expected.items():
        actual = figure[figure["panel_id"] == panel_id]
        columns = [column for column in source.columns if column in actual.columns]
        if not columns or not frames_equal(actual[columns], source[columns], columns[:1]):
            return False, f"arrival-carrier figure mismatch: {panel_id}"
    return True, "arrival-carrier figure scientific fields reconstruct from frozen diagnostics"


def dependence_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    figure = pd.read_csv(
        output_dir / "figures" / "data" / "exp3_appendix_dependence_and_selection_structure_data.csv"
    )
    expected = {
        "panel_a_outcome_reuse": pd.read_csv(
            output_dir / "derived" / "exp3_outcome_reuse_quantiles.csv"
        ),
        "panel_b_selection_instability": pd.read_csv(
            output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv"
        ),
    }
    for panel_id, source in expected.items():
        actual = figure[figure["panel_id"] == panel_id]
        columns = [column for column in source.columns if column in actual.columns]
        if not columns or not frames_equal(actual[columns], source[columns], columns[:1]):
            return False, f"dependence figure mismatch: {panel_id}"
    return True, "dependence and selection figure scientific fields reconstruct from frozen tables"


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


def figure_metadata_hashes_match(output_dir: Path) -> tuple[bool, str]:
    metadata_dir = output_dir / "figures" / "metadata"
    files = sorted(metadata_dir.glob("*.json"))
    if not files:
        return False, "no figure metadata files found"
    for path in files:
        metadata = load_json(path)
        hashes = metadata.get("source_file_hashes", {})
        for relative, expected in hashes.items():
            source = output_dir / relative
            if not source.exists() or sha256_file(source) != expected:
                return False, f"source hash mismatch: {relative}"
    return True, f"verified {len(files)} figure metadata bundles"


def bootstrap_interval_audit_matches(output_dir: Path) -> tuple[bool, str]:
    primary = pd.read_csv(output_dir / "derived" / "exp3_route_metrics_point.csv")
    draws = read_frame(output_dir / "derived" / "exp3_bootstrap_route_draws.parquet")
    audit = pd.read_csv(output_dir / "checks" / "exp3_resampling_sensitivity_audit.csv")
    route_audit = audit[audit["object_type"] == "route_metric"].copy()
    expected_rows: list[dict[str, object]] = []
    for point in primary.itertuples():
        route_draws = draws[draws["route_id"] == point.route_id]
        for metric in ROUTE_METRICS:
            expected = interval_audit(
                metric_id=metric,
                point_estimate=float(getattr(point, metric)),
                values=route_draws[metric].to_numpy(float),
                range_level=DEFAULT_CONFIG.resampling_range_level,
                bounds=ROUTE_METRIC_BOUNDS[metric],
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
