from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Iterable

import pandas as pd
import numpy as np

from cohort import CohortBuildResult, build_primary_cohort
from contracts import DataContractError, ScientificInvariantError
from metrics import MetricResult, compute_primary_metrics, compute_targeted_top_k_metrics
from routes import build_attribution_routes


def _restrict_cohort(cohort: CohortBuildResult, common_ids: set[str]) -> CohortBuildResult:
    manifest = cohort.journey_manifest.copy()
    original_eligible = manifest["is_primary_eligible"].copy()
    in_common = manifest["journey_id"].astype(str).isin(common_ids)
    manifest["is_primary_eligible"] = original_eligible & in_common
    manifest.loc[original_eligible & ~in_common, "primary_exclusion_reason"] = "targeted_common_cohort_exclusion"
    manifest.loc[original_eligible & ~in_common, "exclusion_reason"] = "targeted_common_cohort_exclusion"
    candidates = cohort.eligible_candidates.loc[
        cohort.eligible_candidates["journey_id"].astype(str).isin(common_ids)
    ].copy()
    return CohortBuildResult(
        journey_manifest=manifest,
        eligible_candidates=candidates,
        decision_cell_universe=cohort.decision_cell_universe,
        cohort_summary=cohort.cohort_summary,
        audit={**cohort.audit, "targeted_common_journey_count": len(common_ids)},
    )


def _metric_rows(
    metrics: MetricResult,
    *,
    dimension: str,
    value: int | float,
    cohort: CohortBuildResult,
    cohort_mode: str | None = None,
) -> list[dict[str, object]]:
    retained = cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"]]
    rows: list[dict[str, object]] = []
    for row in metrics.arrival_displacement.itertuples(index=False):
        rows.append(
            {
                "analysis_tier": "targeted",
                "analysis_status": "COMPLETED",
                "targeted_dimension": dimension,
                "targeted_value": value,
                "cohort_mode": cohort_mode,
                "record_type": "arrival_displacement",
                "route_id": row.route_id,
                "route_left": "arrival_time_accounting_anchor",
                "route_right": row.route_id,
                "allocation_tv": row.allocation_tv_vs_arrival,
                "top_k": row.top_k,
                "top_k_overlap": row.top_k_overlap_vs_arrival,
                "top_k_set_disagreement": row.top_k_set_disagreement,
                "kendall_tau_b": row.kendall_tau_b_vs_arrival,
                "retained_journey_count": int(len(retained)),
                "retained_user_count": int(retained["user_id"].nunique()),
                "eligible_decision_cell_count": int(len(cohort.decision_cell_universe)),
            }
        )
    for row in metrics.source_route_pairwise.itertuples(index=False):
        rows.append(
            {
                "analysis_tier": "targeted",
                "analysis_status": "COMPLETED",
                "targeted_dimension": dimension,
                "targeted_value": value,
                "cohort_mode": cohort_mode,
                "record_type": "source_route_pair",
                "route_id": pd.NA,
                "route_left": row.route_left,
                "route_right": row.route_right,
                "allocation_tv": row.allocation_tv,
                "top_k": row.top_k,
                "top_k_overlap": row.top_k_overlap,
                "top_k_set_disagreement": row.top_k_set_disagreement,
                "kendall_tau_b": row.kendall_tau_b,
                "retained_journey_count": int(len(retained)),
                "retained_user_count": int(retained["user_id"].nunique()),
                "eligible_decision_cell_count": int(len(cohort.decision_cell_universe)),
            }
        )
    return rows


def run_targeted_analyses(
    *,
    prepared_candidates: pd.DataFrame,
    impression_counts: pd.DataFrame,
    primary_cohort: CohortBuildResult,
    primary_metrics: MetricResult,
    config: dict[str, Any],
    mode: str,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    # Top-k sensitivity reuses the frozen primary cohort, route allocations, and
    # denominator. It is not crossed with window or support-threshold changes.
    top_k = compute_targeted_top_k_metrics(
        primary_metrics.route_allocations,
        [int(value) for value in config["ranking"].get("targeted_top_k", [])],
    )
    top_k["analysis_status"] = "COMPLETED"
    retained = primary_cohort.journey_manifest.loc[
        primary_cohort.journey_manifest["is_primary_eligible"]
    ]
    top_k["retained_journey_count"] = int(len(retained))
    top_k["retained_user_count"] = int(retained["user_id"].nunique())
    top_k["eligible_decision_cell_count"] = int(len(primary_cohort.decision_cell_universe))
    records.extend(top_k.to_dict(orient="records"))

    if mode != "full":
        records.extend(
            [
                {
                    "analysis_tier": "targeted",
                    "analysis_status": "NOT_RUN_IN_FAST",
                    "targeted_dimension": "candidate_window_days",
                    "targeted_value": 7,
                    "record_type": "run_status",
                },
                {
                    "analysis_tier": "targeted",
                    "analysis_status": "NOT_RUN_IN_FAST",
                    "targeted_dimension": "minimum_impressions",
                    "targeted_value": "25|100",
                    "record_type": "run_status",
                },
                {
                    "analysis_tier": "targeted",
                    "analysis_status": "NOT_RUN_IN_FAST",
                    "targeted_dimension": "time_decay_half_life_days",
                    "targeted_value": "1|1.38629436112|3|7",
                    "record_type": "run_status",
                },
            ]
        )
        return pd.DataFrame(records)

    primary_top_k = int(config["ranking"]["primary_top_k"])

    # Candidate-window sensitivity: build the 7-day cohort, then compare 7 and
    # 30 days on the intersection of route-independent eligible journeys.
    primary_window = int(config["cohort"]["primary_candidate_window_days"])
    window_values = [primary_window] + [
        int(value) for value in config["cohort"].get("robustness_candidate_window_days", [])
    ]
    window_cohorts: dict[int, CohortBuildResult] = {primary_window: primary_cohort}
    window_failures: dict[int, str] = {}
    for window in window_values[1:]:
        filtered = prepared_candidates.loc[
            prepared_candidates["source_lag_days"].le(float(window))
        ].copy()
        window_config = deepcopy(config)
        window_config["cohort"]["analysis_window_days"] = window
        try:
            window_cohorts[window] = build_primary_cohort(
                filtered, impression_counts, window_config
            )
        except (DataContractError, ScientificInvariantError) as exc:
            window_failures[window] = str(exc)
            records.append(
                {
                    "analysis_tier": "targeted",
                    "analysis_status": "NOT_ESTIMABLE",
                    "targeted_dimension": "candidate_window_days",
                    "targeted_value": window,
                    "record_type": "run_status",
                    "status_reason": str(exc),
                }
            )
    if len(window_cohorts) >= 2:
        for window, cohort in window_cohorts.items():
            try:
                routes = build_attribution_routes(
                    cohort.eligible_candidates,
                    cohort.journey_manifest,
                    cohort.decision_cell_universe,
                    config,
                )
                metrics = compute_primary_metrics(
                    routes.assignments,
                    cohort.decision_cell_universe,
                    cohort.journey_manifest,
                    top_k=primary_top_k,
                )
                records.extend(
                    _metric_rows(
                        metrics,
                        dimension="candidate_window_days",
                        value=window,
                        cohort=cohort,
                        cohort_mode="window_specific",
                    )
                )
            except (DataContractError, ScientificInvariantError) as exc:
                records.append(
                    {
                        "analysis_tier": "targeted",
                        "analysis_status": "NOT_ESTIMABLE",
                        "targeted_dimension": "candidate_window_days",
                        "targeted_value": window,
                        "cohort_mode": "window_specific",
                        "record_type": "run_status",
                        "status_reason": str(exc),
                    }
                )
        common_window_ids = set.intersection(
            *[
                set(
                    cohort.journey_manifest.loc[
                        cohort.journey_manifest["is_primary_eligible"], "journey_id"
                    ].astype(str)
                )
                for cohort in window_cohorts.values()
            ]
        )
        if common_window_ids:
            for window, cohort in window_cohorts.items():
                restricted = _restrict_cohort(cohort, common_window_ids)
                try:
                    routes = build_attribution_routes(
                        restricted.eligible_candidates,
                        restricted.journey_manifest,
                        restricted.decision_cell_universe,
                        config,
                    )
                    metrics = compute_primary_metrics(
                        routes.assignments,
                        restricted.decision_cell_universe,
                        restricted.journey_manifest,
                        top_k=primary_top_k,
                    )
                    records.extend(
                        _metric_rows(
                            metrics,
                    dimension="candidate_window_days",
                            value=window,
                            cohort=restricted,
                            cohort_mode="common_intersection",
                        )
                    )
                except (DataContractError, ScientificInvariantError) as exc:
                    records.append(
                        {
                            "analysis_tier": "targeted",
                            "analysis_status": "NOT_ESTIMABLE",
                            "targeted_dimension": "candidate_window_days",
                            "targeted_value": window,
                            "record_type": "run_status",
                            "status_reason": str(exc),
                        }
                    )
        else:
            for window in window_cohorts:
                records.append(
                    {
                        "analysis_tier": "targeted",
                        "analysis_status": "NOT_ESTIMABLE",
                        "targeted_dimension": "candidate_window_days",
                        "targeted_value": window,
                        "record_type": "run_status",
                        "status_reason": "No common eligible journey cohort across candidate windows.",
                    }
                )

    half_lives = [
        float(config["routes"]["time_decay"]["half_life_days"]),
        *[
            float(value)
            for value in config["routes"]["time_decay"].get(
                "robustness_half_life_days", []
            )
        ],
    ]
    for half_life in dict.fromkeys(half_lives):
        decay_config = deepcopy(config)
        decay_config["routes"]["time_decay"]["half_life_days"] = half_life
        routes = build_attribution_routes(
            primary_cohort.eligible_candidates,
            primary_cohort.journey_manifest,
            primary_cohort.decision_cell_universe,
            decay_config,
        )
        metrics = compute_primary_metrics(
            routes.assignments,
            primary_cohort.decision_cell_universe,
            primary_cohort.journey_manifest,
            top_k=primary_top_k,
        )
        records.extend(
            _metric_rows(
                metrics,
                dimension="time_decay_half_life_days",
                value=half_life,
                cohort=primary_cohort,
            )
        )

    # Cell-support sensitivity: build each threshold first, then use the common
    # eligible journey set so that the comparison is not driven by cohort changes.
    threshold_values = [int(config["decision_cell"]["minimum_impressions"])] + [
        int(value) for value in config["decision_cell"].get("support_sensitivity", [])
    ]
    threshold_cohorts: dict[int, CohortBuildResult] = {}
    for threshold in threshold_values:
        threshold_config = deepcopy(config)
        threshold_config["decision_cell"]["minimum_impressions"] = threshold
        try:
            threshold_cohorts[threshold] = build_primary_cohort(
                prepared_candidates,
                impression_counts,
                threshold_config,
            )
        except (DataContractError, ScientificInvariantError) as exc:
            records.append(
                {
                    "analysis_tier": "targeted",
                    "analysis_status": "NOT_ESTIMABLE",
                    "targeted_dimension": "minimum_impressions",
                    "targeted_value": threshold,
                    "record_type": "run_status",
                    "status_reason": str(exc),
                }
            )
    if threshold_cohorts:
        common_threshold_ids = set.intersection(
            *[
                set(
                    cohort.journey_manifest.loc[
                        cohort.journey_manifest["is_primary_eligible"], "journey_id"
                    ].astype(str)
                )
                for cohort in threshold_cohorts.values()
            ]
        )
        if common_threshold_ids:
            for threshold, cohort in threshold_cohorts.items():
                restricted = _restrict_cohort(cohort, common_threshold_ids)
                try:
                    routes = build_attribution_routes(
                        restricted.eligible_candidates,
                        restricted.journey_manifest,
                        restricted.decision_cell_universe,
                        config,
                    )
                    metrics = compute_primary_metrics(
                        routes.assignments,
                        restricted.decision_cell_universe,
                        restricted.journey_manifest,
                        top_k=primary_top_k,
                    )
                    records.extend(
                        _metric_rows(
                            metrics,
                            dimension="minimum_impressions",
                            value=threshold,
                            cohort=restricted,
                        )
                    )
                except (DataContractError, ScientificInvariantError) as exc:
                    records.append(
                        {
                            "analysis_tier": "targeted",
                            "analysis_status": "NOT_ESTIMABLE",
                            "targeted_dimension": "minimum_impressions",
                            "targeted_value": threshold,
                            "record_type": "run_status",
                            "status_reason": str(exc),
                        }
                    )
        else:
            for threshold in threshold_cohorts:
                records.append(
                    {
                        "analysis_tier": "targeted",
                        "analysis_status": "NOT_ESTIMABLE",
                        "targeted_dimension": "minimum_impressions",
                        "targeted_value": threshold,
                        "record_type": "run_status",
                        "status_reason": "No common eligible journey cohort across support thresholds.",
                    }
                )

    return pd.DataFrame(records)


def build_robustness_summary(
    targeted: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    completed = targeted.loc[targeted["analysis_status"].eq("COMPLETED")].copy()
    rows: list[dict[str, object]] = []
    primary_specs = {
        "candidate_window_days": config["cohort"]["primary_candidate_window_days"],
        "minimum_impressions": config["decision_cell"]["minimum_impressions"],
        "top_k": config["ranking"]["primary_top_k"],
        "time_decay_half_life_days": config["routes"]["time_decay"]["half_life_days"],
    }
    for (dimension, record_type), group in completed.groupby(
        ["targeted_dimension", "record_type"], sort=False, dropna=False
    ):
        allocation = pd.to_numeric(group.get("allocation_tv"), errors="coerce").dropna()
        kendall = pd.to_numeric(group.get("kendall_tau_b"), errors="coerce").dropna()
        overlap = pd.to_numeric(group.get("top_k_overlap"), errors="coerce").dropna()
        alternatives = sorted({str(value) for value in group["targeted_value"].dropna()})
        rows.append(
            {
                "dimension": dimension,
                "primary_specification": primary_specs.get(str(dimension)),
                "alternative_specification": "|".join(alternatives),
                "comparison_group": record_type,
                "allocation_tv_min": float(allocation.min()) if len(allocation) else np.nan,
                "allocation_tv_max": float(allocation.max()) if len(allocation) else np.nan,
                "kendall_tau_b_min": float(kendall.min()) if len(kendall) else np.nan,
                "kendall_tau_b_max": float(kendall.max()) if len(kendall) else np.nan,
                "top_k_overlap_min": float(overlap.min()) if len(overlap) else np.nan,
                "top_k_overlap_max": float(overlap.max()) if len(overlap) else np.nan,
                "qualitative_conclusion_preserved": bool(
                    (allocation.gt(0).any() if len(allocation) else False)
                    or (kendall.lt(1).any() if len(kendall) else False)
                ),
            }
        )
    return pd.DataFrame(rows)
