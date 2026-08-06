from __future__ import annotations

from typing import Any

import pandas as pd

from contracts import MAXIMUM_KENDALL_NAN_FRACTION, ScientificInvariantError


def check_frozen_kendall_support(
    arrival_displacement: pd.DataFrame,
    source_route_pairwise: pd.DataFrame,
    bootstrap_draws: pd.DataFrame,
    bootstrap_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    required_draw_columns = {
        "full_sample_support_count",
        "bootstrap_support_count",
        "support_frozen",
        "constant_vector",
        "zero_mass_vector",
    }
    missing = sorted(required_draw_columns.difference(bootstrap_draws.columns))
    if missing:
        raise ScientificInvariantError(
            f"Bootstrap draws lack frozen-support audit fields: {missing}"
        )
    point_support = {
        ("arrival_time_accounting_anchor", str(row.route_id)): int(row.common_active_cell_count)
        for row in arrival_displacement.itertuples(index=False)
    }
    point_support.update(
        {
            (str(row.route_left), str(row.route_right)): int(row.common_active_cell_count)
            for row in source_route_pairwise.itertuples(index=False)
        }
    )
    diagnostics: list[dict[str, Any]] = []
    for keys, group in bootstrap_draws.groupby(
        ["route_left", "route_right"], sort=False, dropna=False
    ):
        key = (str(keys[0]), str(keys[1]))
        if key not in point_support:
            raise ScientificInvariantError(f"Unexpected bootstrap route pair: {key}")
        full_counts = pd.to_numeric(group["full_sample_support_count"], errors="raise").unique()
        if len(full_counts) != 1 or int(full_counts[0]) != point_support[key]:
            raise ScientificInvariantError(
                f"Bootstrap full-sample support does not match point support for {key}."
            )
        observed = pd.to_numeric(group["bootstrap_support_count"], errors="raise")
        support_min = int(observed.min())
        support_max = int(observed.max())
        if support_min != point_support[key] or support_max != point_support[key] or not bool(group["support_frozen"].all()):
            raise ScientificInvariantError(
                f"Kendall support drift detected for {key}: point={point_support[key]}, "
                f"bootstrap_min={support_min}, bootstrap_max={support_max}."
            )
        nan_fraction = float(group["kendall_tau_b"].isna().mean())
        if nan_fraction > MAXIMUM_KENDALL_NAN_FRACTION:
            raise ScientificInvariantError(
                f"Kendall NaN fraction exceeds {MAXIMUM_KENDALL_NAN_FRACTION:.1%} "
                f"for {key}: {nan_fraction:.1%}."
            )
        diagnostics.append(
            {
                "route_left": key[0],
                "route_right": key[1],
                "full_sample_support_count": point_support[key],
                "bootstrap_support_min": support_min,
                "bootstrap_support_max": support_max,
                "nan_fraction": nan_fraction,
            }
        )
    if set(point_support) != {(item["route_left"], item["route_right"]) for item in diagnostics}:
        raise ScientificInvariantError("Frozen-support validation did not cover every comparison.")
    if bootstrap_audit is None or not bool(bootstrap_audit.get("support_frozen", False)):
        raise ScientificInvariantError("Bootstrap audit does not certify frozen Kendall support.")
    audit_comparisons = bootstrap_audit.get("comparisons", [])
    if len(audit_comparisons) != len(diagnostics):
        raise ScientificInvariantError("Bootstrap audit comparison count is incomplete.")
    return {
        "check": "kendall_bootstrap_support_frozen",
        "status": "PASS",
        "comparison_count": len(diagnostics),
        "maximum_nan_fraction": max(item["nan_fraction"] for item in diagnostics),
        "nan_fraction_limit": MAXIMUM_KENDALL_NAN_FRACTION,
    }


def validate_resampling_artifacts(
    config: dict[str, Any],
    *,
    arrival_displacement: pd.DataFrame,
    source_route_pairwise: pd.DataFrame,
    bootstrap_draws: pd.DataFrame,
    mode: str,
    expected_bootstrap_repetitions: int | None,
    bootstrap_audit: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    checks = [
        check_frozen_kendall_support(
            arrival_displacement,
            source_route_pairwise,
            bootstrap_draws,
            bootstrap_audit,
        )
    ]
    expected_repetitions = int(
        expected_bootstrap_repetitions
        if expected_bootstrap_repetitions is not None
        else config["resampling"]["fast_repetitions" if mode == "fast" else "full_repetitions"]
    )
    observed_repetitions = int(bootstrap_draws["replication_id"].nunique())
    if observed_repetitions != expected_repetitions:
        raise ScientificInvariantError(
            f"Bootstrap incomplete: observed={observed_repetitions}, expected={expected_repetitions}."
        )
    checks.append({"check": "bootstrap_complete", "status": "PASS", "value": observed_repetitions})
    kendall_outside_count = int(
        arrival_displacement["kendall_tau_b_full_sample_outside_resampling_range"].fillna(False).astype(bool).sum()
        + source_route_pairwise["kendall_tau_b_full_sample_outside_resampling_range"].fillna(False).astype(bool).sum()
    )
    checks.append(
        {
            "check": "kendall_percentile_bootstrap_behavior",
            "status": "WARNING" if kendall_outside_count else "PASS",
            "value": kendall_outside_count,
            "note": (
                "Point estimates outside fixed-support percentile intervals are reported as "
                "sampling-distribution behavior and do not change the frozen interval method."
            ),
        }
    )
    reported: dict[str, int] = {"bootstrap_draws": observed_repetitions}
    for frame_name, frame in (
        ("arrival_displacement", arrival_displacement),
        ("source_route_pairwise", source_route_pairwise),
    ):
        values = pd.to_numeric(frame["resampling_repetitions"], errors="coerce").dropna().unique()
        if len(values) != 1:
            raise ScientificInvariantError(
                f"{frame_name} reports inconsistent bootstrap repetitions: {values.tolist()}"
            )
        reported[frame_name] = int(values[0])
    if bootstrap_audit is not None:
        reported["bootstrap_audit"] = int(bootstrap_audit["resampling_repetitions"])
    if any(value != expected_repetitions for value in reported.values()):
        raise ScientificInvariantError(
            f"Reported bootstrap repetitions are inconsistent: expected={expected_repetitions}, "
            f"reported={reported}"
        )
    checks.append({"check": "reported_resampling_repetitions_consistent", "status": "PASS", "value": reported})
    outside_column = "allocation_tv_full_sample_outside_resampling_range"
    outside_count = int(source_route_pairwise[outside_column].fillna(False).astype(bool).sum())
    checks.append(
        {
            "check": "percentile_bootstrap_bias_diagnostic",
            "status": "WARNING" if outside_count else "PASS",
            "value": outside_count,
            "note": (
                "Warnings do not fail the run; they record point estimates outside percentile "
                "bootstrap intervals for the non-smooth allocation-TV diagnostic."
            ),
        }
    )
    return checks
