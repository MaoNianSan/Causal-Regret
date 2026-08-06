from __future__ import annotations

from pathlib import Path

from .artifact_stage import fail_run, finalize_run
from .cohort_check import run_cohort_check
from .cohort_stage import run_cohort_stage
from .context import initialize_context, log_stage
from .input_stage import resolve_input, scan_input
from .metric_stage import run_metric_stage
from .reporting_stage import run_reporting_stage
from .resampling_stage import run_resampling_stage
from .route_stage import run_route_stage
from .validation_stage import run_validation_stage


def run(
    mode: str,
    *,
    config_path: str | Path | None = None,
    input_path: str | Path | None = None,
    n_bootstrap: int | None = None,
    n_jobs: str | int | None = None,
) -> int:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be 'fast' or 'full'.")
    context = initialize_context(
        mode,
        config_path=config_path,
        input_path=input_path,
        n_bootstrap=n_bootstrap,
        n_jobs=n_jobs,
    )
    print("EXP2 — Delayed-Conversion Attribution Sensitivity")
    print(f"Run tier: {mode.upper()}")
    print(f"Run ID: {context.run_id}")
    print(f"Large-table format: {context.table_format}")
    try:
        total_stages = 9
        log_stage(1, total_stages, "Validate configuration and resolve input")
        input_spec = resolve_input(context, input_path)
        log_stage(2, total_stages, "Scan raw log and construct route-independent candidates")
        prepared = scan_input(context, input_spec)
        log_stage(3, total_stages, "Build common journey cohort and decision-cell universe")
        cohort = run_cohort_stage(context, prepared)
        log_stage(4, total_stages, "Construct attribution routes")
        routes = run_route_stage(context, cohort)
        log_stage(5, total_stages, "Compute allocation, ranking, and ambiguity metrics")
        metrics = run_metric_stage(context, prepared, cohort, routes)
        log_stage(6, total_stages, "Run UID-cluster bootstrap")
        resampling = run_resampling_stage(
            context,
            cohort,
            routes,
            metrics,
            n_bootstrap=n_bootstrap,
            n_jobs=n_jobs,
        )
        log_stage(7, total_stages, "Generate manuscript figures and tables")
        reporting = run_reporting_stage(context, prepared, cohort, metrics, resampling)
        log_stage(8, total_stages, "Run engineering and scientific validation")
        validation = run_validation_stage(context, cohort, routes, metrics, resampling)
        log_stage(9, total_stages, "Finalize run manifest")
        finalize_run(context, input_spec, prepared, reporting, resampling, validation)
        return 0
    except Exception as exc:
        fail_run(context, exc)
        return 1


__all__ = ["run", "run_cohort_check"]
