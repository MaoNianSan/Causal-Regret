from __future__ import annotations

from typing import Any

import pandas as pd

from contracts import ScientificInvariantError


def build_resampling_audit(
    draws: pd.DataFrame,
    *,
    n_bootstrap: int,
    base_seed: int,
    reported_quantiles: tuple[float, float, float],
    n_users: int,
    n_jobs: int,
) -> dict[str, Any]:
    comparison_audit: list[dict[str, Any]] = []
    for keys, group in draws.groupby(
        ["record_type", "route_left", "route_right"], sort=False, dropna=False
    ):
        full_counts = group["full_sample_support_count"].unique()
        if len(full_counts) != 1:
            raise ScientificInvariantError("Bootstrap comparison has inconsistent full support.")
        comparison_audit.append(
            {
                "record_type": str(keys[0]),
                "route_left": str(keys[1]),
                "route_right": str(keys[2]),
                "full_sample_support_count": int(full_counts[0]),
                "bootstrap_support_min": int(group["bootstrap_support_count"].min()),
                "bootstrap_support_max": int(group["bootstrap_support_count"].max()),
                "support_frozen": bool(group["support_frozen"].all()),
                "nan_fraction": float(group["kendall_tau_b"].isna().mean()),
                "constant_vector_fraction": float(group["constant_vector"].mean()),
                "zero_mass_vector_fraction": float(group["zero_mass_vector"].mean()),
            }
        )
    return {
        "resampling_unit": "uid",
        "resampling_repetitions": n_bootstrap,
        "resampling_seed": base_seed,
        "reported_quantiles": list(reported_quantiles),
        "inferential_interpretation": False,
        "n_users": n_users,
        "n_jobs": n_jobs,
        "support_definition": "full_sample_union_positive_credit_cells",
        "support_frozen": bool(all(item["support_frozen"] for item in comparison_audit)),
        "comparisons": comparison_audit,
    }


def build_bootstrap_bias_audit(
    arrival: pd.DataFrame, pairwise: pd.DataFrame
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for frame_name, frame, identity_columns in (
        ("arrival_displacement", arrival, ["route_id"]),
        ("source_route_pair", pairwise, ["route_left", "route_right"]),
    ):
        for metric in (
            "allocation_tv",
            "top_k_overlap",
            "top_k_set_disagreement",
            "kendall_tau_b",
            "common_active_cell_count",
        ):
            outside_column = f"{metric}_full_sample_outside_resampling_range"
            mean_bias_column = f"{metric}_resampling_bias_mean"
            median_bias_column = f"{metric}_resampling_bias_q500"
            for row in frame.itertuples(index=False):
                record = {
                    "record_type": frame_name,
                    "metric": metric,
                    "full_sample_outside_resampling_range": bool(getattr(row, outside_column)),
                    "resampling_bias_mean": float(getattr(row, mean_bias_column)),
                    "resampling_bias_q500": float(getattr(row, median_bias_column)),
                }
                for identity in identity_columns:
                    record[identity] = getattr(row, identity)
                records.append(record)
    allocation_tv_records = [record for record in records if record["metric"] == "allocation_tv"]
    outside_count = sum(
        record["full_sample_outside_resampling_range"] for record in allocation_tv_records
    )
    return {
        "reported_quantiles": [0.025, 0.5, 0.975],
        "inferential_interpretation": False,
        "headline_metric": "allocation_tv",
        "diagnostic_status": "WARNING" if outside_count else "PASS",
        "full_sample_outside_resampling_range_count": int(outside_count),
        "diagnostic_count": int(len(allocation_tv_records)),
        "all_metric_diagnostic_count": int(len(records)),
        "interpretation": (
            "A full-sample estimate outside the empirical UID-resampling range is a descriptive "
            "diagnostic, not an inferential failure."
        ),
        "records": records,
    }
