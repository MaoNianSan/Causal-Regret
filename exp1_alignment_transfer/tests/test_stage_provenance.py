"""Stage-isolation and reuse-decision tests for Exp1 provenance."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.artifact_io import EXP1_STAGE_SOURCE_FILES, exp1_stage_source_hashes, sha256_file
from src import run_provenance
from src.run_provenance import Exp1ReuseDecision, audit_exp1_provenance


def _write_stage_fixture(root: Path) -> None:
    for files in EXP1_STAGE_SOURCE_FILES.values():
        for relative in files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {relative}\n", encoding="utf-8")


def test_stage_hashes_isolate_generation_validation_aggregation_and_reporting(
    tmp_path: Path,
) -> None:
    root = tmp_path / "exp1"
    _write_stage_fixture(root)
    before = exp1_stage_source_hashes(root)

    cases = (
        ("plot_main.py", "reporting_source_hash"),
        ("plot_appendix.py", "reporting_source_hash"),
        ("promote.py", "reporting_source_hash"),
        ("self_check.py", "validation_source_hash"),
        ("src/derived.py", "aggregation_source_hash"),
        ("src/structural_process.py", "scientific_generation_source_hash"),
        ("src/route_maps.py", "scientific_generation_source_hash"),
    )
    for relative, changed_stage in cases:
        path = root / relative
        original = path.read_text(encoding="utf-8")
        path.write_text(original + "changed = True\n", encoding="utf-8")
        after = exp1_stage_source_hashes(root)
        assert after[changed_stage] != before[changed_stage]
        if changed_stage != "scientific_generation_source_hash":
            assert after["scientific_generation_source_hash"] == before[
                "scientific_generation_source_hash"
            ]
        path.write_text(original, encoding="utf-8")


def _write_reusable_run(root: Path) -> Path:
    _write_stage_fixture(root)
    run_dir = root / "outputs" / "full"
    (run_dir / "metadata").mkdir(parents=True)
    (run_dir / "checks").mkdir(parents=True)
    for relative in run_provenance.RAW_ARTIFACTS:
        path = run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
    hashes = exp1_stage_source_hashes(root)
    manifest = {
        "effective_config_hash": "config-current",
        "artifact_hashes": {},
    }
    calibration = root / "calibration"
    calibration.mkdir()
    (calibration / "exp1_calibration_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (calibration / "exp1_calibration_stage_provenance.json").write_text(
        json.dumps(
            {
                "schema": run_provenance.EXP1_STAGE_PROVENANCE_SCHEMA,
                "calibration_manifest_hash": run_provenance.hash_payload(manifest),
                "config_hash": "config-current",
                "calibration_source_hash": hashes["calibration_source_hash"],
            }
        ),
        encoding="utf-8",
    )
    state = {
        "run_id": "full_fixture",
        "run_tier": "full",
        "config_hash": "config-current",
        "engineering_status": "PASS",
        "scientific_status": "PASS",
    }
    (run_dir / "metadata" / "run_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    (run_dir / "checks" / "exp1_validation_report.json").write_text(
        json.dumps({"engineering_status": "PASS", "scientific_status": "PASS"}),
        encoding="utf-8",
    )
    (run_dir / "metadata" / "exp1_run_lineage.json").write_text(
        json.dumps(
            {
                "schema": run_provenance.EXP1_RUN_LINEAGE_SCHEMA,
                "simulation_execution_mode": "FRESH",
                "simulation_source_run_id": None,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "metadata" / "exp1_stage_provenance.json").write_text(
        json.dumps(
            {
                "schema": run_provenance.EXP1_STAGE_PROVENANCE_SCHEMA,
                "stage_source_hashes": hashes,
                "raw_artifacts": {
                    relative: sha256_file(run_dir / relative)
                    for relative in run_provenance.RAW_ARTIFACTS
                },
            }
        ),
        encoding="utf-8",
    )
    return run_dir


@pytest.mark.parametrize(
    ("relative", "expected"),
    (
        ("plot_main.py", Exp1ReuseDecision.REPORTING_REBUILD),
        ("self_check.py", Exp1ReuseDecision.DOWNSTREAM_REBUILD),
        ("src/derived.py", Exp1ReuseDecision.DOWNSTREAM_REBUILD),
        ("src/structural_process.py", Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN),
    ),
)
def test_reuse_decision_is_stage_aware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str, expected: Exp1ReuseDecision
) -> None:
    root = tmp_path / "exp1"
    run_dir = _write_reusable_run(root)
    monkeypatch.setattr(run_provenance, "_current_config_hash", lambda *_: "config-current")
    monkeypatch.setattr(run_provenance, "_calibration_artifacts_consistent", lambda *_: True)
    target = root / relative
    target.write_text(target.read_text(encoding="utf-8") + "changed = True\n", encoding="utf-8")
    audit = audit_exp1_provenance(run_dir, root)
    assert audit["decision"] == expected.value
    assert audit["scientific_reuse_eligible"] is (expected is not Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN)


def test_config_change_requires_scientific_full_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "exp1"
    run_dir = _write_reusable_run(root)
    monkeypatch.setattr(run_provenance, "_current_config_hash", lambda *_: "different-config")
    monkeypatch.setattr(run_provenance, "_calibration_artifacts_consistent", lambda *_: True)
    audit = audit_exp1_provenance(run_dir, root)
    assert audit["decision"] == Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN.value
    assert audit["failure_reason"] == "PAPER_AUDIT_FAIL_CONFIG_CHANGED"
