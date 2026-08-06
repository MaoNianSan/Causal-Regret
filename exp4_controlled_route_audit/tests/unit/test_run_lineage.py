"""Tests for the run-lineage contract: eligibility vs actual execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exp4.outputs.run_lineage import (
    RunLineage,
    fresh_lineage,
    lineage_valid,
    load_run_lineage,
    mark_downstream_rebuilt,
    write_run_lineage,
)


def _tmp_run(tmp_path: Path, run_id: str = "full_lineage") -> Path:
    run_dir = tmp_path / run_id
    (run_dir / "logs").mkdir(parents=True)
    return run_dir


def test_fresh_lineage_structure() -> None:
    lineage = fresh_lineage("full_x", "full", "abc123", True)
    ok, reason = lineage.validate()
    assert ok, reason
    assert lineage.simulation_execution_mode == "FRESH"
    assert lineage.simulation_source_run_id is None
    assert lineage.downstream_execution_mode == "INLINE_FRESH"
    assert lineage.downstream_source_run_id is None
    assert lineage.exp4_worktree_clean_at_start is True


def test_reuse_eligibility_does_not_imply_actual_reuse(tmp_path: Path) -> None:
    """A lineage never claims REUSED from hash equality alone.

    The execution mode is a recorded fact; the audit derives it from the
    lineage artifact, not from whether stored hashes match the current tree.
    """
    run_dir = _tmp_run(tmp_path)
    write_run_lineage(run_dir, fresh_lineage("full_elig", "full", "abc", True))
    lineage = load_run_lineage(run_dir)
    assert lineage is not None
    assert lineage.simulation_execution_mode == "FRESH"
    # Even a run whose stored hashes happen to match the current source must
    # report FRESH: matching hashes are eligibility, not execution.
    assert lineage.simulation_source_run_id is None


def test_fresh_full_reports_execution_mode_fresh(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    write_run_lineage(run_dir, fresh_lineage("full_f", "full", "abc", True))
    lineage = load_run_lineage(run_dir)
    assert lineage is not None
    assert lineage.simulation_execution_mode == "FRESH"
    assert lineage.simulation_source_run_id is None


def test_reused_full_reports_source_run_id(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    lineage = RunLineage(
        run_id="full_reused",
        run_tier="full",
        simulation_execution_mode="REUSED",
        simulation_source_run_id="full_source_run_1",
        downstream_execution_mode="REBUILT_FROM_REUSED_SIMULATION",
        downstream_source_run_id="full_source_run_1",
        created_from_commit="abc",
        exp4_worktree_clean_at_start=True,
    )
    ok, reason = lineage.validate()
    assert ok, reason
    write_run_lineage(run_dir, lineage)
    loaded = load_run_lineage(run_dir)
    assert loaded is not None
    assert loaded.simulation_execution_mode == "REUSED"
    assert loaded.simulation_source_run_id == "full_source_run_1"
    assert loaded.downstream_execution_mode == "REBUILT_FROM_REUSED_SIMULATION"


def test_downstream_rebuild_status_reads_lineage(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    (run_dir / "logs" / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": "full_own",
                "run_tier": "full",
                "code_commit": "abc",
                "exp4_worktree_clean_at_start": True,
                "formal_full_clean_worktree_required": True,
            }
        ),
        encoding="utf-8",
    )
    write_run_lineage(run_dir, fresh_lineage("full_own", "full", "abc", True))
    rebuilt = mark_downstream_rebuilt(run_dir, tmp_path)
    assert rebuilt.downstream_execution_mode == "REBUILT_FROM_OWN_SIMULATION"
    assert rebuilt.simulation_execution_mode == "FRESH"
    # A rebuilt run still records which run supplied the simulation: itself.
    assert rebuilt.downstream_source_run_id is None
    assert rebuilt.simulation_source_run_id is None


def test_unknown_lineage_is_not_reported_as_reused(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    lineage = RunLineage(
        run_id="full_unknown",
        run_tier="full",
        simulation_execution_mode="UNKNOWN",
        simulation_source_run_id=None,
        downstream_execution_mode="UNKNOWN",
        downstream_source_run_id=None,
        created_from_commit="abc",
        exp4_worktree_clean_at_start=False,
    )
    ok, reason = lineage.validate()
    assert not ok
    assert "UNKNOWN" in reason


def test_missing_lineage_artifact_is_invalid(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    ok, reason = lineage_valid(load_run_lineage(run_dir))
    assert not ok
    assert "missing" in reason


def test_fresh_lineage_rejects_nonnull_source_run_id() -> None:
    lineage = RunLineage(
        run_id="full_bad",
        run_tier="full",
        simulation_execution_mode="FRESH",
        simulation_source_run_id="some_run",
        downstream_execution_mode="INLINE_FRESH",
        downstream_source_run_id=None,
        created_from_commit="abc",
        exp4_worktree_clean_at_start=True,
    )
    ok, reason = lineage.validate()
    assert not ok
    assert "null" in reason


def test_reused_lineage_requires_source_run_id() -> None:
    lineage = RunLineage(
        run_id="full_bad2",
        run_tier="full",
        simulation_execution_mode="REUSED",
        simulation_source_run_id=None,
        downstream_execution_mode="REBUILT_FROM_REUSED_SIMULATION",
        downstream_source_run_id=None,
        created_from_commit="abc",
        exp4_worktree_clean_at_start=True,
    )
    ok, reason = lineage.validate()
    assert not ok
    assert "simulation_source_run_id" in reason


def test_legacy_schema_lineage_artifacts_are_not_loaded(tmp_path: Path) -> None:
    run_dir = _tmp_run(tmp_path)
    (run_dir / "logs" / "exp4_run_lineage.json").write_text(
        json.dumps(
            {
                "schema": "some_old_schema",
                "run_id": "full_legacy",
                "simulation_execution_mode": "FRESH",
            }
        ),
        encoding="utf-8",
    )
    assert load_run_lineage(run_dir) is None
