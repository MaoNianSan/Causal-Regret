from __future__ import annotations

from typing import Any

from ..cohort import CohortBuildResult
from ..metrics import MetricResult, compute_targeted_top_k_metrics


def run_ranking_depth(
    primary_cohort: CohortBuildResult,
    primary_metrics: MetricResult,
    config: dict[str, Any],
) -> list[dict[str, object]]:
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
    return top_k.to_dict(orient="records")
