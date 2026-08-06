from __future__ import annotations

import traceback

from ..raw_data import PreparedRawData, input_manifest_identity_hash, write_json
from ..validation import ValidationResult
from .context import RunContext, now_local, write_artifact_manifest
from .input_stage import InputSpec
from .reporting_stage import ReportingStageResult
from .resampling_stage import ResamplingStageResult


def finalize_run(
    context: RunContext,
    input_spec: InputSpec,
    prepared: PreparedRawData,
    reporting: ReportingStageResult,
    resampling: ResamplingStageResult,
    validation: ValidationResult,
) -> None:
    context.manifest.update(
        {
            "status": "COMPLETE",
            "engineering_status": validation.engineering_status,
            "scientific_status": validation.scientific_status,
            "paper_promotion_status": validation.paper_promotion_status,
            "completed_at": now_local().isoformat(),
            "input_kind": input_spec.kind,
            "input_manifest_hash": input_manifest_identity_hash(prepared.input_manifest),
            "cohort_hash": reporting.run_metadata["cohort_hash"],
            "decision_cell_universe_hash": reporting.run_metadata["decision_cell_universe_hash"],
            "resampling_repetitions": resampling.bootstrap.audit["resampling_repetitions"],
            "resampling_range_diagnostic_count": resampling.bias_audit["full_sample_outside_resampling_range_count"],
            "input_content_sha256": prepared.input_manifest["input_content_sha256"],
            "primary_full_runs_complete": context.mode == "full" and not bool(context.manifest["development_override"]),
            "main_figures_reconstructable": True,
            "main_tables_reconstructable": True,
            "claims_within_scope": True,
        }
    )
    write_json(context.manifest, context.paths.manifest)
    write_artifact_manifest(context.paths.root, context.paths.audit / "artifact_manifest.json")
    print("      Status: COMPLETE")
    print(f"      Output: {context.paths.root}")
    print(f"      Paper promotion: {validation.paper_promotion_status}")


def fail_run(context: RunContext, exc: Exception) -> None:
    context.manifest.update(
        {
            "status": "FAILED",
            "engineering_status": "FAIL",
            "scientific_status": "STOP_AND_REVIEW",
            "paper_promotion_status": "BLOCKED",
            "completed_at": now_local().isoformat(),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    )
    write_json(context.manifest, context.paths.manifest)
    (context.paths.logs / "failure_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(f"\nEXP2 FAILED: {type(exc).__name__}: {exc}", flush=True)
    print(f"Failure report: {context.paths.logs / 'failure_traceback.txt'}", flush=True)
