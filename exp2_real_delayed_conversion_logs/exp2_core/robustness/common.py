from __future__ import annotations

import pandas as pd

from cohort import CohortBuildResult
from metrics import MetricResult


def restrict_cohort(cohort: CohortBuildResult, common_ids: set[str]) -> CohortBuildResult:
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


def metric_rows(
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
