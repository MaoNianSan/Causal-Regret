"""High-level Exp4 v2 pipeline composition."""

from __future__ import annotations

from pathlib import Path

from exp4.configuration.schema import RESULT_SCHEMA
from exp4.execution.aggregation_stage import aggregate_existing_run
from exp4.execution.calibration_stage import run_calibration_stage
from exp4.execution.module_a_stage import run_module_a_stage
from exp4.execution.module_bc_stage import (
    run_module_bc_replication as _run_module_bc_replication,
    run_module_bc_stage,
)
from exp4.outputs.manifests import write_output_manifest, write_stage_manifest
from exp4.outputs.writers import RunContext, write_json
from exp4.reporting.figures_appendix import plot_appendix_figures
from exp4.reporting.figures_main import plot_main_figure
from exp4.reporting.run_summary import write_run_summary
from exp4.reporting.tables import make_tables
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.validation.runner import validate_run
from exp4.validation.run_provenance import write_stage_provenance_record
from exp4.validation.static_checks import run_static_checks


def render_existing_run(context: RunContext) -> list[Path]:
    plot_main_figure(context.run_dir)
    plot_appendix_figures(context.run_dir)
    make_tables(context.run_dir)
    artifacts = list((context.run_dir / "figures").rglob("*"))
    artifacts.extend((context.run_dir / "tables").glob("*"))
    files = [path for path in artifacts if path.is_file()]
    write_stage_manifest(context.run_dir, "reporting", len(files), files)
    return files


def _write_final_status(
    context: RunContext, engineering: dict[str, object], scientific: dict[str, object]
) -> dict[str, object]:
    status = {
        "run_id": context.run_id,
        "run_tier": context.run_tier,
        "run_dir": str(context.run_dir),
        "result_schema": RESULT_SCHEMA,
        "engineering_status": engineering["status"],
        "scientific_status": scientific["status"],
        "paper_promotion": "NOT_RUN",
        "paper_result": False,
    }
    write_json(status, context.run_dir / "logs" / "exp4_result_status.json")
    return status


def run_pipeline(
    context: RunContext,
    base_dir: Path,
    resume: bool = False,
) -> dict[str, object]:
    static = run_static_checks(base_dir)
    write_json(static, context.run_dir / "checks" / "exp4_static_code_checks.json")
    if static["status"] != "PASS":
        raise RuntimeError("Static Exp4 v2 code contract failed")
    calibration: ProxyRouteCalibration = run_calibration_stage(context, resume)
    run_module_a_stage(context, calibration, resume)
    run_module_bc_stage(context, calibration, resume)
    aggregate_existing_run(context, calibration)
    render_existing_run(context)
    engineering, scientific = validate_run(context.run_dir)
    write_run_summary(context.run_dir)
    write_stage_provenance_record(context.run_dir, base_dir)
    status = _write_final_status(context, engineering, scientific)
    write_output_manifest(context.run_dir)
    return status


__all__ = [
    "_run_module_bc_replication",
    "aggregate_existing_run",
    "render_existing_run",
    "run_pipeline",
]
