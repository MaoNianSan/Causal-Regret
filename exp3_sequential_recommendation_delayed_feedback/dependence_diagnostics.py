"""Data-dependence and resampling-selection diagnostics for Exp3.

These outputs explain why ordinary bootstrap confidence-interval interpretations
are not claimed. They do not change the target, routes, support rule, or primary
point estimands.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from evaluation_artifacts import MetricResult
from utilities import save_frame, save_json


REUSE_QUANTILES = (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1.0)


def _engagement_value(frame: pd.DataFrame, cfg: ExperimentConfig) -> pd.Series:
    value = pd.Series(0.0, index=frame.index)
    for column, weight in (
        (cfg.long_view_col, cfg.future_value_weights["long_view"]),
        (cfg.like_col, cfg.future_value_weights["like"]),
        (cfg.comment_col, cfg.future_value_weights["comment"]),
        (cfg.forward_col, cfg.future_value_weights["forward"]),
        (cfg.follow_col, cfg.future_value_weights["follow"]),
    ):
        value = value + float(weight) * frame[column].astype(float)
    return value


def _split_structure(frame: pd.DataFrame, split_id: str, cfg: ExperimentConfig) -> tuple[dict[str, object], pd.DataFrame]:
    positive = _engagement_value(frame, cfg) > 0
    reuse = frame.loc[positive, "source_windows_per_outcome_event"].to_numpy(float)
    events_per_user = frame.groupby(cfg.user_col, observed=True).size().to_numpy(float)
    row = {
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
    quantiles = pd.DataFrame(
        {
            "split_id": split_id,
            "quantile": REUSE_QUANTILES,
            "source_windows_per_outcome_event": [
                float(np.quantile(reuse, q)) if reuse.size else 0.0 for q in REUSE_QUANTILES
            ],
        }
    )
    return row, quantiles


def write_data_dependence_diagnostics(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    history_row, history_quantiles = _split_structure(history, "history", cfg)
    evaluation_row, evaluation_quantiles = _split_structure(evaluation, "evaluation", cfg)
    structure = pd.DataFrame([history_row, evaluation_row])
    quantiles = pd.concat([history_quantiles, evaluation_quantiles], ignore_index=True)
    diagnostics = {
        "diagnostic_role": "dependence_structure_disclosure",
        "formal_ci_validated": False,
        "interpretation": (
            "Overlapping six-hour targets create strong within-user and adjacent-window dependence; "
            "source-event counts are not independent sample sizes."
        ),
        "splits": {row["split_id"]: row for row in (history_row, evaluation_row)},
    }
    save_frame(structure, output_dir / "tables" / "exp3_data_dependence_structure.csv")
    save_frame(quantiles, output_dir / "derived" / "exp3_outcome_reuse_quantiles.csv")
    save_json(diagnostics, output_dir / "diagnostics" / "exp3_data_dependence_structure.json")
    return structure, quantiles, diagnostics


def compare_replication_structure(
    point: MetricResult,
    replication: MetricResult,
    replication_id: int,
) -> pd.DataFrame:
    point_support = point.support_margins[["audit_unit_id", "action_id", "is_supported_action"]].rename(
        columns={"is_supported_action": "point_supported"}
    )
    draw_support = replication.support_margins[["audit_unit_id", "action_id", "is_supported_action"]].rename(
        columns={"is_supported_action": "draw_supported"}
    )
    support_merge = point_support.merge(draw_support, on=["audit_unit_id", "action_id"], how="outer")
    support_switch_rate = float(
        np.mean(support_merge["point_supported"].fillna(False).astype(bool) != support_merge["draw_supported"].fillna(False).astype(bool))
    ) if len(support_merge) else 0.0

    point_units = point.support_cells[["audit_unit_id", "is_valid_audit_unit"]].rename(
        columns={"is_valid_audit_unit": "point_valid"}
    )
    draw_units = replication.support_cells[["audit_unit_id", "is_valid_audit_unit"]].rename(
        columns={"is_valid_audit_unit": "draw_valid"}
    )
    unit_merge = point_units.merge(draw_units, on="audit_unit_id", how="outer")
    valid_unit_change_rate = float(
        np.mean(unit_merge["point_valid"].fillna(False).astype(bool) != unit_merge["draw_valid"].fillna(False).astype(bool))
    ) if len(unit_merge) else 0.0

    reference_keys = ["audit_unit_id", "selection_fold_id", "reference_action_id"]
    point_reference = point.audit_unit_metrics[reference_keys].drop_duplicates(
        ["audit_unit_id", "selection_fold_id"]
    ).rename(columns={"reference_action_id": "point_reference"})
    draw_reference = replication.audit_unit_metrics[reference_keys].drop_duplicates(
        ["audit_unit_id", "selection_fold_id"]
    ).rename(columns={"reference_action_id": "draw_reference"})
    reference_merge = point_reference.merge(
        draw_reference, on=["audit_unit_id", "selection_fold_id"], how="outer"
    )
    reference_switch_rate = float(
        np.mean(reference_merge["point_reference"].fillna("<missing>") != reference_merge["draw_reference"].fillna("<missing>"))
    ) if len(reference_merge) else 0.0

    rows: list[dict[str, object]] = []
    for route_id in sorted(point.audit_unit_metrics["route_id"].astype(str).unique()):
        keys = ["audit_unit_id", "selection_fold_id", "route_id"]
        point_route = point.audit_unit_metrics[point.audit_unit_metrics["route_id"] == route_id][
            [*keys, "route_selected_action_id", "valid_gap_pair_count"]
        ].rename(columns={"route_selected_action_id": "point_selected"})
        draw_route = replication.audit_unit_metrics[replication.audit_unit_metrics["route_id"] == route_id][
            [*keys, "route_selected_action_id", "valid_gap_pair_count"]
        ].rename(columns={"route_selected_action_id": "draw_selected"})
        merged = point_route.merge(draw_route, on=keys, how="outer", suffixes=("_point", "_draw"))
        selected_switch_rate = float(
            np.mean(merged["point_selected"].fillna("<missing>") != merged["draw_selected"].fillna("<missing>"))
        ) if len(merged) else 0.0
        rows.append(
            {
                "replication_id": int(replication_id),
                "route_id": route_id,
                "support_set_switch_rate": support_switch_rate,
                "valid_audit_unit_change_rate": valid_unit_change_rate,
                "reference_action_switch_rate": reference_switch_rate,
                "route_selected_action_switch_rate": selected_switch_rate,
                "mean_valid_gap_pairs_per_direction": float(draw_route["valid_gap_pair_count"].mean()) if len(draw_route) else np.nan,
                "valid_selection_direction_count": int(len(draw_route)),
            }
        )
    return pd.DataFrame(rows)


def summarize_resampling_structure(
    structure_draws: pd.DataFrame,
    point_result: MetricResult,
    output_dir: Path,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for route_id, draws in structure_draws.groupby("route_id", observed=True):
        point_route = point_result.audit_unit_metrics[
            point_result.audit_unit_metrics["route_id"].astype(str) == str(route_id)
        ]
        row: dict[str, object] = {
            "route_id": route_id,
            "point_mean_valid_gap_pairs_per_direction": float(point_route["valid_gap_pair_count"].mean()),
            "point_selection_direction_count": int(len(point_route)),
            "valid_resampling_count": int(draws["replication_id"].nunique()),
        }
        for metric in (
            "support_set_switch_rate",
            "valid_audit_unit_change_rate",
            "reference_action_switch_rate",
            "route_selected_action_switch_rate",
            "mean_valid_gap_pairs_per_direction",
        ):
            values = draws[metric].to_numpy(float)
            row[f"{metric}_mean"] = float(np.mean(values))
            row[f"{metric}_median"] = float(np.median(values))
            row[f"{metric}_p90"] = float(np.quantile(values, 0.90))
        rows.append(row)
    summary = pd.DataFrame(rows)
    save_frame(summary, output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv")
    save_json(
        {
            "diagnostic_role": "selection_instability_under_user_resampling",
            "formal_ci_validated": False,
            "route_count": int(len(summary)),
            "resampling_replication_count": int(structure_draws["replication_id"].nunique()) if len(structure_draws) else 0,
            "interpretation": (
                "Rates quantify how often user resampling changes support sets, valid units, held-out reference actions, "
                "or route-selected actions. They diagnose non-smooth selection behavior and do not alter the estimand."
            ),
        },
        output_dir / "diagnostics" / "exp3_resampling_structure_diagnostics.json",
    )
    return summary
