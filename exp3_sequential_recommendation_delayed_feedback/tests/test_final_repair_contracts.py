from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from artifact_integrity import verify_artifact_manifest
from code_version import code_version
from plot_main_results import PANEL_A_TITLE, SENSITIVITY_CAPTION, _evaluation_exposure_scope
from run_reporting import calculate_final_engineering_status, write_run_report
from self_check import run_self_check, write_self_check_outputs
from utilities import build_artifact_manifest


def test_code_version_is_stable_nonunknown_and_excludes_runtime_trees(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    first = code_version(tmp_path)
    (tmp_path / "outputs" / "run").mkdir(parents=True)
    (tmp_path / "outputs" / "run" / "large.bin").write_bytes(b"runtime")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "private.csv").write_text("x", encoding="utf-8")
    assert code_version(tmp_path) == first
    assert first["code_version_type"] == "source_tree_sha256"
    assert first["code_version"] != "unknown"


def test_panel_title_sensitivity_caption_and_dynamic_exposure_contract() -> None:
    table = pd.DataFrame(
        {
            "split_id": ["evaluation"],
            "design_scope": ["active_run"],
            "selected_action_count": [7],
            "selected_action_exposure_mass_coverage": [0.1234],
        }
    )
    assert PANEL_A_TITLE == "History-based score calibration on common held-out support"
    assert _evaluation_exposure_scope(table, "active_run") == (7, 0.1234)
    assert "sensitivity diagnostics rather than confidence intervals" in SENSITIVITY_CAPTION
    assert "need not contain the full-sample estimate" in SENSITIVITY_CAPTION


def test_report_reads_exposure_mass_and_statuses_from_artifacts(tmp_path: Path) -> None:
    for relative, payload in (
        ("design/exp3_split_manifest.json", {}),
        ("checks/exp3_bootstrap_diagnostics.json", {"formal_ci_validated": False}),
        ("diagnostics/exp3_full_design_support_preflight.json", {"status": "READY"}),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    coverage = pd.DataFrame(
        [
            {"split_id": "evaluation", "design_scope": "active_run", "selected_action_count": 6, "selected_action_exposure_mass_coverage": 0.321},
            {"split_id": "evaluation", "design_scope": "full_design_preflight", "selected_action_count": 20, "selected_action_exposure_mass_coverage": 0.876},
        ]
    )
    path = tmp_path / "tables" / "exp3_action_space_coverage.csv"
    path.parent.mkdir(parents=True)
    coverage.to_csv(path, index=False)
    report = write_run_report(
        tmp_path,
        {
            "pipeline_execution_status": "PASS",
            "independent_self_check_status": "FAIL",
            "archival_integrity_check_status": "NOT_RUN",
            "final_engineering_status": "FAIL",
        },
    ).read_text(encoding="utf-8")
    assert "top-6" in report and "32.1%" in report
    assert "top-20" in report and "87.6%" in report
    assert "Independent self-check status: **FAIL**" in report
    assert "Final engineering status: **FAIL**" in report


def test_independent_and_archival_verification_are_separate(tmp_path: Path) -> None:
    output = tmp_path / "run"
    processed = output / "processed" / "exp3_history_events_with_targets.parquet"
    processed.parent.mkdir(parents=True)
    processed.write_bytes(b"large-event-data")
    lightweight = output / "tables" / "summary.csv"
    lightweight.parent.mkdir(parents=True)
    lightweight.write_text("value\n1\n", encoding="utf-8")
    manifest = output / "metadata" / "run_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"code_version": "test"}), encoding="utf-8")
    build_artifact_manifest(output)
    assert verify_artifact_manifest(output, archival=False)[0]
    processed.unlink()
    assert verify_artifact_manifest(output, archival=True)[0]
    assert not verify_artifact_manifest(output, archival=False)[0]
    with pytest.raises(RuntimeError, match="archival verification is not independent reconstruction"):
        run_self_check(output)


def test_final_engineering_requires_all_four_gates() -> None:
    base = {
        "pipeline_execution_status": "PASS",
        "independent_self_check_status": "PASS",
        "figure_data_contract_status": "PASS",
        "artifact_manifest_status": "PASS",
    }
    assert calculate_final_engineering_status(base) == "PASS"
    for key in base:
        failed = {**base, key: "FAIL"}
        assert calculate_final_engineering_status(failed) == "FAIL"


def test_self_check_failure_status_is_synchronized_to_all_carriers(tmp_path: Path) -> None:
    result = {
        "pipeline_execution_status": "PASS",
        "independent_self_check_status": "FAIL",
        "archival_integrity_check_status": "NOT_RUN",
        "final_engineering_status": "FAIL",
        "scientific_contract_status": "PASS",
        "scientific_uncertainty_status": "SENSITIVITY_ONLY_ACCEPTED",
        "figure_data_contracts": "FAIL",
        "artifact_manifest_status": "PASS",
    }
    manifest = {**result, "run_id": "exp3-fast-test", "run_tier": "fast"}
    rows = [{"check_id": "forced_failure", "category": "engineering", "status": "FAIL", "detail": "test"}]
    write_self_check_outputs(tmp_path, manifest, result, rows)
    saved_manifest = json.loads((tmp_path / "metadata/run_manifest.json").read_text(encoding="utf-8"))
    saved_check = json.loads((tmp_path / "checks/exp3_self_check.json").read_text(encoding="utf-8"))
    saved_summary = pd.read_csv(tmp_path / "checks/exp3_self_check_summary.csv")
    report = (tmp_path / "EXP3_RUN_REPORT.md").read_text(encoding="utf-8")
    assert saved_manifest["final_engineering_status"] == "FAIL"
    assert saved_check["final_engineering_status"] == "FAIL"
    assert set(saved_summary["final_engineering_status"]) == {"FAIL"}
    assert "Final engineering status: **FAIL**" in report
