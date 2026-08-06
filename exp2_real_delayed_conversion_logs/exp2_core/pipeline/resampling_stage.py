from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..cohort import CohortBuildResult
from ..raw_data import write_frame, write_json
from ..resampling import (
    BootstrapResult,
    attach_bootstrap_intervals,
    build_bootstrap_bias_audit,
    run_uid_cluster_bootstrap,
)
from ..routes import RouteBuildResult
from .context import RunContext, write_csv
from .metric_stage import MetricStageResult


@dataclass(frozen=True)
class ResamplingStageResult:
    bootstrap: BootstrapResult
    arrival: pd.DataFrame
    pairwise: pd.DataFrame
    bias_audit: dict


def run_resampling_stage(
    context: RunContext,
    cohort: CohortBuildResult,
    routes: RouteBuildResult,
    metrics: MetricStageResult,
    *,
    n_bootstrap: int | None,
    n_jobs: str | int | None,
) -> ResamplingStageResult:
    bootstrap = run_uid_cluster_bootstrap(
        routes.assignments,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        context.config,
        mode=context.mode,
        metric_states=metrics.point.kendall_metric_states,
        n_bootstrap_override=n_bootstrap,
        n_jobs_override=n_jobs,
        progress=context.config["runtime"].get("progress_mode", "normal") != "quiet",
    )
    write_frame(bootstrap.draws, context.paths.derived / "bootstrap_draws", table_format=context.table_format)
    write_json(bootstrap.audit, context.paths.audit / "resampling_audit.json")
    arrival, pairwise = attach_bootstrap_intervals(
        metrics.point.arrival_displacement,
        metrics.point.source_route_pairwise,
        bootstrap,
    )
    write_csv(arrival, context.paths.derived / "arrival_displacement.csv")
    write_csv(pairwise, context.paths.derived / "source_route_pairwise.csv")
    write_csv(
        pd.concat(
            [
                arrival.assign(comparison_group="source_vs_arrival_anchor", route_left="arrival_time_accounting_anchor", route_right=arrival["route_id"]),
                pairwise.assign(comparison_group="source_route_pair"),
            ],
            ignore_index=True,
            sort=False,
        ),
        context.paths.derived / "primary_comparisons.csv",
    )
    bias_audit = build_bootstrap_bias_audit(arrival, pairwise)
    write_json(bias_audit, context.paths.audit / "bootstrap_bias_audit.json")
    print(f"      Replicates: {bootstrap.audit['resampling_repetitions']:,}")
    print(f"      Resampling-range diagnostics: {bias_audit['full_sample_outside_resampling_range_count']:,}")
    print("      Status: PASS")
    return ResamplingStageResult(
        bootstrap=bootstrap,
        arrival=arrival,
        pairwise=pairwise,
        bias_audit=bias_audit,
    )
