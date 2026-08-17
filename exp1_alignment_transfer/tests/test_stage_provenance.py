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
        ("targeted.py", "validation_source_hash"),
        ("src/theory_sweeps.py", "validation_source_hash"),
        ("src/derived.py", "aggregation_source_hash"),
        ("src/scientific_execution.py", "scientific_generation_source_hash"),
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


def test_main_plumbing_does_not_change_scientific_generation_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "exp1"
    _write_stage_fixture(root)
    main_path = root / "main.py"
    main_path.write_text("# orchestration\n", encoding="utf-8")
    before = exp1_stage_source_hashes(root)
    main_path.write_text("# orchestration\nstatus = 'changed'\n", encoding="utf-8")
    after = exp1_stage_source_hashes(root)
    assert (
        after["scientific_generation_source_hash"]
        == before["scientific_generation_source_hash"]
    )


@pytest.mark.parametrize("relative", ("targeted.py", "src/theory_sweeps.py"))
def test_targeted_sources_change_validation_hash_only(
    tmp_path: Path, relative: str
) -> None:
    root = tmp_path / "exp1"
    _write_stage_fixture(root)
    before = exp1_stage_source_hashes(root)
    path = root / relative
    path.write_text(path.read_text(encoding="utf-8") + "changed = True\n", encoding="utf-8")
    after = exp1_stage_source_hashes(root)
    changed = {name for name in before if before[name] != after[name]}
    assert changed == {"validation_source_hash"}


def test_canonical_aggregation_source_changes_aggregation_hash_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "exp1"
    _write_stage_fixture(root)
    before = exp1_stage_source_hashes(root)
    path = root / "src" / "derived.py"
    path.write_text(path.read_text(encoding="utf-8") + "changed = True\n", encoding="utf-8")
    after = exp1_stage_source_hashes(root)
    changed = {name for name in before if before[name] != after[name]}
    assert changed == {"aggregation_source_hash"}


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
        ("targeted.py", Exp1ReuseDecision.DOWNSTREAM_REBUILD),
        ("src/derived.py", Exp1ReuseDecision.DOWNSTREAM_REBUILD),
        ("src/scientific_execution.py", Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN),
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


def test_reconcile_uses_canonical_aggregation_and_rebuilds_full_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import reconcile

    source = tmp_path / "outputs" / "full"
    source.mkdir(parents=True)
    targeted_dir = source / "targeted"
    targeted_dir.mkdir()
    expected_targeted = (
        "exp1_targeted_validation_report.json",
        "exp1_targeted_mean_delay_seed_metrics.csv",
        "exp1_targeted_mean_delay_summary.csv",
        "exp1_targeted_horizon_seed_metrics.csv",
        "exp1_targeted_horizon_summary.csv",
        "exp1_targeted_theory_exact_shift_sweep.csv",
        "exp1_targeted_theory_margin_threshold_sweep.csv",
        "fig_exp1_targeted_validation_data.csv",
    )
    (source / "checks").mkdir()
    (source / "checks" / "exp1_validation_report.json").write_text(
        "{}", encoding="utf-8"
    )
    for name in expected_targeted:
        payload = '{"status":"PASS"}' if name.endswith("report.json") else "x\n"
        (targeted_dir / name).write_text(payload, encoding="utf-8")
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        reconcile, "run_checks", lambda tier: calls.append(("self_check", tier))
    )
    monkeypatch.setattr(
        reconcile,
        "execute_targeted_validation",
        lambda tier, force: calls.append(("targeted", (tier, force))) or targeted_dir,
    )
    artifacts = reconcile._rebuild_validation(source, "full")
    assert calls == [("self_check", "full"), ("targeted", ("full", True))]
    assert "checks/exp1_validation_report.json" in artifacts
    assert "targeted/exp1_targeted_theory_exact_shift_sweep.csv" in artifacts

    source_text = (PROJECT_ROOT / "reconcile.py").read_text(encoding="utf-8")
    assert "rebuild_derived_from_scientific_artifacts" in source_text
    assert "arrival_assigned" not in source_text
    assert "systematic_misbinding" not in source_text


def _write_memo(root: Path, memo_id: int, authorization: str) -> None:
    (root / f"CHANGE_MEMO_EXP1_{memo_id:03d}.md").write_text(
        "\n".join(
            [
                f"- memo_id: CHANGE_MEMO_EXP1_{memo_id:03d}",
                "- experiment_id: exp1_alignment_transfer",
                "- approved_status: approved",
                f"- paper_promotion_authorized: {authorization}",
            ]
        ),
        encoding="utf-8",
    )


def test_latest_memo_no_blocks_actual_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import promote

    _write_memo(tmp_path, 3, "YES")
    _write_memo(tmp_path, 4, "NO")
    monkeypatch.setattr(promote, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(promote, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(promote, "STATUS", tmp_path / "status")
    monkeypatch.setattr(
        promote,
        "promotion_readiness",
        lambda full=None: {
            "status": "PASS",
            "checks": {},
            "stage_aware_provenance": {},
        },
    )
    with pytest.raises(RuntimeError, match="latest applicable change memo"):
        promote.promote()
    assert promote.promotion_authorization()["status"] == "ABSENT"


def test_latest_memo_yes_permits_authorization_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import promote

    _write_memo(tmp_path, 4, "NO")
    _write_memo(tmp_path, 5, "YES")
    monkeypatch.setattr(promote, "PROJECT_ROOT", tmp_path)
    authorization = promote.promotion_authorization()
    assert authorization["status"] == "PRESENT"
    assert authorization["memo_id"] == "CHANGE_MEMO_EXP1_005"


def test_promotion_dry_run_does_not_mutate_paper_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import promote

    candidate = tmp_path / "outputs" / "paper_candidate"
    candidate.mkdir(parents=True)
    marker = candidate / "marker.txt"
    marker.write_bytes(b"unchanged")
    monkeypatch.setattr(promote, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(
        promote,
        "promotion_readiness",
        lambda full=None: {
            "status": "PASS",
            "technical_promotion_readiness": "PASS",
        },
    )
    monkeypatch.setattr(
        promote,
        "promotion_authorization",
        lambda: {"status": "ABSENT", "present": False},
    )
    before = marker.read_bytes()
    result = promote.dry_run_promotion()
    assert result["promotion_ready_except_authorization"] is True
    assert result["actual_promotion_executed"] is False
    assert marker.read_bytes() == before


def test_stored_full_execution_contract_replay_is_identical() -> None:
    run_dir = PROJECT_ROOT / "outputs" / "full"
    if not run_dir.exists():
        pytest.skip("local stored full artifacts are unavailable")
    from main import load_frozen_calibration
    from src.scientific_execution_replay import (
        replay_scientific_execution_contract,
    )

    replay = replay_scientific_execution_contract(
        run_dir, load_frozen_calibration()
    )
    assert replay["scientific_equivalence"] == "PASS"
    assert all(item["status"] == "PASS" for item in replay["comparisons"])
