"""Module C control, parameter-recovery, and correspondence aggregation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from exp4.metrics.monte_carlo import mean_mcse


def aggregate_control_summary(replication_level: pd.DataFrame) -> pd.DataFrame:
    return (
        replication_level.groupby(
            ["control_id", "control_display_name", "analysis_tier", "correspondence_status"],
            sort=True,
        )
        .agg(
            raw_defect=("raw_defect", "mean"),
            oof_calibrated_defect=("oof_calibrated_defect", "mean"),
            recoverability=("recoverability", "mean"),
            negative_recoverability_rate=("negative_recoverability_indicator", "mean"),
            estimability_rate=("estimable", "mean"),
            minimum_training_support=("minimum_training_support", "min"),
            monte_carlo_replications=("replication_id", "nunique"),
        )
        .reset_index()
    )


def aggregate_parameter_recovery(parameter_level: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for (control_id, parameter), group in _parameter_long(parameter_level).groupby(
        ["control_id", "parameter"], sort=True
    ):
        finite = group[np.isfinite(group["estimate"])]
        true_values = finite["true_value"].dropna().unique()
        true_value = float(true_values[0]) if len(true_values) == 1 else np.nan
        estimates = finite["estimate"].to_numpy(dtype=float)
        records.append(
            {
                "control_id": control_id,
                "parameter": parameter,
                "true_value": true_value,
                "mean_estimate": float(np.mean(estimates)) if len(estimates) else np.nan,
                "bias": float(np.mean(estimates) - true_value) if len(estimates) and np.isfinite(true_value) else np.nan,
                "sd": float(np.std(estimates, ddof=1)) if len(estimates) > 1 else 0.0,
                "mcse": mean_mcse(estimates),
                "pair_sd": float(finite.groupby(["action_pair_low", "action_pair_high"])["estimate"].mean().std()),
                "fold_sd": float(finite.groupby("fold_id")["estimate"].mean().std()),
                "estimability_rate": float(np.mean(group["estimable"].astype(bool))),
            }
        )
    return pd.DataFrame.from_records(records)


def _parameter_long(parameter_level: pd.DataFrame) -> pd.DataFrame:
    intercept = parameter_level.rename(columns={"intercept": "estimate", "true_intercept": "true_value"}).copy()
    intercept["parameter"] = "intercept"
    slope = parameter_level.rename(columns={"slope": "estimate", "true_slope": "true_value"}).copy()
    slope["parameter"] = "slope"
    return pd.concat([intercept, slope], ignore_index=True, sort=False)


def aggregate_correspondence_checks(correspondence_level: pd.DataFrame) -> pd.DataFrame:
    summary = (
        correspondence_level.groupby("control_id", sort=True)
        .agg(
            pre_mean_abs_pearson=("pre_mean_abs_pearson", "mean"),
            post_mean_abs_pearson=("post_mean_abs_pearson", "mean"),
            pre_mean_abs_spearman=("pre_mean_abs_spearman", "mean"),
            post_mean_abs_spearman=("post_mean_abs_spearman", "mean"),
            mean_difference_in_pair_marginal_mean=("mean_difference_in_pair_marginal_mean", "mean"),
            mean_difference_in_pair_marginal_sd=("mean_difference_in_pair_marginal_sd", "mean"),
            permutation_hash_count=("permutation_hash", lambda values: values.dropna().nunique()),
        )
        .reset_index()
    )
    summary["status"] = np.where(
        summary["control_id"].eq("blocked_correspondence_destroyed"),
        np.where(
            summary["post_mean_abs_pearson"] < summary["pre_mean_abs_pearson"],
            "PASS",
            "FAIL",
        ),
        "NOT_APPLICABLE",
    )
    return summary
