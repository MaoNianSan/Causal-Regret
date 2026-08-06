"""Finalize run manifests, readiness fields, and public status output."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import ExperimentConfig
from pipeline_contract import contract_hash_fields
from run_reporting import (
    full_design_support_ready,
    readiness_fields,
    scientific_uncertainty_status,
    synchronize_run_outputs,
)
from utilities import build_artifact_manifest


def finalize_run(
    output_dir: Path,
    run_manifest: dict[str, object],
    design,
    run_tier: str,
    bootstrap_diagnostics: dict[str, object],
    cfg: ExperimentConfig,
    *,
    history_target_audit: dict[str, object] | None = None,
    evaluation_target_audit: dict[str, object] | None = None,
    full_design_preflight: dict[str, object] | None = None,
) -> None:
    support = pd.read_csv(output_dir / "tables" / "exp3_support_coverage.csv").iloc[0]
    if run_tier == "full":
        scientific_status = "PENDING_SELF_CHECK"
    elif bool(run_manifest.get("synthetic_fixture", False)):
        scientific_status = "NOT_EVALUATED_FAST_FIXTURE"
    else:
        scientific_status = "NOT_EVALUATED_FAST_REAL"
    selection = json.loads(
        (output_dir / "metadata" / "exp3_ridge_selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    run_manifest.update(
        {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_execution_status": "PASS",
            "independent_self_check_status": "NOT_RUN",
            "final_engineering_status": "PENDING_SELF_CHECK",
            "engineering_status": "PENDING_SELF_CHECK",
            "scientific_status": scientific_status,
            "scientific_contract_status": "PENDING_SELF_CHECK",
            "pipeline_scientific_support_status": str(support["scientific_support_status"]),
            "paper_result": False,
            "selected_user_group_count": design.user_group_count,
            "support_min_events_per_fold": design.support_min_events_per_fold,
            "near_tie_threshold": design.near_tie_threshold,
            "candidate_action_count": len(design.candidate_actions),
            "selected_ridge_alpha": selection["selected_alpha"],
            "bootstrap_repetitions": cfg.bootstrap_repetitions(run_tier),
            "valid_bootstrap_fraction": bootstrap_diagnostics["valid_bootstrap_fraction"],
            **contract_hash_fields(output_dir),
        }
    )
    if history_target_audit is not None:
        run_manifest["history_target_audit"] = history_target_audit
    if evaluation_target_audit is not None:
        run_manifest["evaluation_target_audit"] = evaluation_target_audit
    split = json.loads(
        (output_dir / "design" / "exp3_split_manifest.json").read_text(encoding="utf-8")
    )
    quarantine_count = int(split.get("history_events_excluded_before_start", 0)) + int(
        split.get("evaluation_events_excluded_before_boundary", 0)
    )
    run_manifest.update(
        {
            "input_boundary_status": (
                "PASS_WITH_BOUNDARY_QUARANTINE" if quarantine_count else "PASS"
            ),
            "input_audit_status": "PENDING_SELF_CHECK",
            "boundary_quarantine_event_count": quarantine_count,
            "resampling_range_method": bootstrap_diagnostics.get("displayed_range_method"),
            "resampling_output_role": bootstrap_diagnostics.get("resampling_output_role"),
            "formal_ci_validated": bool(bootstrap_diagnostics.get("formal_ci_validated", False)),
            "ridge_refit_in_resampling": False,
            "resampling_centering_status": bootstrap_diagnostics.get(
                "resampling_centering_status"
            ),
            "scientific_uncertainty_status": scientific_uncertainty_status(
                bootstrap_diagnostics
            ),
            "figure_data_contract_status": "PENDING_SELF_CHECK",
            "archival_integrity_check_status": "NOT_RUN",
            "artifact_manifest_status": "PASS",
        }
    )
    if full_design_preflight is not None:
        run_manifest["full_design_support_preflight"] = full_design_preflight
        run_manifest["full_design_support_ready"] = full_design_support_ready(full_design_preflight)
    run_manifest.update(readiness_fields(run_manifest))
    synchronize_run_outputs(output_dir, run_manifest)
    build_artifact_manifest(output_dir)
    print("\nEXP3 RUN SUMMARY")
    print("-" * 58)
    print(f"Run ID                    {run_manifest['run_id']}")
    print(f"Output directory          {output_dir}")
    print(f"Run tier                  {run_tier}")
    print("Pipeline execution        PASS")
    print("Final engineering         PENDING_SELF_CHECK")
    print(f"Scientific status         {scientific_status}")
    print(f"Selected Ridge alpha      {selection['selected_alpha']}")
    print(f"Action coverage           {float(support.action_coverage):.3f}")
    print(f"Reference-pair coverage   {float(support.reference_pair_coverage):.3f}")
    print(f"Audit-unit coverage       {float(support.audit_unit_coverage):.3f}")
    print("-" * 58)


_finalize_run = finalize_run
