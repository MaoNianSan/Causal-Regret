"""Tests for the auto-generated implementation status report."""

from __future__ import annotations

import json
from pathlib import Path

from exp4.outputs.run_lineage import fresh_lineage, write_run_lineage
from exp4.reporting.implementation_status import (
    build_implementation_status,
    scan_runs,
    write_implementation_status,
)


def _make_run(
    base: Path, tier: str, run_id: str, paper_promotion: str = "NOT_RUN"
) -> Path:
    run_dir = base / "outputs" / "runs" / run_id
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "checks").mkdir(parents=True)
    run_config = {
        "run_id": run_id,
        "run_tier": tier,
        "generated_at": "2026-08-06T00:00:00+00:00",
        "paper_result": paper_promotion == "PASS",
        "result_schema": "exp4_controlled_route_audit_v2",
        "source_code_hash": "0" * 64,
        "config_hash": "0" * 64,
        "code_commit": "x",
    }
    (run_dir / "logs" / "run_config.json").write_text(
        json.dumps(run_config), encoding="utf-8"
    )
    (run_dir / "logs" / "exp4_result_status.json").write_text(
        json.dumps(
            {
                "paper_promotion": paper_promotion,
                "paper_result": paper_promotion == "PASS",
            }
        ),
        encoding="utf-8",
    )
    for name, status in (
        ("exp4_engineering_checks.json", "PASS"),
        ("exp4_scientific_checks.json", "PASS"),
    ):
        (run_dir / "checks" / name).write_text(
            json.dumps({"status": status, "checks": []}), encoding="utf-8"
        )
    return run_dir


def test_implementation_status_detects_existing_full_run(tmp_path: Path) -> None:
    _make_run(tmp_path, "fast", "fast_1")
    _make_run(tmp_path, "full", "full_1")
    status = build_implementation_status(tmp_path)
    assert status["latest_full_run"] == "full_1"
    assert status["FULL_RUN_EXECUTED"] == "YES"
    assert status["full_run_engineering_status"] == "PASS"
    assert status["full_run_scientific_status"] == "PASS"


def test_status_report_does_not_claim_full_not_executed(tmp_path: Path) -> None:
    _make_run(tmp_path, "full", "full_2")
    path = tmp_path / "reports" / "EXP4_V2_IMPLEMENTATION_STATUS.md"
    status = write_implementation_status(tmp_path, path)
    assert status["FULL_RUN_EXECUTED"] == "YES"
    text = path.read_text(encoding="utf-8")
    assert "FULL_RUN_EXECUTED=YES" in text
    assert "FULL_RUN_EXECUTED=NO" not in text


def test_scan_runs_selects_latest_per_tier(tmp_path: Path) -> None:
    _make_run(tmp_path, "middle", "middle_old")
    _make_run(tmp_path, "middle", "middle_new")
    _make_run(tmp_path, "full", "full_1")
    runs = scan_runs(tmp_path)
    assert runs["middle"]["run_id"] == "middle_new"


def test_status_reflects_promotion_state(tmp_path: Path) -> None:
    _make_run(tmp_path, "full", "full_3", paper_promotion="PASS")
    status = build_implementation_status(tmp_path)
    assert status["PAPER_PROMOTION_EXECUTED"] == "YES"
    assert status["paper_result"] is True


def test_reuse_eligibility_does_not_imply_actual_reuse(tmp_path: Path) -> None:
    """Eligibility is a hash property; execution mode is a lineage fact."""
    _make_run(tmp_path, "full", "full_elig")
    run_dir = tmp_path / "outputs" / "runs" / "full_elig"
    write_run_lineage(run_dir, fresh_lineage("full_elig", "full", "x", True))
    status = build_implementation_status(tmp_path)
    # Stored hashes do not match the current tree, so the run is not eligible
    # for reuse...
    assert status["FULL_SIMULATION_REUSE_ELIGIBLE"] == "NO"
    # ...but the lineage still records that it actually executed its own
    # simulation fresh.
    assert status["FULL_SIMULATION_EXECUTION_MODE"] == "FRESH"
    assert status["FULL_SIMULATION_SOURCE_RUN_ID"] == "NONE"
    assert status["FULL_SIMULATION_RERUN_REQUIRED"] is True


def test_unknown_lineage_is_not_reported_as_reused(tmp_path: Path) -> None:
    _make_run(tmp_path, "full", "full_unknown")
    status = build_implementation_status(tmp_path)
    assert status["FULL_SIMULATION_EXECUTION_MODE"] == "UNKNOWN"
    assert status["FULL_SIMULATION_REUSE_ELIGIBLE"] == "UNKNOWN"
    assert status["FULL_SIMULATION_SOURCE_RUN_ID"] == "UNKNOWN"
    assert status["DOWNSTREAM_ARTIFACTS_EXECUTION_MODE"] == "UNKNOWN"
    assert status["FULL_SIMULATION_RERUN_REQUIRED"] is True


def test_fresh_full_without_provenance_requires_rerun(tmp_path: Path) -> None:
    _make_run(tmp_path, "full", "full_fresh_no_prov")
    run_dir = tmp_path / "outputs" / "runs" / "full_fresh_no_prov"
    write_run_lineage(run_dir, fresh_lineage("full_fresh_no_prov", "full", "x", True))
    status = build_implementation_status(tmp_path)
    assert status["FULL_SIMULATION_EXECUTION_MODE"] == "FRESH"
    assert status["FULL_SIMULATION_RERUN_REQUIRED"] is True
    assert status["provenance_status"] == "UNVERIFIED"
