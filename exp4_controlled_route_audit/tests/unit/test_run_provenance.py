"""Tests for stage-level provenance, reconciliation, and promotion gates."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from exp4.configuration.schema import MAIN_TABLE_ID
from exp4.outputs.writers import compute_exp4_source_code_hash, hash_files, source_code_hash
from exp4.reporting.tables import _write_table
from exp4.validation.run_provenance import (
    audit_run_provenance,
    compute_stage_source_hashes,
    write_provenance_reconciliation,
    write_stage_provenance_record,
)
from promote_results import validate_paper_promotion

ROOT = Path(__file__).resolve().parents[1]


def _make_minimal_exp4_package(tmp_path: Path) -> Path:
    base = tmp_path / "exp4"
    (base / "configuration").mkdir(parents=True)
    (base / "simulation").mkdir(parents=True)
    (base / "reporting").mkdir(parents=True)
    (base / "validation").mkdir(parents=True)
    (base / "configuration" / "__init__.py").write_text("", encoding="utf-8")
    (base / "configuration" / "parameters.py").write_text("FROZEN = 1\n", encoding="utf-8")
    (base / "simulation" / "__init__.py").write_text("", encoding="utf-8")
    (base / "simulation" / "trajectory.py").write_text("def sim():\n    return 1\n", encoding="utf-8")
    (base / "reporting" / "__init__.py").write_text("", encoding="utf-8")
    (base / "reporting" / "tables.py").write_text("def table():\n    return 1\n", encoding="utf-8")
    (base / "validation" / "__init__.py").write_text("", encoding="utf-8")
    (base / "validation" / "invariants.py").write_text("def check():\n    return True\n", encoding="utf-8")
    return tmp_path


def test_source_hash_function_is_shared_across_run_and_audit() -> None:
    # Run creation, provenance audit, and promotion all use the same canonical
    # source hash function over the same file set.
    assert compute_exp4_source_code_hash(ROOT) == source_code_hash(ROOT)
    expected = hash_files(list((ROOT / "exp4").rglob("*.py")))
    assert compute_exp4_source_code_hash(ROOT) == expected


def test_promotion_rejects_unverified_simulation_provenance(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "checks").mkdir(parents=True)
    (run_dir / "derived" / "module_a").mkdir(parents=True)
    (run_dir / "derived" / "module_c").mkdir(parents=True)
    (run_dir / "tables").mkdir(parents=True)
    (run_dir / "figures" / "pdf").mkdir(parents=True)
    (run_dir / "figures" / "data").mkdir(parents=True)
    (run_dir / "figures" / "metadata").mkdir(parents=True)
    run_config = {
        "run_id": "full_test",
        "run_tier": "full",
        "result_schema": "exp4_controlled_route_audit_v2",
        "paper_result": False,
        "source_code_hash": "0" * 64,
        "config_hash": "1" * 64,
        "code_commit": "test",
    }
    (run_dir / "logs" / "run_config.json").write_text(
        json.dumps(run_config), encoding="utf-8"
    )
    for name, payload in (
        ("exp4_engineering_checks.json", {"status": "PASS", "checks": []}),
        ("exp4_scientific_checks.json", {"status": "PASS", "checks": []}),
    ):
        (run_dir / "checks" / name).write_text(json.dumps(payload), encoding="utf-8")
    contrasts = pd.DataFrame(
        {
            "contrast_id": ["primary"],
            "is_primary_contrast": [True],
            "monte_carlo_precision_gate": ["PASS"],
        }
    )
    contrasts.to_csv(run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv", index=False)
    summary = pd.DataFrame(
        {
            "control_id": ["affine_linked", "blocked_correspondence_destroyed"],
            "control_display_name": ["Affine-linked control", "Temporally blocked correspondence-destroyed control"],
            "analysis_tier": ["primary", "primary"],
            "correspondence_status": ["preserved by construction", "destroyed within temporal blocks"],
            "raw_defect": [0.5, 1.4],
            "oof_calibrated_defect": [0.1, 0.9],
            "recoverability": [0.7, 0.4],
            "estimability_rate": [1.0, 1.0],
        }
    )
    summary.to_csv(run_dir / "derived" / "module_c" / "exp4_module_c_control_summary.csv", index=False)
    main = summary[["control_display_name", "correspondence_status", "raw_defect", "oof_calibrated_defect", "recoverability", "estimability_rate"]].rename(
        columns={
            "control_display_name": "Control",
            "correspondence_status": "Unit-level correspondence",
            "raw_defect": "Raw defect",
            "oof_calibrated_defect": "OOF calibrated defect",
            "recoverability": "Recoverability",
            "estimability_rate": "Estimability rate",
        }
    )
    _write_table(main, run_dir / "tables" / MAIN_TABLE_ID, "caption", "label")
    (run_dir / "figures" / "pdf" / "fig_exp4_route_alignment_and_audit_reliability.pdf").write_bytes(b"x")
    result = validate_paper_promotion(run_dir, approve_claims=True, base_dir=ROOT, dry_run=True)
    assert result["checks"]["simulation_provenance_verified"] is False
    assert result["checks"]["source_hash_algorithm_version_present"] is False
    assert result["status"] == "FAIL"


def test_reconciliation_does_not_overwrite_original_run_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    original = {
        "run_id": "full_x",
        "run_tier": "full",
        "source_code_hash": "abc",
        "config_hash": "def",
        "calibration_hash": "ghi",
        "code_commit": "old",
    }
    (run_dir / "logs" / "run_config.json").write_text(json.dumps(original), encoding="utf-8")
    write_provenance_reconciliation(run_dir, ROOT)
    after = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    assert after == original
    reconciliation = json.loads(
        (run_dir / "logs" / "exp4_provenance_reconciliation.json").read_text(encoding="utf-8")
    )
    assert reconciliation["original_run_id"] == "full_x"
    assert reconciliation["original_recorded_commit"] == "old"
    assert reconciliation["stored_simulation_source_hash"] == "abc"


def test_stage_level_source_hashes_present(tmp_path: Path) -> None:
    base = _make_minimal_exp4_package(tmp_path)
    hashes = compute_stage_source_hashes(base)
    for name in ("simulation_source_hash", "aggregation_source_hash", "reporting_source_hash", "validation_source_hash"):
        assert hashes[name], name
        assert len(hashes[name]) == 64


def test_stage_provenance_record_written(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    path = write_stage_provenance_record(run_dir, ROOT)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source_hash_algorithm_version"]
    assert payload["simulation_source_hash"]
    assert payload["reporting_source_hash"]


def test_source_manifest_detects_changed_scientific_file(tmp_path: Path) -> None:
    base = _make_minimal_exp4_package(tmp_path)
    before = compute_stage_source_hashes(base)
    trajectory = base / "exp4" / "simulation" / "trajectory.py"
    trajectory.write_text("def sim():\n    return 2\n", encoding="utf-8")
    after = compute_stage_source_hashes(base)
    assert after["simulation_source_hash"] != before["simulation_source_hash"]
    # Reporting source is untouched, so its hash must not change.
    assert after["reporting_source_hash"] == before["reporting_source_hash"]


def test_audit_reports_stored_vs_current_hash(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    run_config = {
        "run_id": "full_y",
        "run_tier": "full",
        "source_code_hash": "0" * 64,
        "config_hash": "0" * 64,
        "code_commit": "old",
    }
    (run_dir / "logs" / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
    audit = audit_run_provenance(run_dir, ROOT)
    assert audit["source_hash_match"] is False
    assert audit["full_simulation_reuse_decision"] == "DO_NOT_REUSE"
    assert audit["source_hash_algorithm_version_present"] is False
