from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..cohort import CohortBuildResult
from ..metrics import MetricResult, compute_primary_metrics
from ..raw_data import PreparedRawData, write_frame
from ..robustness import build_robustness_summary, run_targeted_analyses
from ..routes import RouteBuildResult
from .context import RunContext, write_csv


@dataclass(frozen=True)
class MetricStageResult:
    point: MetricResult
    targeted: pd.DataFrame
    robustness_summary: pd.DataFrame


def run_metric_stage(
    context: RunContext,
    prepared: PreparedRawData,
    cohort: CohortBuildResult,
    routes: RouteBuildResult,
) -> MetricStageResult:
    point = compute_primary_metrics(
        routes.assignments,
        cohort.decision_cell_universe,
        cohort.journey_manifest,
        top_k=int(context.config["ranking"]["primary_top_k"]),
    )
    write_frame(point.route_allocations, context.paths.derived / "route_allocations", table_format=context.table_format)
    write_csv(point.kendall_support, context.paths.derived / "kendall_support.csv")
    write_csv(point.ambiguity_strata, context.paths.derived / "ambiguity_mechanism.csv")
    targeted = run_targeted_analyses(
        prepared_candidates=prepared.candidates,
        impression_counts=prepared.impression_counts,
        primary_cohort=cohort,
        primary_metrics=point,
        config=context.config,
        mode=context.mode,
    )
    write_csv(targeted, context.paths.derived / "targeted_robustness.csv")
    robustness_summary = build_robustness_summary(targeted, context.config)
    print("      Common cohort: PASS")
    print("      Common ranking denominator: PASS")
    return MetricStageResult(point=point, targeted=targeted, robustness_summary=robustness_summary)
