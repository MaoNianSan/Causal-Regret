"""Promotion lineage tests: legacy refusal, fresh acceptance, tamper rejection."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from exp4.configuration.schema import MAIN_FIGURE_ID, MAIN_TABLE_ID, RESULT_SCHEMA
from exp4.outputs.run_lineage import RunLineage, fresh_lineage, write_run_lineage
from exp4.outputs.writers import (
    SOURCE_HASH_ALGORITHM_VERSION,
    compute_exp4_source_code_hash,
    compute_stage_source_hashes,
    config_hash,
    git_commit,
    write_json,
)
from exp4.reporting.tables import _write_table, select_main_calibration_rows
from exp4.validation.run_provenance import write_stage_provenance_record
from promote_results import validate_paper_promotion

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DERIVED_PATHS = (
    "derived/module_a/exp4_module_a_seed_level.parquet",
    "derived/module_a/exp4_module_a_population_summary.csv",
    "derived/module_a/exp4_module_a_paired_contrasts.csv",
    "derived/module_a/exp4_module_a_seed_direction_summary.csv",
    "derived/module_b/exp4_module_b_audit_unit_level.parquet",
    "derived/module_b/exp4_module_b_condition_level.parquet",
    "derived/module_b/exp4_module_b_audit_performance.csv",
    "derived/module_b/exp4_module_b_weight_diagnostics.csv",
    "derived/module_b/exp4_module_b_selection_diagnostics.csv",
    "derived/module_c/exp4_module_c_replication_level.parquet",
    "derived/module_c/exp4_module_c_control_summary.csv",
    "derived/module_c/exp4_module_c_parameter_recovery.csv",
    "derived/module_c/exp4_module_c_correspondence_checks.csv",
    "derived/calibration/exp4_proxy_route_calibration.json",
    "derived/calibration/exp4_delay_prior.csv",
    "derived/calibration/exp4_proxy_distance_summary.csv",
)


def _control_summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "control_id": ["affine_linked", "blocked_correspondence_destroyed"],
            "control_display_name": [
                "Affine-linked control",
                "Temporally blocked correspondence-destroyed control",
            ],
            "analysis_tier": ["primary", "primary"],
            "correspondence_status": [
                "preserved by construction",
                "destroyed within temporal blocks",
            ],
            "raw_defect": [0.5, 1.4],
            "oof_calibrated_defect": [0.1, 0.9],
            "recoverability": [0.7, 0.4],
            "estimability_rate": [1.0, 1.0],
        }
    )


def _make_empty_parquet(path: Path) -> None:
    pd.DataFrame({"__empty__": []}).to_parquet(path, index=False)


def _build_fresh_full_run(
    run_dir: Path,
    base_dir: Path,
    lineage: RunLineage | None = None,
    calibration_hash: str = "c" * 64,
    source_unchanged: bool = True,
) -> dict[str, object]:
    current_source_hash = compute_exp4_source_code_hash(base_dir)
    current_config_hash = config_hash()
    current_commit = git_commit(base_dir)
    stage_hashes = compute_stage_source_hashes(base_dir)
    run_config = {
        "run_id": "full_fixture",
        "run_tier": "full",
        "result_schema": RESULT_SCHEMA,
        "paper_result": False,
        "is_paper_eligible": False,
        "source_code_hash": current_source_hash,
        "config_hash": current_config_hash,
        "code_commit": current_commit,
        "source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "formal_full_clean_worktree_required": True,
        "exp4_worktree_clean_at_start": True,
        "simulation_stage_hash": stage_hashes["simulation_source_hash"],
        "aggregation_stage_hash": stage_hashes["aggregation_source_hash"],
        "reporting_stage_hash": stage_hashes["reporting_source_hash"],
        "validation_stage_hash": stage_hashes["validation_source_hash"],
        "generated_at": "2026-08-06T00:00:00+00:00",
    }
    (run_dir / "logs").mkdir(parents=True)
    write_json(run_config, run_dir / "logs" / "run_config.json")

    if lineage is None:
        lineage = fresh_lineage("full_fixture", "full", current_commit, True)
    write_run_lineage(run_dir, lineage)

    for name, payload in (
        ("exp4_engineering_checks.json", {"status": "PASS", "checks": []}),
        ("exp4_scientific_checks.json", {"status": "PASS", "checks": []}),
    ):
        (run_dir / "checks").mkdir(parents=True, exist_ok=True)
        (run_dir / "checks" / name).write_text(json.dumps(payload), encoding="utf-8")

    for relative in REQUIRED_DERIVED_PATHS:
        path = run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith(".parquet"):
            _make_empty_parquet(path)
        elif relative == "derived/calibration/exp4_proxy_route_calibration.json":
            write_json({"calibration_hash": calibration_hash}, path)
        elif relative == "derived/module_a/exp4_module_a_paired_contrasts.csv":
            contrasts = pd.DataFrame(
                {
                    "contrast_id": ["primary"],
                    "is_primary_contrast": [True],
                    "monte_carlo_precision_gate": ["PASS"],
                }
            )
            contrasts.to_csv(path, index=False)
        elif relative == "derived/module_c/exp4_module_c_control_summary.csv":
            _control_summary().to_csv(path, index=False)
        else:
            path.write_text("", encoding="utf-8")

    (run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv").parent.mkdir(
        parents=True, exist_ok=True
    )
    main = select_main_calibration_rows(_control_summary())
    (run_dir / "tables").mkdir(parents=True, exist_ok=True)
    _write_table(main, run_dir / "tables" / MAIN_TABLE_ID, "caption", "label")
    (run_dir / "figures" / "pdf").mkdir(parents=True)
    (run_dir / "figures" / "pdf" / f"{MAIN_FIGURE_ID}.pdf").write_bytes(b"x")
    (run_dir / "figures" / "png").mkdir(parents=True)
    (run_dir / "figures" / "png" / f"{MAIN_FIGURE_ID}.png").write_bytes(b"x")
    (run_dir / "figures" / "data").mkdir(parents=True)
    (run_dir / "figures" / "data" / f"{MAIN_FIGURE_ID}_data.csv").write_text("x\n", encoding="utf-8")
    (run_dir / "figures" / "metadata").mkdir(parents=True)
    (run_dir / "figures" / "metadata" / f"{MAIN_FIGURE_ID}_metadata.json").write_text(
        json.dumps({"source_file_hashes": {}}), encoding="utf-8"
    )

    # Empty raw path manifests (satisfy artifact-completeness for the audit).
    for name in ("exp4_module_a_path_manifest.csv", "exp4_module_bc_path_manifest.csv"):
        pd.DataFrame(columns=["trajectory_file", "route_map_file"]).to_csv(
            run_dir / "logs" / name, index=False
        )

    write_stage_provenance_record(
        run_dir,
        base_dir,
        lineage=lineage,
        calibration_hash=calibration_hash,
        source_unchanged_during_run=source_unchanged,
    )
    return run_config


def test_promotion_rejects_legacy_full_without_lineage(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT)
    # Remove the lineage artifact to emulate a legacy full run.
    (run_dir / "logs" / "exp4_run_lineage.json").unlink()
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["run_lineage_present"] is False
    assert result["checks"]["run_lineage_valid"] is False
    assert result["checks"]["simulation_provenance_verified"] is False
    assert result["status"] == "FAIL"


def test_promotion_accepts_valid_fresh_full_fixture(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    failed = {name: value for name, value in result["checks"].items() if not value}
    assert result["status"] == "PASS", f"failed gates: {failed}"
    assert result["provenance"]["simulation_execution_mode"] == "FRESH"
    assert result["provenance"]["full_simulation_reuse_eligibility"] == "ELIGIBLE"
    assert result["checks"]["formal_full_started_clean"] is True
    assert result["checks"]["source_unchanged_during_run"] is True


def test_promotion_rejects_fresh_full_with_wrong_stage_hash(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT)
    stage_path = run_dir / "logs" / "exp4_stage_provenance.json"
    payload = json.loads(stage_path.read_text(encoding="utf-8"))
    payload["stages"]["reporting"]["source_hash"] = "0" * 64
    write_json(payload, stage_path)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["reporting_stage_hash_match"] is False
    assert result["checks"]["downstream_provenance_verified"] is False
    assert result["status"] == "FAIL"


def test_promotion_rejects_changed_simulation_stage(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT)
    stage_path = run_dir / "logs" / "exp4_stage_provenance.json"
    payload = json.loads(stage_path.read_text(encoding="utf-8"))
    payload["stages"]["simulation"]["source_hash"] = "0" * 64
    write_json(payload, stage_path)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["simulation_stage_hash_match"] is False
    assert result["checks"]["simulation_provenance_verified"] is False
    assert result["status"] == "FAIL"


def test_promotion_rejects_fake_reused_lineage_without_source_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    fake_reused = RunLineage(
        run_id="full_fixture",
        run_tier="full",
        simulation_execution_mode="REUSED",
        simulation_source_run_id=None,
        downstream_execution_mode="REBUILT_FROM_REUSED_SIMULATION",
        downstream_source_run_id=None,
        created_from_commit=git_commit(ROOT),
        exp4_worktree_clean_at_start=True,
    )
    _build_fresh_full_run(run_dir, ROOT, lineage=fake_reused)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["run_lineage_valid"] is False
    assert result["status"] == "FAIL"


def test_promotion_rejects_unverified_reused_lineage_without_reconciliation(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    reused = RunLineage(
        run_id="full_fixture",
        run_tier="full",
        simulation_execution_mode="REUSED",
        simulation_source_run_id="full_source_1",
        downstream_execution_mode="REBUILT_FROM_REUSED_SIMULATION",
        downstream_source_run_id="full_source_1",
        created_from_commit=git_commit(ROOT),
        exp4_worktree_clean_at_start=True,
    )
    _build_fresh_full_run(run_dir, ROOT, lineage=reused)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    # Structurally valid REUSED lineage, but no reconciliation artifact linking
    # the raw simulation to the source run: simulation provenance unverified.
    assert result["checks"]["run_lineage_valid"] is True
    assert result["checks"]["simulation_provenance_verified"] is False
    assert result["status"] == "FAIL"


def test_promotion_rejects_missing_stage_record(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT)
    (run_dir / "logs" / "exp4_stage_provenance.json").unlink()
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["simulation_stage_record_present"] is False
    assert result["checks"]["reporting_stage_record_present"] is False
    assert result["checks"]["source_unchanged_during_run"] is False
    assert result["status"] == "FAIL"


def test_promotion_rejects_source_changed_during_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _build_fresh_full_run(run_dir, ROOT, source_unchanged=False)
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["source_unchanged_during_run"] is False
    assert result["status"] == "FAIL"
