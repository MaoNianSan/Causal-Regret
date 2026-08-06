from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from cohort import CohortBuildResult, build_primary_cohort
from contracts import DataContractError, ScientificInvariantError
from metrics import compute_primary_metrics
from routes import build_attribution_routes

from .common import metric_rows, restrict_cohort


def run_candidate_window(
    *,
    prepared_candidates: pd.DataFrame,
    impression_counts: pd.DataFrame,
    primary_cohort: CohortBuildResult,
    config: dict[str, Any],
    primary_top_k: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    primary_window = int(config["cohort"]["primary_candidate_window_days"])
    window_values = [primary_window] + [
        int(value) for value in config["cohort"].get("robustness_candidate_window_days", [])
    ]
    window_cohorts: dict[int, CohortBuildResult] = {primary_window: primary_cohort}
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
    if len(window_cohorts) < 2:
        return records
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
                metric_rows(
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
            restricted = restrict_cohort(cohort, common_window_ids)
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
    return records
