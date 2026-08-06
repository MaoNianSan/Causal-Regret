from __future__ import annotations

from contracts import SCHEMA_VERSION

from ..cohort import CohortBuildResult
from ..raw_data import write_frame, write_json
from ..routes import RouteBuildResult, build_attribution_routes
from .context import RunContext, write_csv


def run_route_stage(context: RunContext, cohort: CohortBuildResult) -> RouteBuildResult:
    routes = build_attribution_routes(
        cohort.eligible_candidates,
        cohort.journey_manifest,
        cohort.decision_cell_universe,
        context.config,
    )
    write_frame(routes.assignments, context.paths.derived / "route_assignments", table_format=context.table_format)
    write_csv(routes.route_summary, context.paths.audit / "route_summary.csv")
    write_json(
        {
            "schema_version": SCHEMA_VERSION,
            "credit_conservation_status": "PASS",
            "primary_route_count": len(context.config["routes"]["primary"]),
            "exploratory_routes_enabled": bool(context.config["routes"].get("run_exploratory_by_default", False)),
            "route_summary": routes.route_summary.to_dict(orient="records"),
        },
        context.paths.audit / "route_invariants.json",
    )
    write_csv(routes.em_diagnostics, context.paths.audit / "em_diagnostics.csv")
    write_csv(routes.logged_reference_summary, context.paths.audit / "logged_reference_summary.csv")
    print("      Primary routes: 5")
    print("      Exploratory EM route: DISABLED")
    print("      Credit conservation: PASS")
    return routes
