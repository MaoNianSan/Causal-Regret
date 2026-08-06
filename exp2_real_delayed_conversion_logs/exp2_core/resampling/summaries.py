from __future__ import annotations

import numpy as np
import pandas as pd

from contracts import ScientificInvariantError


def quantile_summary(
    draws: pd.DataFrame,
    *,
    group_columns: list[str],
    reported_quantiles: tuple[float, float, float],
) -> pd.DataFrame:
    q025, q500, q975 = reported_quantiles
    metrics = [
        "allocation_tv",
        "top_k_overlap",
        "top_k_set_disagreement",
        "kendall_tau_b",
        "common_active_cell_count",
    ]
    rows: list[dict[str, object]] = []
    for keys, group in draws.groupby(group_columns, sort=False, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys, strict=True))
        row["resampling_repetitions"] = int(group["replication_id"].nunique())
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(dtype=float)
            row[f"{metric}_resampling_mean"] = float(np.mean(values)) if len(values) else np.nan
            row[f"{metric}_resampling_q025"] = float(np.quantile(values, q025)) if len(values) else np.nan
            row[f"{metric}_resampling_q500"] = float(np.quantile(values, q500)) if len(values) else np.nan
            row[f"{metric}_resampling_q975"] = float(np.quantile(values, q975)) if len(values) else np.nan
        full_counts = pd.to_numeric(group["full_sample_support_count"], errors="raise").unique()
        if len(full_counts) != 1:
            raise ScientificInvariantError("Full-sample Kendall support varies within a comparison.")
        bootstrap_support = pd.to_numeric(
            group["bootstrap_support_count"], errors="raise"
        ).to_numpy(dtype=int)
        row["full_sample_support_count"] = int(full_counts[0])
        row["bootstrap_support_min"] = int(bootstrap_support.min())
        row["bootstrap_support_max"] = int(bootstrap_support.max())
        row["support_frozen"] = bool(group["support_frozen"].all())
        row["kendall_tau_b_nan_fraction"] = float(group["kendall_tau_b"].isna().mean())
        row["constant_vector_fraction"] = float(group["constant_vector"].mean())
        row["zero_mass_vector_fraction"] = float(group["zero_mass_vector"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def _attach_metric_diagnostics(
    frame: pd.DataFrame,
    point_columns: dict[str, str],
) -> pd.DataFrame:
    output = frame.copy()
    for metric, point_column in point_columns.items():
        mean_column = f"{metric}_resampling_mean"
        median_column = f"{metric}_resampling_q500"
        lower_column = f"{metric}_resampling_q025"
        upper_column = f"{metric}_resampling_q975"
        output[f"{metric}_resampling_bias_mean"] = output[mean_column] - output[point_column]
        output[f"{metric}_resampling_bias_q500"] = output[median_column] - output[point_column]
        output[f"{metric}_full_sample_outside_resampling_range"] = (
            output[point_column].lt(output[lower_column])
            | output[point_column].gt(output[upper_column])
        )
    return output


def attach_bootstrap_intervals(
    arrival_point: pd.DataFrame,
    pairwise_point: pd.DataFrame,
    bootstrap,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    arrival = arrival_point.merge(
        bootstrap.arrival_summary,
        on=["route_id", "top_k"],
        how="left",
        validate="one_to_one",
    )
    pairwise = pairwise_point.merge(
        bootstrap.pairwise_summary,
        on=["route_left", "route_right", "top_k"],
        how="left",
        validate="one_to_one",
    )
    arrival = _attach_metric_diagnostics(
        arrival,
        {
            "allocation_tv": "allocation_tv_vs_arrival",
            "top_k_overlap": "top_k_overlap_vs_arrival",
            "top_k_set_disagreement": "top_k_set_disagreement",
            "kendall_tau_b": "kendall_tau_b_vs_arrival",
            "common_active_cell_count": "common_active_cell_count",
        },
    )
    pairwise = _attach_metric_diagnostics(
        pairwise,
        {
            "allocation_tv": "allocation_tv",
            "top_k_overlap": "top_k_overlap",
            "top_k_set_disagreement": "top_k_set_disagreement",
            "kendall_tau_b": "kendall_tau_b",
            "common_active_cell_count": "common_active_cell_count",
        },
    )
    return arrival, pairwise
