"""Aggregation and uncertainty quantification for Exp4 derived outputs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

import config


MODULE_A_METRICS = [
    "population_raw_action_gap_defect",
    "ranking_reversal_rate",
    "margin_preservation_rate",
    "structural_regret_per_round",
    "absolute_loss_map_error_appendix",
]


def _quantile_interval(values: np.ndarray) -> tuple[float, float]:
    alpha = (1.0 - config.PARAMETERS.confidence_level) / 2.0
    return float(np.quantile(values, alpha)), float(np.quantile(values, 1.0 - alpha))


def _bootstrap_indices(
    sample_size: int, bootstrap_replications: int, seed: int
) -> np.ndarray:
    if bootstrap_replications <= 0:
        return np.empty((0, sample_size), dtype=np.int64)
    generator = np.random.default_rng(np.random.SeedSequence(seed))
    return generator.integers(
        0, sample_size, size=(bootstrap_replications, sample_size), endpoint=False
    )


def summarize_route_boundary(
    seed_level: pd.DataFrame,
    bootstrap_replications: int,
) -> pd.DataFrame:
    seed_order = sorted(seed_level["seed"].unique().tolist())
    bootstrap_index = _bootstrap_indices(
        len(seed_order), bootstrap_replications, config.PARAMETERS.bootstrap_seed
    )
    records: list[dict[str, Any]] = []
    group_columns = [
        "route_id",
        "route_label_rate",
        "attribution_proxy_noise_sd",
        "configuration_id",
        "analysis_tier",
    ]
    for keys, group in seed_level.groupby(group_columns, dropna=False, sort=False):
        group = group.sort_values("seed")
        observed_seeds = group["seed"].tolist()
        if observed_seeds != seed_order:
            raise RuntimeError(
                "Module A shared-seed invariant failed for configuration "
                f"{keys}: observed={observed_seeds}, expected={seed_order}"
            )
        record = dict(zip(group_columns, keys, strict=True))
        record["shared_seed_count"] = len(group)
        for metric in MODULE_A_METRICS:
            values = group[metric].to_numpy(dtype=float)
            record[f"{metric}_mean"] = float(np.mean(values))
            record[f"{metric}_sd"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            if bootstrap_replications > 0:
                bootstrap_means = np.mean(values[bootstrap_index], axis=1)
                lower, upper = _quantile_interval(bootstrap_means)
            else:
                lower = upper = np.nan
            record[f"{metric}_ci_lower"] = lower
            record[f"{metric}_ci_upper"] = upper
        records.append(record)
    return pd.DataFrame.from_records(records)


def _bootstrap_summary_statistic(
    frame: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    bootstrap_replications: int,
    seed: int,
) -> tuple[float, float]:
    if bootstrap_replications <= 0 or len(frame) == 0:
        return np.nan, np.nan
    generator = np.random.default_rng(np.random.SeedSequence(seed))
    statistics = np.empty(bootstrap_replications, dtype=float)
    for index in range(bootstrap_replications):
        sample_positions = generator.integers(0, len(frame), size=len(frame))
        statistics[index] = statistic(frame.iloc[sample_positions])
    return _quantile_interval(statistics)


def summarize_audit_conditions(
    raw_estimates: pd.DataFrame,
    calibrated_estimates: pd.DataFrame,
    bootstrap_replications: int,
) -> pd.DataFrame:
    join_columns = [
        "replication_id",
        "route_id",
        "audit_evidence_rate",
        "audit_design_id",
        "inclusion_mechanism",
        "weighting_method",
    ]
    merged = raw_estimates.merge(
        calibrated_estimates,
        on=join_columns,
        how="left",
        validate="one_to_one",
        suffixes=("", "_cal"),
    )
    group_columns = [
        "route_id",
        "audit_evidence_rate",
        "audit_design_id",
        "inclusion_mechanism",
        "weighting_method",
    ]
    records: list[dict[str, Any]] = []
    for group_index, (keys, group) in enumerate(
        merged.groupby(group_columns, dropna=False, sort=False)
    ):
        group = group.sort_values("replication_id")
        finite_calibration = group["is_calibration_estimable"].fillna(False).astype(bool)
        raw_error = group["raw_estimation_error"].to_numpy(dtype=float)
        raw_bias = float(np.mean(raw_error))
        raw_rmse = float(np.sqrt(np.mean(raw_error**2)))
        calibrated_error = group.loc[
            finite_calibration, "calibrated_estimation_error"
        ].to_numpy(dtype=float)
        calibrated_bias = (
            float(np.mean(calibrated_error)) if len(calibrated_error) else np.nan
        )
        calibrated_rmse = (
            float(np.sqrt(np.mean(calibrated_error**2)))
            if len(calibrated_error)
            else np.nan
        )
        recoverability_error = group.loc[
            finite_calibration, "absolute_recoverability_error"
        ].dropna().to_numpy(dtype=float)
        record = dict(zip(group_columns, keys, strict=True))
        record.update(
            {
                "monte_carlo_replications": int(group["replication_id"].nunique()),
                "raw_bias": raw_bias,
                "raw_rmse": raw_rmse,
                "mean_absolute_raw_error": float(
                    np.mean(np.abs(raw_error))
                ),
                "calibrated_bias": calibrated_bias,
                "calibrated_rmse": calibrated_rmse,
                "recoverability_mae": (
                    float(np.mean(recoverability_error))
                    if len(recoverability_error)
                    else np.nan
                ),
                "negative_recoverability_rate": float(
                    np.mean(
                        group.loc[finite_calibration, "estimated_recoverability"]
                        < 0.0
                    )
                )
                if np.any(finite_calibration)
                else np.nan,
                "calibration_estimable_rate": float(np.mean(finite_calibration)),
                "mean_labelled_audit_sample_size": float(
                    group["labelled_audit_sample_size"].mean()
                ),
                "mean_effective_labelled_sample_size": float(
                    group["effective_labelled_sample_size"].mean()
                ),
                "mean_labelled_support_coefficient": float(
                    group["labelled_support_coefficient"].mean()
                ),
                "mean_pair_coverage_rate": float(group["pair_coverage_rate"].mean()),
                "mean_route_audit_mask_correlation": float(
                    group["route_audit_mask_correlation"].mean(skipna=True)
                ),
            }
        )
        statistics: dict[str, Callable[[pd.DataFrame], float]] = {
            "raw_bias": lambda sample: float(sample["raw_estimation_error"].mean()),
            "raw_rmse": lambda sample: float(
                np.sqrt(np.mean(sample["raw_estimation_error"].to_numpy(dtype=float) ** 2))
            ),
            "calibrated_bias": lambda sample: float(
                sample.loc[
                    sample["is_calibration_estimable"].fillna(False),
                    "calibrated_estimation_error",
                ].mean()
            ),
            "calibrated_rmse": lambda sample: float(
                np.sqrt(
                    np.mean(
                        sample.loc[
                            sample["is_calibration_estimable"].fillna(False),
                            "calibrated_estimation_error",
                        ].to_numpy(dtype=float)
                        ** 2
                    )
                )
            ),
        }
        for offset, (name, statistic) in enumerate(statistics.items()):
            lower, upper = _bootstrap_summary_statistic(
                group,
                statistic,
                bootstrap_replications,
                config.PARAMETERS.bootstrap_seed + 1000 * group_index + offset,
            )
            record[f"{name}_ci_lower"] = lower
            record[f"{name}_ci_upper"] = upper
        records.append(record)
    return pd.DataFrame.from_records(records)


def summarize_effective_support(raw_estimates: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "route_id",
        "audit_evidence_rate",
        "audit_design_id",
        "inclusion_mechanism",
        "weighting_method",
    ]
    return (
        raw_estimates.groupby(group_columns, dropna=False, sort=False)
        .agg(
            monte_carlo_replications=("replication_id", "nunique"),
            mean_labelled_audit_sample_size=("labelled_audit_sample_size", "mean"),
            sd_labelled_audit_sample_size=("labelled_audit_sample_size", "std"),
            mean_effective_labelled_sample_size=(
                "effective_labelled_sample_size",
                "mean",
            ),
            sd_effective_labelled_sample_size=(
                "effective_labelled_sample_size",
                "std",
            ),
            mean_labelled_support_coefficient=(
                "labelled_support_coefficient",
                "mean",
            ),
            sd_labelled_support_coefficient=(
                "labelled_support_coefficient",
                "std",
            ),
        )
        .reset_index()
    )


def summarize_calibration_controls(
    control_estimates: pd.DataFrame,
    bootstrap_replications: int,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for group_index, (control_id, group) in enumerate(
        control_estimates.groupby("control_id", sort=False)
    ):
        group = group.sort_values("replication_id")
        valid = group["is_calibration_estimable"].fillna(False).astype(bool)
        record = {
            "control_id": control_id,
            "control_display_name": group["control_display_name"].iloc[0],
            "analysis_tier": group["analysis_tier"].iloc[0],
            "audit_evidence_rate": float(group["audit_evidence_rate"].iloc[0]),
            "monte_carlo_replications": int(group["replication_id"].nunique()),
            "raw_defect_mean": float(group["sample_raw_action_gap_defect"].mean()),
            "calibrated_defect_mean": float(
                group.loc[valid, "sample_calibrated_action_gap_defect"].mean()
            ),
            "estimated_recoverability_mean": float(
                group.loc[valid, "estimated_recoverability"].mean()
            ),
            "negative_recoverability_rate": float(
                group.loc[valid, "negative_recoverability_indicator"].mean()
            ),
            "calibration_estimable_rate": float(valid.mean()),
        }
        for offset, (column, prefix) in enumerate(
            [
                ("sample_raw_action_gap_defect", "raw_defect"),
                ("sample_calibrated_action_gap_defect", "calibrated_defect"),
                ("estimated_recoverability", "estimated_recoverability"),
            ]
        ):
            finite_group = group.loc[valid] if column != "sample_raw_action_gap_defect" else group
            lower, upper = _bootstrap_summary_statistic(
                finite_group,
                lambda sample, selected=column: float(sample[selected].mean()),
                bootstrap_replications,
                config.PARAMETERS.bootstrap_seed + 20_000 + 1000 * group_index + offset,
            )
            record[f"{prefix}_ci_lower"] = lower
            record[f"{prefix}_ci_upper"] = upper
        records.append(record)
    return pd.DataFrame.from_records(records)
