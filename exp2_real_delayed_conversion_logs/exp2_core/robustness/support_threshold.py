from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from cohort import CohortBuildResult, build_primary_cohort
from contracts import DataContractError, ScientificInvariantError
from metrics import compute_primary_metrics
from routes import build_attribution_routes

from .common import metric_rows, restrict_cohort


def run_support_threshold(
    *,
    prepared_candidates: pd.DataFrame,
    impression_counts: pd.DataFrame,
    config: dict[str, Any],
    primary_top_k: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
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
    if not threshold_cohorts:
        return records
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
            restricted = restrict_cohort(cohort, common_threshold_ids)
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
                    metric_rows(
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
    return records
