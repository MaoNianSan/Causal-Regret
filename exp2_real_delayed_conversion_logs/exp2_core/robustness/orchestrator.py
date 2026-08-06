from __future__ import annotations

from typing import Any

import pandas as pd

from cohort import CohortBuildResult
from metrics import MetricResult

from .candidate_window import run_candidate_window
from .decay_half_life import run_decay_half_life
from .ranking_depth import run_ranking_depth
from .summary import build_robustness_summary
from .support_threshold import run_support_threshold


def run_targeted_analyses(
    *,
    prepared_candidates: pd.DataFrame,
    impression_counts: pd.DataFrame,
    primary_cohort: CohortBuildResult,
    primary_metrics: MetricResult,
    config: dict[str, Any],
    mode: str,
) -> pd.DataFrame:
    records = run_ranking_depth(primary_cohort, primary_metrics, config)
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
    records.extend(
        run_candidate_window(
            prepared_candidates=prepared_candidates,
            impression_counts=impression_counts,
            primary_cohort=primary_cohort,
            config=config,
            primary_top_k=primary_top_k,
        )
    )
    records.extend(run_decay_half_life(primary_cohort, config, primary_top_k=primary_top_k))
    records.extend(
        run_support_threshold(
            prepared_candidates=prepared_candidates,
            impression_counts=impression_counts,
            config=config,
            primary_top_k=primary_top_k,
        )
    )
    return pd.DataFrame(records)


__all__ = ["build_robustness_summary", "run_targeted_analyses"]
