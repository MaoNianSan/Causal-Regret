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
from exp4.outputs.run_lineage import fresh_lineage, write_run_lineage
from exp4.outputs.writers import (
    RunContext,
    compute_exp4_source_code_hash,
    compute_stage_source_hashes,
    git_commit,
    write_json,
)
from exp4.reporting.figures_appendix import plot_appendix_figures
from exp4.reporting.figures_main import plot_main_figure
from exp4.reporting.run_summary import write_run_summary
from exp4.reporting.tables import make_tables
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.validation.runner import validate_run
from exp4.validation.run_provenance import write_stage_provenance_record
from exp4.validation.static_checks import run_static_checks

SOURCE_CHANGED_MARKER = "logs/exp4_source_changed_marker.json"


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
    context: RunContext,
    engineering: dict[str, object],
    scientific: dict[str, object],
    source_changed: bool = False,
) -> dict[str, object]:
    engineering_status = "FAIL" if source_changed else engineering["status"]
    status = {
        "run_id": context.run_id,
        "run_tier": context.run_tier,
        "run_dir": str(context.run_dir),
        "result_schema": RESULT_SCHEMA,
        "engineering_status": engineering_status,
        "scientific_status": scientific["status"],
        "paper_promotion": "NOT_RUN",
        "paper_result": False,
        "source_changed_during_run": source_changed,
    }
    write_json(status, context.run_dir / "logs" / "exp4_result_status.json")
    return status


def _verify_simulation_stage_unchanged(
    context: RunContext, base_dir: Path
) -> bool:
    frozen = (context.stage_source_hashes or {}).get("simulation_source_hash", "")
    current = compute_stage_source_hashes(base_dir).get("simulation_source_hash", "")
    unchanged = bool(frozen) and frozen == current
    if not unchanged:
        write_json(
            {
                "source_changed_during_run": True,
                "detected_at_stage": "simulation",
                "frozen_simulation_stage_hash": frozen,
                "current_simulation_stage_hash": current,
            },
            context.run_dir / SOURCE_CHANGED_MARKER,
        )
    return unchanged


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
    # Freeze the simulation stage hash after the raw simulation; a change here
    # means the raw simulation and the remaining stages were built from
    # different sources, so the run is not internally consistent.
    if not _verify_simulation_stage_unchanged(context, base_dir):
        raise RuntimeError(
            "SOURCE_CHANGED_DURING_RUN=FAIL: simulation source changed during run"
        )
    aggregate_existing_run(context, calibration)
    render_existing_run(context)
    engineering, scientific = validate_run(context.run_dir)
    # End-of-run source-consistency check: the complete source hash and git
    # commit must still match the values frozen when the run was created.
    source_changed = (
        compute_exp4_source_code_hash(base_dir) != context.source_code_hash
        or git_commit(base_dir) != context.code_commit
    )
    if source_changed:
        write_json(
            {
                "source_changed_during_run": True,
                "detected_at_stage": "final",
                "frozen_complete_source_hash": context.source_code_hash,
                "current_complete_source_hash": compute_exp4_source_code_hash(base_dir),
                "frozen_git_commit": context.code_commit,
                "current_git_commit": git_commit(base_dir),
            },
            context.run_dir / SOURCE_CHANGED_MARKER,
        )
    lineage = fresh_lineage(
        context.run_id,
        context.run_tier,
        context.code_commit,
        context.exp4_worktree_clean_at_start,
    )
    write_run_lineage(context.run_dir, lineage)
    write_stage_provenance_record(
        context.run_dir,
        base_dir,
        lineage=lineage,
        calibration_hash=calibration.calibration_hash,
        source_unchanged_during_run=not source_changed,
    )
    write_run_summary(context.run_dir)
    status = _write_final_status(
        context, engineering, scientific, source_changed=source_changed
    )
    write_output_manifest(context.run_dir)
    return status


__all__ = [
    "_run_module_bc_replication",
    "aggregate_existing_run",
    "render_existing_run",
    "run_pipeline",
]
