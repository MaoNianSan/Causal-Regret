from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from contracts import (
    ALL_ROUTE_ORDER,
    CREDIT_TOLERANCE,
    DISALLOWED_RESULT_TERMS,
    MAXIMUM_KENDALL_NAN_FRACTION,
    PRIMARY_ROUTE_ORDER,
    PRIMARY_SOURCE_ROUTE_ORDER,
    ConfigurationError,
    ScientificInvariantError,
)


@dataclass(frozen=True)
class ValidationResult:
    engineering_status: str
    scientific_status: str
    paper_promotion_status: str
    checks: list[dict[str, Any]]

    @property
    def passed(self) -> bool:
        return self.engineering_status == "PASS" and self.scientific_status == "PASS"


def validate_frozen_configuration(config: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    expected_primary = list(PRIMARY_ROUTE_ORDER)
    observed_primary = list(config["routes"]["primary"])
    if observed_primary != expected_primary:
        raise ConfigurationError(
            f"Primary route order changed: expected={expected_primary}, observed={observed_primary}"
        )
    checks.append({"check": "primary_route_order", "status": "PASS"})

    if bool(config["cohort"].get("modal_campaign_fallback", True)) is not False:
        raise ConfigurationError("Modal-campaign fallback must remain prohibited.")
    checks.append({"check": "modal_campaign_fallback_prohibited", "status": "PASS"})

    if str(config["input"].get("timezone", "")).upper() != "UTC":
        raise ConfigurationError("Experiment 2 timestamps must be interpreted in UTC.")
    checks.append({"check": "utc_time_standard", "status": "PASS"})

    if int(config["ranking"]["primary_top_k"]) != 10:
        raise ConfigurationError("Primary top-k is frozen at 10.")
    checks.append({"check": "primary_top_k", "status": "PASS"})

    if str(config["ranking"]["kendall_variant"]) != "tau_b":
        raise ConfigurationError("Kendall variant is frozen at tau_b.")
    checks.append({"check": "kendall_tau_b", "status": "PASS"})

    half_life = float(config["routes"]["time_decay"].get("half_life_days", 0.0))
    if not np.isclose(half_life, 1.38629436112, atol=1e-10, rtol=0.0):
        raise ConfigurationError("Time-decay half-life is frozen at 1.38629436112 days.")
    checks.append({"check": "time_decay_half_life", "status": "PASS"})
    if str(config["resampling"].get("unit")) != "uid":
        raise ConfigurationError("UID-cluster resampling is required.")
    if list(config["resampling"].get("reported_quantiles", [])) != [0.025, 0.5, 0.975]:
        raise ConfigurationError("Resampling quantiles must be q025/q500/q975.")
    if bool(config["resampling"].get("inferential_interpretation", True)):
        raise ConfigurationError("UID-resampling ranges are descriptive, not inferential.")
    checks.append({"check": "uid_resampling_contract", "status": "PASS"})
    return checks


def _check_no_disallowed_columns(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    violations: list[str] = []
    for frame_name, frame in frames.items():
        for column in frame.columns:
            lowered = str(column).lower()
            for term in DISALLOWED_RESULT_TERMS:
                if term in lowered:
                    violations.append(f"{frame_name}.{column}")
    if violations:
        raise ScientificInvariantError(
            f"Out-of-scope result terminology found: {violations[:20]}"
        )
    return {"check": "no_out_of_scope_result_terms", "status": "PASS"}


def _check_pairwise_symmetry(pairwise: pd.DataFrame) -> dict[str, Any]:
    # The long output stores each unordered pair once. Reconstruct the matrix and
    # verify that its mathematical symmetric completion is valid.
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    matrix = pd.DataFrame(np.nan, index=routes, columns=routes, dtype=float)
    np.fill_diagonal(matrix.values, 0.0)
    for row in pairwise.itertuples(index=False):
        matrix.loc[row.route_left, row.route_right] = float(row.allocation_tv)
        matrix.loc[row.route_right, row.route_left] = float(row.allocation_tv)
    if matrix.isna().any().any():
        raise ScientificInvariantError("Pairwise allocation-TV matrix is incomplete.")
    if not np.allclose(matrix.to_numpy(), matrix.to_numpy().T, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Pairwise allocation-TV matrix is not symmetric.")
    if not np.allclose(np.diag(matrix), 0.0, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Pairwise allocation-TV diagonal is not zero.")
    return {"check": "pairwise_metric_symmetry", "status": "PASS"}


def _check_frozen_kendall_support(
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
            (str(row.route_left), str(row.route_right)): int(
                row.common_active_cell_count
            )
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
        full_counts = pd.to_numeric(
            group["full_sample_support_count"], errors="raise"
        ).unique()
        if len(full_counts) != 1 or int(full_counts[0]) != point_support[key]:
            raise ScientificInvariantError(
                f"Bootstrap full-sample support does not match point support for {key}."
            )
        observed = pd.to_numeric(group["bootstrap_support_count"], errors="raise")
        support_min = int(observed.min())
        support_max = int(observed.max())
        if (
            support_min != point_support[key]
            or support_max != point_support[key]
            or not bool(group["support_frozen"].all())
        ):
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
    if set(point_support) != {
        (item["route_left"], item["route_right"]) for item in diagnostics
    }:
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


def validate_run(
    config: dict[str, Any],
    *,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    assignments: pd.DataFrame,
    route_allocations: pd.DataFrame,
    arrival_displacement: pd.DataFrame,
    source_route_pairwise: pd.DataFrame,
    bootstrap_draws: pd.DataFrame,
    mode: str,
    expected_bootstrap_repetitions: int | None = None,
    bootstrap_audit: dict[str, Any] | None = None,
    development_override: bool = False,
) -> ValidationResult:
    checks = validate_frozen_configuration(config)

    retained = journey_manifest.loc[journey_manifest["is_primary_eligible"]]
    if retained.empty:
        raise ScientificInvariantError("Primary cohort is empty.")
    checks.append(
        {
            "check": "primary_cohort_nonempty",
            "status": "PASS",
            "value": int(len(retained)),
        }
    )

    if retained["user_id"].isna().any() or retained["user_id"].astype(str).isin({"-1", "-1.0"}).any():
        raise ScientificInvariantError("Retained cohort contains invalid user IDs.")
    checks.append({"check": "valid_bootstrap_users", "status": "PASS"})

    if retained["candidate_campaign_count"].ne(1).any():
        raise ScientificInvariantError("A multi-campaign journey entered the primary cohort.")
    checks.append({"check": "unique_campaign_primary_cohort", "status": "PASS"})

    if not bool(retained["has_complete_lookback"].all()):
        raise ScientificInvariantError("An incomplete-lookback journey entered the primary cohort.")
    checks.append({"check": "complete_lookback_primary_cohort", "status": "PASS"})

    ambiguous_count = int(retained["is_attribution_ambiguous"].sum())
    if ambiguous_count <= 0:
        raise ScientificInvariantError(
            "No attribution-ambiguous journeys remain; the primary diagnostic is unsupported."
        )
    checks.append(
        {
            "check": "attribution_ambiguity_present",
            "status": "PASS",
            "value": ambiguous_count,
        }
    )

    max_top_k = max(
        [int(config["ranking"]["primary_top_k"])]
        + [int(value) for value in config["ranking"].get("targeted_top_k", [])]
    )
    if len(decision_cells) <= max_top_k:
        raise ScientificInvariantError(
            f"Decision-cell universe={len(decision_cells)} is not larger than max top-k={max_top_k}."
        )
    checks.append({"check": "decision_cell_support_for_top_k", "status": "PASS"})

    primary_assignments = assignments.loc[assignments["route_id"].isin(PRIMARY_ROUTE_ORDER)]
    cohort_sets = {
        route_id: frozenset(
            primary_assignments.loc[
                primary_assignments["route_id"].eq(route_id), "journey_id"
            ].astype(str)
        )
        for route_id in PRIMARY_ROUTE_ORDER
    }
    if len(set(cohort_sets.values())) != 1:
        raise ScientificInvariantError("Primary routes use different journey cohorts.")
    checks.append({"check": "common_route_cohort", "status": "PASS"})

    credit_sums = (
        primary_assignments.groupby(["route_id", "journey_id"], sort=False)["credit_weight"]
        .sum()
        .sub(1.0)
        .abs()
    )
    if credit_sums.gt(CREDIT_TOLERANCE).any():
        raise ScientificInvariantError("Primary route credit conservation failed.")
    checks.append({"check": "credit_conservation", "status": "PASS"})

    single_cell_ids = set(
        retained.loc[retained["candidate_cell_count"].eq(1), "journey_id"].astype(str)
    )
    single_cell = primary_assignments.loc[
        primary_assignments["journey_id"].astype(str).isin(single_cell_ids)
        & primary_assignments["route_id"].isin(PRIMARY_SOURCE_ROUTE_ORDER)
    ]
    if single_cell_ids:
        counts = single_cell.groupby(["route_id", "journey_id"], sort=False).agg(
            assigned_cell_count=("decision_cell_id", "nunique"),
            credit_sum=("credit_weight", "sum"),
        )
        if counts["assigned_cell_count"].ne(1).any() or not np.allclose(
            counts["credit_sum"].to_numpy(dtype=float), 1.0, atol=CREDIT_TOLERANCE, rtol=0.0
        ):
            raise ScientificInvariantError("Single-cell source-route invariant failed.")
    checks.append({"check": "single_cell_source_route_invariant", "status": "PASS"})

    allocation_sums = route_allocations.groupby("route_id", sort=False)["allocation_share"].sum()
    if not np.allclose(allocation_sums.to_numpy(), 1.0, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("Route allocation vectors do not sum to one.")
    checks.append({"check": "allocation_normalization", "status": "PASS"})

    denominator_counts = route_allocations.groupby("decision_cell_id", sort=False)[
        "eligible_impression_count"
    ].nunique()
    if denominator_counts.gt(1).any():
        raise ScientificInvariantError("Ranking denominator changes across routes.")
    checks.append({"check": "common_ranking_denominator", "status": "PASS"})

    if arrival_displacement["allocation_tv_vs_arrival"].lt(-1e-12).any() or arrival_displacement[
        "allocation_tv_vs_arrival"
    ].gt(1.0 + 1e-12).any():
        raise ScientificInvariantError("Arrival allocation TV is outside [0,1].")
    checks.append({"check": "arrival_tv_range", "status": "PASS"})

    checks.append(_check_pairwise_symmetry(source_route_pairwise))
    checks.append(
        _check_no_disallowed_columns(
            {
                "journey_manifest": journey_manifest,
                "route_allocations": route_allocations,
                "arrival_displacement": arrival_displacement,
                "source_route_pairwise": source_route_pairwise,
            }
        )
    )
    checks.append(
        _check_frozen_kendall_support(
            arrival_displacement,
            source_route_pairwise,
            bootstrap_draws,
            bootstrap_audit,
        )
    )

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
    checks.append(
        {
            "check": "bootstrap_complete",
            "status": "PASS",
            "value": observed_repetitions,
        }
    )

    kendall_outside_count = int(
        arrival_displacement["kendall_tau_b_full_sample_outside_resampling_range"]
        .fillna(False).astype(bool).sum()
        + source_route_pairwise["kendall_tau_b_full_sample_outside_resampling_range"]
        .fillna(False).astype(bool).sum()
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
    checks.append(
        {
            "check": "reported_resampling_repetitions_consistent",
            "status": "PASS",
            "value": reported,
        }
    )

    outside_column = "allocation_tv_full_sample_outside_resampling_range"
    outside_count = int(
        source_route_pairwise[outside_column].fillna(False).astype(bool).sum()
    )
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

    if bool(config["runtime"].get("paper_result", False)):
        raise ConfigurationError("Runtime configuration cannot directly set paper_result=true.")
    checks.append({"check": "explicit_paper_promotion_only", "status": "PASS"})

    if mode == "fast":
        promotion_status = "INELIGIBLE_FAST"
    elif development_override:
        promotion_status = "BLOCKED_DEVELOPMENT_OVERRIDE"
    else:
        promotion_status = "PENDING_INDEPENDENT_PROMOTION"
    return ValidationResult(
        engineering_status="PASS",
        scientific_status="PASS",
        paper_promotion_status=promotion_status,
        checks=checks,
    )
