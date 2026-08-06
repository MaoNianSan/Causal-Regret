from __future__ import annotations

from ..cohort import CohortBuildResult
from ..raw_data import write_json
from ..routes import RouteBuildResult
from ..validation import ValidationResult, validate_run
from .context import RunContext
from .metric_stage import MetricStageResult
from .resampling_stage import ResamplingStageResult


def run_validation_stage(
    context: RunContext,
    cohort: CohortBuildResult,
    routes: RouteBuildResult,
    metrics: MetricStageResult,
    resampling: ResamplingStageResult,
) -> ValidationResult:
    validation = validate_run(
        context.config,
        journey_manifest=cohort.journey_manifest,
        decision_cells=cohort.decision_cell_universe,
        assignments=routes.assignments,
        route_allocations=metrics.point.route_allocations,
        arrival_displacement=resampling.arrival,
        source_route_pairwise=resampling.pairwise,
        bootstrap_draws=resampling.bootstrap.draws,
        mode=context.mode,
        expected_bootstrap_repetitions=int(resampling.bootstrap.audit["resampling_repetitions"]),
        bootstrap_audit=resampling.bootstrap.audit,
        development_override=bool(context.manifest["development_override"]),
        cohort_flow=cohort.cohort_flow,
    )
    write_json(
        {
            "engineering_status": validation.engineering_status,
            "scientific_status": validation.scientific_status,
            "paper_promotion_status": validation.paper_promotion_status,
            "checks": validation.checks,
        },
        context.paths.audit / "scientific_validation.json",
    )
    print(f"      Engineering status: {validation.engineering_status}")
    print(f"      Scientific status: {validation.scientific_status}")
    return validation
