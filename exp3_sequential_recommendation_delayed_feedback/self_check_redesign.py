"""Independent reconstruction checks introduced by the Exp3 redesign."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import load_audit_design
from config import DEFAULT_CONFIG
from evaluation_aggregation import aggregate_user_arrays
from evaluation_artifacts import load_evaluation_arrays
from gap_metrics import direction_gap_metrics
from plot_scope_note import build_scope_note
from target_audit import audit_target_components
from utilities import deterministic_tie_argmax, read_frame


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _frames_equal(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> bool:
    left = left.sort_values(keys).reset_index(drop=True)
    right = right.sort_values(keys).reset_index(drop=True)
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        return False
    for column in left.columns:
        if left[column].dtype == object or right[column].dtype == object:
            if not left[column].astype(str).equals(right[column].astype(str)):
                return False
        elif not np.allclose(
            left[column].to_numpy(float), right[column].to_numpy(float), equal_nan=True
        ):
            return False
    return True


def main_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    primary = pd.read_csv(output_dir / "tables" / "exp3_primary_route_results.csv")
    paired = pd.read_csv(output_dir / "tables" / "exp3_paired_ranking_contrast.csv")
    figure = pd.read_csv(
        output_dir / "figures" / "data" / "exp3_main_score_gap_ranking_data.csv"
    )
    metrics = (
        "pooled_supported_cell_spearman",
        "pooled_supported_cell_mae",
        "maximum_heldout_reference_pair_gap_error",
        "heldout_reference_pair_sign_agreement",
        "top_action_agreement_with_fold_reference",
    )
    expected_rows = []
    for row in primary.itertuples():
        for metric in metrics:
            expected_rows.append(
                {
                    "route_id": row.route_id,
                    "metric_id": metric,
                    "full_sample_estimate": getattr(row, metric),
                    "resampling_median": getattr(row, f"{metric}_resampling_median"),
                    "sensitivity_lower": getattr(row, f"{metric}_sensitivity_lower"),
                    "sensitivity_upper": getattr(row, f"{metric}_sensitivity_upper"),
                }
            )
    columns = [
        "route_id",
        "metric_id",
        "full_sample_estimate",
        "resampling_median",
        "sensitivity_lower",
        "sensitivity_upper",
    ]
    actual = figure[figure["route_id"].notna()][columns]
    route_ok = _frames_equal(
        actual, pd.DataFrame(expected_rows)[columns], ["route_id", "metric_id"]
    )
    paired_row = figure[
        figure["metric_id"] == "ridge_over_historical_paired_value_gain"
    ].iloc[0]
    paired_expected = paired.iloc[0]
    paired_ok = all(
        np.isclose(float(paired_row[column]), float(paired_expected[column]))
        for column in (
            "full_sample_estimate",
            "resampling_median",
            "sensitivity_lower",
            "sensitivity_upper",
        )
    )
    support = pd.read_csv(output_dir / "tables" / "exp3_support_coverage.csv").iloc[0]
    coverage = pd.read_csv(output_dir / "tables" / "exp3_action_space_coverage.csv")
    scope = figure[figure["panel_id"] == "figure_scope_summary"].iloc[0]["scope_note"]
    scope_ok = str(scope) == build_scope_note(support, coverage)
    return bool(route_ok and paired_ok and scope_ok), "canonical main-figure metrics and dynamic scope reconstruct"


def ridge_selection_contract_matches(output_dir: Path) -> tuple[bool, str]:
    selection = _load_json(output_dir / "metadata" / "exp3_ridge_selection_manifest.json")
    model = _load_json(output_dir / "metadata" / "exp3_model_manifest.json")
    cv = pd.read_csv(output_dir / "tables" / "exp3_ridge_history_cv.csv")
    strict = pd.to_datetime(cv["train_end"]) < pd.to_datetime(cv["validation_date"])
    aggregate = cv[["alpha", "macro_supported_cell_mae_mean"]].drop_duplicates("alpha")
    best = float(aggregate["macro_supported_cell_mae_mean"].min())
    eligible = aggregate[
        aggregate["macro_supported_cell_mae_mean"]
        <= best + float(selection["tie_tolerance"])
    ]
    expected = float(eligible["alpha"].max())
    selected = float(selection["selected_alpha"])
    passed = bool(
        selection.get("selection_scope") == "history_only"
        and selection.get("evaluation_data_used") is False
        and cv["evaluation_data_used"].astype(str).str.lower().isin({"false", "0"}).all()
        and strict.all()
        and np.isclose(selected, expected)
        and np.isclose(float(model["selected_alpha"]), selected)
        and model.get("selected_alpha_is_run_artifact") is True
    )
    return passed, f"selected_alpha={selected}; origins={selection.get('origin_count')}"


def target_component_audit_matches(output_dir: Path) -> tuple[bool, str]:
    actual = pd.read_csv(output_dir / "tables" / "exp3_target_component_audit.csv")
    expected = []
    for split_id in ("history", "evaluation"):
        frame = read_frame(
            output_dir / "processed" / f"exp3_{split_id}_events_with_targets.parquet"
        )
        expected.append(audit_target_components(frame, split_id, DEFAULT_CONFIG))
    expected_frame = pd.concat(expected, ignore_index=True, sort=False)
    columns = list(expected_frame.columns)
    keys = ["split_id", "record_type", "component_id", "statistic"]
    object_columns = [column for column in columns if expected_frame[column].dtype == object]
    actual_compare = actual[columns].copy()
    expected_compare = expected_frame.copy()
    actual_compare[object_columns] = actual_compare[object_columns].fillna("")
    expected_compare[object_columns] = expected_compare[object_columns].fillna("")
    return _frames_equal(actual_compare, expected_compare, keys), "target component audit reconstructs"


def two_fold_contract_matches(output_dir: Path) -> tuple[bool, str]:
    arrays = load_evaluation_arrays(output_dir)
    design = load_audit_design(output_dir)
    units = read_frame(output_dir / "derived" / "exp3_audit_unit_metrics.parquet")
    source_sum, source_count, arrival_sum, arrival_count = aggregate_user_arrays(
        arrays,
        np.ones(len(arrays.user_ids), dtype=float),
        design.user_group_count,
        DEFAULT_CONFIG.reference_fold_count,
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        observed = source_sum / source_count
    arrival = np.empty_like(arrival_sum)
    for group_id in range(design.user_group_count):
        prior = arrays.history_scores[group_id]
        arrival[:, group_id] = (
            arrival_sum[:, group_id] + DEFAULT_CONFIG.history_prior_count * prior[None, None, :]
        ) / (arrival_count[:, group_id] + DEFAULT_CONFIG.history_prior_count)
    routes = {
        "arrival_carrier": arrival,
        "history_mean_control": np.repeat(
            arrays.fixed_route_scores["history_mean_control"][:, :, None, :], 2, axis=2
        ),
        "ridge_proxy": np.repeat(
            arrays.fixed_route_scores["ridge_proxy"][:, :, None, :], 2, axis=2
        ),
    }
    day_index = {day: index for index, day in enumerate(arrays.calendar_days)}
    for checked, row in enumerate(units.itertuples(), start=1):
        d, g = day_index[str(row.calendar_day)], int(row.user_group_id)
        selection_fold = int(row.selection_fold_id)
        evaluation_fold = int(row.evaluation_fold_id)
        supported = np.flatnonzero(
            np.all(source_count[d, g] >= design.support_min_events_per_fold, axis=0)
        )
        reference = deterministic_tie_argmax(observed[d, g, selection_fold], supported)
        selection_scores = routes[str(row.route_id)][d, g, selection_fold]
        route_action = deterministic_tie_argmax(selection_scores, supported)
        heldout = observed[d, g, evaluation_fold]
        gap, _, _, _ = direction_gap_metrics(
            selection_scores[reference] - selection_scores[supported],
            heldout[reference] - heldout[supported],
            supported,
            reference,
            design.near_tie_threshold,
        )
        matches = (
            str(row.reference_action_id) == arrays.candidate_actions[reference]
            and str(row.route_selected_action_id) == arrays.candidate_actions[route_action]
            and np.isclose(
                float(row.maximum_heldout_reference_pair_gap_error),
                float(gap["maximum_heldout_reference_pair_gap_error"]),
                equal_nan=True,
            )
            and np.isclose(
                float(row.signed_cross_fitted_reference_minus_route_value_difference),
                float(heldout[reference] - heldout[route_action]),
                equal_nan=True,
            )
        )
        if not matches:
            return False, f"two-fold mismatch at {row.audit_unit_id}; route={row.route_id}"
    return True, f"verified_fold_directions={len(units)}"
