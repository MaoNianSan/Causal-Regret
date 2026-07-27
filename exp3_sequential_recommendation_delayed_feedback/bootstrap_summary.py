"""Summaries and sensitivity diagnostics for completed Exp3 user resampling."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bootstrap_intervals import MetricBounds, ROUTE_METRIC_BOUNDS, interval_audit
from config import ExperimentConfig
from dependence_diagnostics import summarize_resampling_structure
from evaluation_artifacts import MetricResult
from utilities import save_frame, save_json


ROUTE_METRICS = (
    "score_spearman_correlation",
    "score_calibration_mae",
    "heldout_gap_defect",
    "gap_sign_agreement",
    "gap_reversal_rate",
    "cross_fitted_ranking_shortfall",
    "top_action_match_rate",
)


def support_status(support: pd.DataFrame, cfg: ExperimentConfig) -> str:
    row = support.iloc[0]
    values = [float(row.action_coverage), float(row.pair_coverage), float(row.audit_unit_coverage)]
    if any(value < cfg.support_limited_threshold for value in values):
        return "STOP_AND_REVIEW"
    if any(value < cfg.history_support_pass_threshold for value in values):
        return "PASS_WITH_LIMITED_SUPPORT"
    return "PASS"


def _audit(metric: str, point: float, values: np.ndarray, cfg: ExperimentConfig, bounds: MetricBounds) -> dict[str, object]:
    return interval_audit(
        metric_id=metric,
        point_estimate=point,
        values=values,
        range_level=cfg.resampling_range_level,
        bounds=bounds,
    )


def _route_summaries(
    route_draws: pd.DataFrame,
    point_result: MetricResult,
    repetitions: int,
    valid_count: int,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    summary_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for route_id, point in point_result.route_metrics.set_index("route_id").iterrows():
        row: dict[str, object] = {
            "route_id": route_id,
            "route_display_name": point["route_display_name"],
            "route_role": point["route_role"],
            "is_deployable": bool(point["is_deployable"]),
            "uses_future_outcome": bool(point["uses_future_outcome"]),
            "uses_source_identity": bool(point.get("uses_source_identity", False)),
            "valid_resampling_count": valid_count,
            "resampling_repetition_count": repetitions,
            "resampling_range_level": cfg.resampling_range_level,
            "resampling_range_method": cfg.resampling_range_method,
            "uncertainty_role": cfg.resampling_output_role,
            "formal_ci_validated": cfg.formal_ci_validated,
            "resampling_unit": "user_cluster",
        }
        draws = route_draws[route_draws["route_id"] == route_id]
        for metric in ROUTE_METRICS:
            audit = _audit(
                metric,
                float(point[metric]),
                draws[metric].to_numpy(float),
                cfg,
                ROUTE_METRIC_BOUNDS[metric],
            )
            audit.update({"object_type": "route_metric", "object_id": route_id})
            audit_rows.append(audit)
            row[metric] = float(point[metric])
            row[f"{metric}_resampling_median"] = audit["resampling_median"]
            row[f"{metric}_sensitivity_lower"] = audit["sensitivity_lower"]
            row[f"{metric}_sensitivity_upper"] = audit["sensitivity_upper"]
        row["valid_gap_pair_count"] = int(point["valid_gap_pair_count"])
        row["near_tie_pair_count"] = int(point["near_tie_pair_count"])
        row["valid_audit_unit_count"] = int(point["valid_audit_unit_count"])
        summary_rows.append(row)
    return pd.DataFrame(summary_rows), audit_rows


def _paired_summary(
    route_draws: pd.DataFrame,
    point_result: MetricResult,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, dict[str, object]]:
    pivot = route_draws.pivot(
        index="replication_id",
        columns="route_id",
        values="cross_fitted_ranking_shortfall",
    )
    paired_values = (
        pivot["history_mean_control"] - pivot["ridge_proxy"]
        if {"history_mean_control", "ridge_proxy"}.issubset(pivot.columns)
        else pd.Series(dtype=float)
    )
    point_pivot = point_result.route_metrics.set_index("route_id")["cross_fitted_ranking_shortfall"]
    paired_point = float(point_pivot["history_mean_control"] - point_pivot["ridge_proxy"])
    audit = _audit(
        "ranking_improvement_vs_history",
        paired_point,
        paired_values.to_numpy(float),
        cfg,
        MetricBounds(),
    )
    audit.update({"object_type": "paired_contrast", "object_id": "ridge_proxy_vs_history_mean_control"})
    paired = pd.DataFrame(
        [
            {
                "contrast_id": "ridge_proxy_vs_history_mean_control",
                "metric_id": "ranking_improvement_vs_history",
                "point_estimate": paired_point,
                "resampling_median": audit["resampling_median"],
                "sensitivity_lower": audit["sensitivity_lower"],
                "sensitivity_upper": audit["sensitivity_upper"],
                "resampling_range_method": cfg.resampling_range_method,
                "uncertainty_role": cfg.resampling_output_role,
                "formal_ci_validated": cfg.formal_ci_validated,
                "positive_favors": "ridge_proxy",
                "valid_resampling_count": int(paired_values.notna().sum()),
            }
        ]
    )
    return paired, audit


def _decile_summary(
    decile_draws: pd.DataFrame,
    point_result: MetricResult,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    for point in point_result.decile_calibration.itertuples():
        draws = decile_draws[
            (decile_draws["route_id"] == point.route_id)
            & (decile_draws["calibration_decile"] == point.calibration_decile)
        ]
        audit = _audit(
            "mean_observed_target",
            float(point.mean_observed_target),
            draws["mean_observed_target"].to_numpy(float),
            cfg,
            MetricBounds(0.0, None),
        )
        object_id = f"{point.route_id}__decile_{int(point.calibration_decile):02d}"
        audit.update({"object_type": "calibration_decile", "object_id": object_id})
        audits.append(audit)
        rows.append(
            {
                "route_id": point.route_id,
                "calibration_decile": int(point.calibration_decile),
                "mean_predicted_target": float(point.mean_predicted_target),
                "mean_observed_target": float(point.mean_observed_target),
                "mean_observed_target_resampling_median": audit["resampling_median"],
                "mean_observed_target_sensitivity_lower": audit["sensitivity_lower"],
                "mean_observed_target_sensitivity_upper": audit["sensitivity_upper"],
                "resampling_range_method": cfg.resampling_range_method,
                "uncertainty_role": cfg.resampling_output_role,
                "formal_ci_validated": cfg.formal_ci_validated,
                "valid_action_cell_count": int(point.valid_action_cell_count),
                "valid_resampling_count": int(len(draws)),
            }
        )
    return pd.DataFrame(rows), audits


def _support_summary(
    support_draws: pd.DataFrame,
    point_result: MetricResult,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]], str]:
    point = point_result.support_metrics.iloc[0].to_dict()
    status = support_status(point_result.support_metrics, cfg)
    summary = pd.DataFrame(
        [
            {
                **point,
                "scientific_support_status": status,
                "resampling_range_method": cfg.resampling_range_method,
                "uncertainty_role": cfg.resampling_output_role,
                "formal_ci_validated": cfg.formal_ci_validated,
            }
        ]
    )
    audits: list[dict[str, object]] = []
    for column in ("action_coverage", "pair_coverage", "audit_unit_coverage"):
        audit = _audit(
            column,
            float(point[column]),
            support_draws[column].to_numpy(float),
            cfg,
            MetricBounds(0.0, 1.0),
        )
        audit.update({"object_type": "support_metric", "object_id": "evaluation_support"})
        audits.append(audit)
        summary[f"{column}_resampling_median"] = audit["resampling_median"]
        summary[f"{column}_sensitivity_lower"] = audit["sensitivity_lower"]
        summary[f"{column}_sensitivity_upper"] = audit["sensitivity_upper"]
    return summary, audits, status


def summarize_bootstrap(
    *,
    route_draws: pd.DataFrame,
    decile_draws: pd.DataFrame,
    support_draws: pd.DataFrame,
    structure_draws: pd.DataFrame,
    point_result: MetricResult,
    output_dir: Path,
    repetitions: int,
    valid_count: int,
    invalid_count: int,
    invalid_records: list[dict[str, object]],
    n_jobs: int,
    resumed: bool,
    cfg: ExperimentConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    summary, audits = _route_summaries(route_draws, point_result, repetitions, valid_count, cfg)
    paired, paired_audit = _paired_summary(route_draws, point_result, cfg)
    decile_summary, decile_audits = _decile_summary(decile_draws, point_result, cfg)
    support_summary, support_audits, status = _support_summary(support_draws, point_result, cfg)
    structure_summary = summarize_resampling_structure(structure_draws, point_result, output_dir)
    audit_table = pd.DataFrame([*audits, paired_audit, *decile_audits, *support_audits])
    max_bias = float(audit_table["absolute_bias_over_sd"].max(skipna=True)) if not audit_table.empty else np.nan
    warning_count = int((audit_table["absolute_bias_over_sd"] > cfg.bootstrap_bias_sd_warning_threshold).sum())
    centering_status = "PASS_WITH_WARNING" if warning_count else "PASS"
    valid_fraction = valid_count / repetitions if repetitions else 0.0
    diagnostics = {
        "requested_resampling_repetitions": repetitions,
        "valid_resampling_repetitions": valid_count,
        "invalid_resampling_repetitions": invalid_count,
        "valid_bootstrap_repetitions": valid_count,
        "invalid_bootstrap_repetitions": invalid_count,
        "valid_bootstrap_fraction": valid_fraction,
        "valid_bootstrap_fraction_gate": cfg.valid_bootstrap_fraction_gate,
        "bootstrap_reconstructs_support": True,
        "bootstrap_reconstructs_reference_action": True,
        "bootstrap_reconstructs_pair_set": True,
        "bootstrap_retrains_proxy_model": False,
        "bootstrap_parallel_jobs": n_jobs,
        "replication_seed_rule": "SeedSequence([bootstrap_seed, replication_id])",
        "resume_supported": True,
        "resumed_from_partial_draws": bool(resumed),
        "scientific_support_status": status,
        "uncertainty_interface_status": "SENSITIVITY_ONLY_ACCEPTED",
        "resampling_output_role": cfg.resampling_output_role,
        "displayed_range_method": cfg.resampling_range_method,
        "resampling_range_level": cfg.resampling_range_level,
        "formal_ci_validated": cfg.formal_ci_validated,
        "legacy_basic_interval_retained_for_audit": True,
        "resampling_centering_status": centering_status,
        "bootstrap_centering_status": centering_status,
        "bootstrap_bias_sd_warning_threshold": cfg.bootstrap_bias_sd_warning_threshold,
        "bootstrap_bias_warning_count": warning_count,
        "maximum_absolute_bootstrap_bias_over_sd": max_bias,
        "point_outside_sensitivity_range_count": int((~audit_table["point_inside_sensitivity_range"]).sum()),
        "point_outside_legacy_basic_audit_count": int((~audit_table["point_inside_legacy_basic_audit"]).sum()),
        "selection_structure_diagnostic_rows": int(len(structure_summary)),
        "invalid_replications": invalid_records[:20],
    }

    save_frame(summary, output_dir / "tables" / "exp3_primary_route_results.csv")
    save_frame(paired, output_dir / "tables" / "exp3_paired_ranking_contrast.csv")
    save_frame(decile_summary, output_dir / "tables" / "exp3_decile_calibration.csv")
    save_frame(support_summary, output_dir / "tables" / "exp3_support_coverage.csv")
    save_frame(audit_table, output_dir / "checks" / "exp3_resampling_sensitivity_audit.csv")
    # Compatibility copy for local scripts that still look for the old audit filename.
    save_frame(audit_table, output_dir / "checks" / "exp3_bootstrap_interval_audit.csv")
    save_json(diagnostics, output_dir / "checks" / "exp3_bootstrap_diagnostics.json")
    return summary, paired, decile_summary, diagnostics
