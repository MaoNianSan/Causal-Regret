"""Module B bias, RMSE, MCSE, support, and selection aggregation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from exp4.metrics.monte_carlo import mean_mcse, rmse_mcse


def aggregate_audit_performance(condition_level: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    group_columns = ["audit_design_id", "audit_evidence_rate"]
    for keys, group in condition_level.groupby(group_columns, sort=True):
        errors = group["audit_estimation_error"].to_numpy(dtype=float)
        estimates = group["audited_action_gap_defect"].to_numpy(dtype=float)
        finite = np.isfinite(errors)
        errors = errors[finite]
        rmse = float(np.sqrt(np.mean(errors**2))) if len(errors) else np.nan
        rmse_error, rmse_method = rmse_mcse(errors)
        records.append(
            {
                "audit_design_id": keys[0],
                "audit_evidence_rate": keys[1],
                "bias": float(np.mean(errors)) if len(errors) else np.nan,
                "bias_mcse": mean_mcse(errors),
                "rmse": rmse,
                "rmse_mcse": rmse_error,
                "rmse_mcse_method": rmse_method,
                "sd": float(np.std(estimates[np.isfinite(estimates)], ddof=1)) if np.sum(np.isfinite(estimates)) > 1 else 0.0,
                "mae": float(np.mean(np.abs(errors))) if len(errors) else np.nan,
                "monte_carlo_replications": int(group["replication_id"].nunique()),
                "estimability_rate": float(np.mean(group["estimable"].astype(bool))),
            }
        )
    return pd.DataFrame.from_records(records)


def aggregate_weight_diagnostics(condition_level: pd.DataFrame) -> pd.DataFrame:
    value_columns = (
        "labelled_sample_size",
        "effective_sample_size",
        "effective_to_labelled_ratio",
        "effective_to_population_ratio",
        "weight_min",
        "weight_median",
        "weight_p95",
        "weight_max",
        "weight_cv",
        "lower_clip_fraction",
        "upper_clip_fraction",
        "minimum_inclusion_probability",
        "maximum_inclusion_probability",
    )
    return (
        condition_level.groupby(["audit_design_id", "audit_evidence_rate"], sort=True)[list(value_columns)]
        .mean()
        .add_prefix("mean_")
        .reset_index()
    )


def aggregate_selection_diagnostics(
    condition_level: pd.DataFrame, ambiguity_deciles: pd.DataFrame
) -> pd.DataFrame:
    summary = (
        condition_level.groupby(["audit_design_id", "audit_evidence_rate"], sort=True)
        .agg(
            mean_ambiguity_defect_correlation=("ambiguity_defect_correlation", "mean"),
            mean_included_defect=("included_mean_defect", "mean"),
            mean_excluded_defect=("excluded_mean_defect", "mean"),
            mean_selection_defect_difference=("selection_defect_difference", "mean"),
            mean_route_label_audit_mask_correlation=("route_label_audit_mask_correlation", "mean"),
        )
        .reset_index()
    )
    decile_summary = (
        ambiguity_deciles.groupby("ambiguity_decile", sort=True)
        .agg(
            mean_ambiguity=("mean_ambiguity", "mean"),
            mean_true_unit_defect=("mean_true_unit_defect", "mean"),
            monte_carlo_replications=("replication_id", "nunique"),
        )
        .reset_index()
    )
    decile_summary["audit_design_id"] = "ambiguity_decile_population"
    decile_summary["audit_evidence_rate"] = np.nan
    return pd.concat([summary, decile_summary], ignore_index=True, sort=False)
