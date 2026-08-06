from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..cohort import CohortBuildResult
from ..metrics import compute_primary_metrics
from ..routes import build_attribution_routes

from .common import metric_rows


def run_decay_half_life(
    primary_cohort: CohortBuildResult,
    config: dict[str, Any],
    *,
    primary_top_k: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    half_lives = [
        float(config["routes"]["time_decay"]["half_life_days"]),
        *[
            float(value)
            for value in config["routes"]["time_decay"].get("robustness_half_life_days", [])
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
            metric_rows(
                metrics,
                dimension="time_decay_half_life_days",
                value=half_life,
                cohort=primary_cohort,
            )
        )
    return records
