"""Governance, preservation, and resolution tests for the targeted promotion.

The targeted manuscript extension may only reach ``outputs/paper_candidate``
through the scope-safe additive path in ``promote_targeted.py``: no scientific
recomputation, no full-candidate replacement, and no authorization reuse.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import types

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import promote_targeted
from promote_targeted import (
    ALLOWLIST_PATHS,
    PROMOTION_MANIFEST_RELATIVE,
    PROMOTION_SCOPE,
    PROMOTION_STATUS_RELATIVE,
    PUBLICATION_REQUIREMENTS,
    TARGETED_ALLOWLIST,
)
from src.artifact_io import exp1_stage_source_hashes, sha256_file


PRIMARY_CANDIDATE_FILES = {
    "seed_metrics/exp1_learner_seed_metrics.csv": "seed,structural_regret\n0,1.5\n",
    "derived/exp1_route_summary.csv": "route_id,estimate\narrival_assigned,0.18\n",
    "figures/pdf/fig_exp1_alignment_transfer.pdf": "%PDF-1.4 primary figure\n",
    "exp1_promotion_manifest.json": '{"promotion": "primary"}\n',
}

LEDGER_RELATIVE = "metadata/artifact_manifest.json"

STALE_PRIMARY_MEMO = {
    "memo_id": "CHANGE_MEMO_EXP1_005",
    "experiment_id": "exp1_alignment_transfer",
    "approved_status": "approved",
    "patch_type": "PAPER_PROMOTION_AUTHORIZATION",
    "paper_promotion_authorized": "YES",
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_memo(root: Path, name: str, **fields: str) -> None:
    lines = ["# Change memo", ""]
    lines.extend(f"- {key}: {value}" for key, value in fields.items())
    (root / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _source_csv_text(relative: str) -> str:
    if "cancellation_sweep" in relative:
        return "run_id,metric_id,value\nrun-1,mean_chi,0.0\n"
    if "theory_" in relative:
        return "scale,chi,delta\n0.0,0.0,0.0\n"
    if "utilization" in relative:
        return (
            "mechanism_id,route_id,run_tier,paper_result,analysis_tier,estimate\n"
            "zero_delay,arrival_assigned,full,False,primary,\n"
            "geometric_delay,arrival_assigned,full,False,primary,0.1256766378398699\n"
        )
    return (
        "run_id,mechanism_id,run_tier,paper_result,analysis_tier,value\n"
        "run-1,zero_delay,full,False,targeted,0.179898\n"
    )


def _source_json_payload(relative: str) -> dict:
    if "validation_report" in relative:
        return {
            "analysis_tier": "targeted",
            "experiment_id": "exp1_alignment_transfer",
            "generated_at": "2026-09-10T09:18:42.549152+00:00",
            "horizon_levels": [1000, 5000, 10000],
            "horizon_route_map": {
                "manuscript_facing_route": "arrival_assigned",
                "paper_result": False,
                "stability_inequality_pass": True,
                "utilization_defined_rows": 90,
            },
            "paper_result": False,
            "run_tier": "full",
            "status": "PASS",
            "cancellation_sweep": {
                "gates": {
                    gate: True for gate in promote_targeted.CANCELLATION_GATES
                },
                "grid_cells_per_seed": 48,
                "n_cells": 48 * 30,
                "seeds": list(range(30)),
                "tolerance": 1e-10,
            },
        }
    if "cancellation_invariants" in relative:
        return {
            "analysis_tier": "targeted",
            "cancellation_sweep": {
                gate: {"passed": True} for gate in promote_targeted.CANCELLATION_GATES
            },
        }
    return {
        "figure_id": "fig_exp1_appendix_targeted_cancellation",
        "paper_result": False,
        "run_tier": "full",
    }


def _build_fixture(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "exp1_alignment_transfer"
    full = root / "outputs" / "full"
    candidate = root / "outputs" / "paper_candidate"

    for entry in TARGETED_ALLOWLIST:
        source = full / entry.relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower()
        if suffix == ".csv":
            source.write_text(_source_csv_text(entry.relative_path), encoding="utf-8")
        elif suffix == ".json":
            source.write_text(
                json.dumps(_source_json_payload(entry.relative_path), indent=2),
                encoding="utf-8",
            )
        elif suffix == ".pdf":
            source.write_bytes(b"%PDF-1.4 fixture\n")
        else:
            source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    _write_json(
        full / "metadata" / "run_state.json",
        {
            "run_id": "exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00",
            "paper_result": False,
            "run_tier": "full",
        },
    )

    for relative, text in PRIMARY_CANDIDATE_FILES.items():
        target = candidate / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    indexed_primary = candidate / "seed_metrics" / "exp1_learner_seed_metrics.csv"
    _write_json(
        candidate / LEDGER_RELATIVE,
        {
            "config_hash": "0" * 64,
            "generated_at": "2026-08-18T09:34:37.694802+00:00",
            "paper_result": True,
            "run_id": "exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00",
            "run_tier": "paper",
            "artifacts": [
                {
                    "path": "seed_metrics/exp1_learner_seed_metrics.csv",
                    "sha256": sha256_file(indexed_primary),
                    "size_bytes": indexed_primary.stat().st_size,
                },
                {
                    "path": "targeted/exp1_targeted_horizon_summary.csv",
                    "sha256": "0" * 64,
                    "size_bytes": 1,
                },
            ],
        },
    )

    hashes = exp1_stage_source_hashes(root)
    _write_json(
        root / "status" / "full_validation_status.json",
        {
            "stage": "full_validation",
            "status": "PASS",
            "engineering_status": "PASS",
            "scientific_status": "PASS",
            "paper_result": False,
            "scientific_generation_source_hash": hashes[
                "scientific_generation_source_hash"
            ],
            "validation_source_hash": hashes["validation_source_hash"],
            "reporting_source_hash": hashes["reporting_source_hash"],
            "generated_at": "2026-09-10T09:27:42.847439+00:00",
        },
    )
    _write_json(
        root / "status" / "full_targeted_status.json",
        {
            "stage": "full_targeted",
            "status": "PASS",
            "output": "outputs/full/targeted",
            "paper_result": False,
        },
    )
    _write_json(
        root / "status" / "paper_promotion_status.json",
        {"stage": "paper_promotion", "status": "PASS", "paper_result": True},
    )
    return {"root": root, "full": full, "candidate": candidate}


def _write_scoped_authorization(
    root: Path, full: Path, overrides: dict[str, str] | None = None
) -> None:
    binding = promote_targeted.expected_authorization_binding(full, root)
    binding.update(overrides or {})
    _write_memo(
        root,
        "CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION.md",
        memo_id="CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION",
        experiment_id="exp1_alignment_transfer",
        approved_status="approved",
        patch_type="TARGETED_PAPER_PROMOTION_AUTHORIZATION",
        targeted_paper_promotion_authorized="YES",
        paper_promotion_authorized="NO",
        **binding,
    )


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
def test_stale_primary_memo_does_not_authorize_targeted_extension(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)

    authorization = promote_targeted.promotion_authorization(
        fixture["full"], fixture["root"]
    )

    assert authorization["status"] == "ABSENT"
    assert authorization["present"] is False
    assert (
        authorization["reason"]
        == "STALE_PRIMARY_PROMOTION_MEMO_DOES_NOT_AUTHORIZE_TARGETED_EXTENSION"
    )
    assert authorization["stale_authorization_reuse"] == "BLOCKED"
    legacy = authorization["legacy_primary_authorizations"]
    assert [entry["memo_id"] for entry in legacy] == ["CHANGE_MEMO_EXP1_005"]
    assert legacy[0]["authorized_promotion_scope"] is None


def test_targeted_promotion_requires_scope_specific_authorization(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)

    result = promote_targeted.dry_run(
        fixture["full"], fixture["candidate"], fixture["root"]
    )

    assert result["technical_readiness"] == "PASS"
    assert result["authorization_status"] == "ABSENT"
    assert result["targeted_promotion_ready_except_authorization"] is True
    with pytest.raises(RuntimeError, match="scope-specific authorization"):
        promote_targeted.promote(
            fixture["full"], fixture["candidate"], fixture["root"]
        )
    assert not (fixture["candidate"] / PROMOTION_MANIFEST_RELATIVE).exists()


@pytest.mark.parametrize(
    "overrides",
    (
        {"authorized_validation_hash": "stale-validation-hash"},
        {"authorized_source_run_id": "exp1_alignment_transfer:full:stale"},
        {"authorized_targeted_validation_report_sha256": "0" * 64},
        {"authorized_cancellation_invariants_sha256": "0" * 64},
    ),
)
def test_targeted_authorization_is_bound_to_the_exact_snapshot(
    tmp_path: Path, overrides: dict[str, str]
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"], overrides)

    authorization = promote_targeted.promotion_authorization(
        fixture["full"], fixture["root"]
    )

    assert authorization["status"] == "ABSENT"
    assert authorization["reason"] == "TARGETED_AUTHORIZATION_SNAPSHOT_MISMATCH"
    assert sorted(authorization["authorization_mismatches"]) == sorted(overrides)
    with pytest.raises(RuntimeError, match="scope-specific authorization"):
        promote_targeted.promote(
            fixture["full"], fixture["candidate"], fixture["root"]
        )


def test_dry_run_mutates_nothing(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    before = _snapshot(fixture["root"])

    result = promote_targeted.dry_run(
        fixture["full"], fixture["candidate"], fixture["root"]
    )

    assert result["actual_promotion_executed"] is False
    assert result["mutations_performed"] == []
    assert _snapshot(fixture["root"]) == before


def test_promotion_never_replaces_the_candidate_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the targeted path must never remove a directory")

    monkeypatch.setattr(promote_targeted.shutil, "rmtree", _forbidden)
    monkeypatch.setattr(promote_targeted.shutil, "copytree", _forbidden)
    for name, value in vars(promote_targeted).items():
        if isinstance(value, types.ModuleType):
            assert value.__name__ != "promote", name
        assert name != "promote_module"

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    assert (fixture["candidate"] / "exp1_promotion_manifest.json").is_file()


# ---------------------------------------------------------------------------
# Preservation
# ---------------------------------------------------------------------------
def test_primary_and_source_artifacts_are_preserved(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])
    before = _snapshot(fixture["root"])
    candidate_before = set(_snapshot(fixture["candidate"]))
    allowlisted = set(ALLOWLIST_PATHS)
    ledger_key = "outputs/paper_candidate/" + LEDGER_RELATIVE
    protected_before = {
        key: value
        for key, value in before.items()
        if key not in allowlisted and key != ledger_key
    }

    result = promote_targeted.promote(
        fixture["full"], fixture["candidate"], fixture["root"]
    )

    after = _snapshot(fixture["root"])
    assert result["full_source_hash_preservation"] == "PASS"
    assert result["primary_paper_candidate_hash_preservation"] == "PASS"
    for relative in ALLOWLIST_PATHS:
        source_key = "outputs/full/" + relative
        assert after[source_key] == before[source_key], relative
    for relative, digest in protected_before.items():
        assert after.get(relative) == digest, relative
    assert result["candidate_ledger"]["status"] == "REFRESHED"
    assert candidate_before <= set(_snapshot(fixture["candidate"]))


def test_only_allowlisted_destinations_are_written(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])
    candidate_before = set(_snapshot(fixture["candidate"]))

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    candidate_after = set(_snapshot(fixture["candidate"]))
    added = candidate_after - candidate_before
    assert added == set(ALLOWLIST_PATHS) | {PROMOTION_MANIFEST_RELATIVE}
    assert candidate_before - candidate_after == set()


def _ledger_payload(candidate: Path) -> dict:
    return json.loads((candidate / LEDGER_RELATIVE).read_text(encoding="utf-8"))


def _ledger_records(candidate: Path) -> dict[str, dict]:
    return {item["path"]: item for item in _ledger_payload(candidate)["artifacts"]}


def test_promotion_refreshes_only_promoted_candidate_ledger_entries(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])
    before_payload = _ledger_payload(fixture["candidate"])
    before_records = _ledger_records(fixture["candidate"])
    assert before_records["targeted/exp1_targeted_horizon_summary.csv"]["sha256"] == "0" * 64

    result = promote_targeted.promote(
        fixture["full"], fixture["candidate"], fixture["root"]
    )

    after_records = _ledger_records(fixture["candidate"])
    ledger_record = result["candidate_ledger"]
    assert ledger_record["status"] == "REFRESHED"
    assert ledger_record["non_promoted_entries_unchanged"] is True
    assert set(ledger_record["entries_refreshed"]) | set(
        ledger_record["entries_added"]
    ) == set(ALLOWLIST_PATHS)
    for relative in ALLOWLIST_PATHS:
        destination = fixture["candidate"] / relative
        assert after_records[relative]["sha256"] == sha256_file(destination)
        assert after_records[relative]["size_bytes"] == destination.stat().st_size
    for relative, record in before_records.items():
        if relative in set(ALLOWLIST_PATHS):
            continue
        assert after_records[relative] == record, relative
    after_payload = _ledger_payload(fixture["candidate"])
    assert after_payload["run_id"] == before_payload["run_id"]
    assert after_payload["generated_at"] == before_payload["generated_at"]
    assert after_payload["paper_result"] is True


def test_candidate_ledger_absence_is_tolerated(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    (fixture["candidate"] / LEDGER_RELATIVE).unlink()
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    result = promote_targeted.promote(
        fixture["full"], fixture["candidate"], fixture["root"]
    )

    assert result["candidate_ledger"]["status"] == "ABSENT"
    assert result["primary_paper_candidate_hash_preservation"] == "PASS"
    assert not (fixture["candidate"] / LEDGER_RELATIVE).exists()


def test_malformed_candidate_ledger_blocks_promotion(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    (fixture["candidate"] / LEDGER_RELATIVE).write_text(
        '{"artifact": "primary"}\n', encoding="utf-8"
    )
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    with pytest.raises(RuntimeError, match="candidate_ledger_maintainable"):
        promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    assert _snapshot(fixture["full"])  # source tree untouched by the refusal


# ---------------------------------------------------------------------------
# Flags, manifest, status
# ---------------------------------------------------------------------------
def test_promoted_destination_flags_and_preserved_analysis_tier(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    promoted = (
        fixture["candidate"] / "targeted" / "exp1_targeted_horizon_summary.csv"
    ).read_text(encoding="utf-8")
    header, row = promoted.splitlines()[0].split(","), promoted.splitlines()[1].split(",")
    record = dict(zip(header, row))
    assert record["paper_result"] == "True"
    assert record["run_tier"] == "paper"
    assert record["analysis_tier"] == "targeted"

    utilization = (
        fixture["candidate"] / "derived" / "exp1_regret_stability_utilization.csv"
    ).read_text(encoding="utf-8")
    utilization_header = utilization.splitlines()[0].split(",")
    utilization_row = dict(
        zip(utilization_header, utilization.splitlines()[2].split(","))
    )
    assert utilization_row["paper_result"] == "True"
    assert utilization_row["run_tier"] == "paper"
    assert utilization_row["analysis_tier"] == "primary"

    source = (
        fixture["full"] / "targeted" / "exp1_targeted_horizon_summary.csv"
    ).read_text(encoding="utf-8")
    source_row = dict(zip(source.splitlines()[0].split(","), source.splitlines()[1].split(",")))
    assert source_row["paper_result"] == "False"
    assert source_row["run_tier"] == "full"


def test_promoted_numeric_payload_is_byte_preserved(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    source_lines = (
        fixture["full"] / "derived" / "exp1_regret_stability_utilization.csv"
    ).read_text(encoding="utf-8").splitlines()
    destination_lines = (
        fixture["candidate"] / "derived" / "exp1_regret_stability_utilization.csv"
    ).read_text(encoding="utf-8").splitlines()
    assert len(source_lines) == len(destination_lines)
    estimate_index = source_lines[0].split(",").index("estimate")
    for source_line, destination_line in zip(source_lines[1:], destination_lines[1:]):
        assert (
            source_line.split(",")[estimate_index]
            == destination_line.split(",")[estimate_index]
        )
    assert destination_lines[2].split(",")[estimate_index] == "0.1256766378398699"


def test_targeted_manifest_and_status_are_separate_from_primary(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])
    primary_status_before = _snapshot(fixture["root"] / "status")

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    manifest = json.loads(
        (fixture["candidate"] / PROMOTION_MANIFEST_RELATIVE).read_text(encoding="utf-8")
    )
    assert manifest["promotion_scope"] == PROMOTION_SCOPE
    assert manifest["analysis_tier"] == "targeted"
    assert manifest["paper_result"] is True
    assert manifest["source_root"] == "outputs/full"
    assert manifest["destination_root"] == "outputs/paper_candidate"
    assert manifest["authorization_memo_id"] == "CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION"
    recorded = {entry["relative_path"]: entry for entry in manifest["artifacts"]}
    assert set(recorded) == set(ALLOWLIST_PATHS)
    for relative, entry in recorded.items():
        assert entry["source_sha256"] == sha256_file(fixture["full"] / relative)
        assert entry["destination_sha256"] == sha256_file(
            fixture["candidate"] / relative
        )

    status = json.loads(
        (fixture["root"] / PROMOTION_STATUS_RELATIVE).read_text(encoding="utf-8")
    )
    assert status["stage"] == "targeted_paper_promotion"
    assert status["promotion_scope"] == PROMOTION_SCOPE
    assert status["manifest"] == "outputs/paper_candidate/" + PROMOTION_MANIFEST_RELATIVE
    primary_status_after = _snapshot(fixture["root"] / "status")
    assert {
        key: value
        for key, value in primary_status_after.items()
        if key != Path(PROMOTION_STATUS_RELATIVE).name
    } == primary_status_before


def test_allowlist_is_flat_and_never_recursive(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    assert len(set(ALLOWLIST_PATHS)) == len(ALLOWLIST_PATHS)
    for entry in TARGETED_ALLOWLIST:
        assert (fixture["full"] / entry.relative_path).is_file()
        assert not (fixture["full"] / entry.relative_path).is_dir()
        assert promote_targeted._is_targeted_extension_destination(entry.relative_path)


# ---------------------------------------------------------------------------
# Publication compatibility
# ---------------------------------------------------------------------------
def test_publication_requirements_resolve_after_simulated_promotion(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_scoped_authorization(fixture["root"], fixture["full"])

    # Before promotion the candidate root cannot satisfy the renderer: this is
    # the FileNotFoundError condition the debug task had to resolve.
    for relative in PUBLICATION_REQUIREMENTS:
        assert relative in ALLOWLIST_PATHS
    assert not (fixture["candidate"] / PUBLICATION_REQUIREMENTS[0]).is_file()

    promote_targeted.promote(fixture["full"], fixture["candidate"], fixture["root"])

    for relative in PUBLICATION_REQUIREMENTS:
        resolved = fixture["candidate"] / relative
        assert resolved.is_file(), relative
        source_lines = (fixture["full"] / relative).read_text(encoding="utf-8").splitlines()
        resolved_lines = resolved.read_text(encoding="utf-8").splitlines()
        assert len(resolved_lines) == len(source_lines)
        assert resolved_lines[0] == source_lines[0]


def test_targeted_appendix_reads_only_from_the_publication_source_run() -> None:
    source = (PROJECT_ROOT / "presentation.py").read_text(encoding="utf-8")

    for relative in PUBLICATION_REQUIREMENTS:
        assert relative in source, relative
    assert "outputs/full" not in source
    assert source.count(PUBLICATION_REQUIREMENTS[0]) == 1
    assert source.count(PUBLICATION_REQUIREMENTS[1]) == 1


def test_publication_registry_points_exp1_at_paper_candidate() -> None:
    registry = (PROJECT_ROOT.parent / "presentation_sources.py").read_text(
        encoding="utf-8"
    )
    publication = registry.split("PUBLICATION_SOURCES", 1)[1]
    exp1_publication = publication.split('"2": replace(', 1)[0]
    assert '"paper_candidate"' in exp1_publication
    assert '/ "full"' not in exp1_publication

    preview = registry.split("SOURCES: dict[str, PresentationSource] = {", 1)[1]
    exp1_preview = preview.split('"2": PresentationSource(', 1)[0]
    assert '/ "full"' in exp1_preview
    assert '"paper_candidate"' not in exp1_preview


# ---------------------------------------------------------------------------
# Regression: authorization must be bound to the snapshot it authorizes
# ---------------------------------------------------------------------------
def test_authorization_binding_tracks_the_artifact_snapshot(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    before = promote_targeted.expected_authorization_binding(
        fixture["full"], fixture["root"]
    )

    invariants = fixture["full"] / promote_targeted.CANCELLATION_INVARIANTS_RELATIVE
    invariants.write_text('{"tampered": true}\n', encoding="utf-8")

    after = promote_targeted.expected_authorization_binding(
        fixture["full"], fixture["root"]
    )
    assert (
        after["authorized_cancellation_invariants_sha256"]
        != before["authorized_cancellation_invariants_sha256"]
    )

    _write_memo(
        fixture["root"],
        "CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION.md",
        memo_id="CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION",
        experiment_id="exp1_alignment_transfer",
        approved_status="approved",
        targeted_paper_promotion_authorized="YES",
        **before,
    )
    authorization = promote_targeted.promotion_authorization(
        fixture["full"], fixture["root"]
    )
    assert authorization["status"] == "ABSENT"
    assert authorization["reason"] == "TARGETED_AUTHORIZATION_SNAPSHOT_MISMATCH"
    assert (
        "authorized_cancellation_invariants_sha256"
        in authorization["authorization_mismatches"]
    )


def test_targeted_memo_does_not_authorize_primary_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import promote

    fixture = _build_fixture(tmp_path)
    _write_memo(fixture["root"], "CHANGE_MEMO_EXP1_005.md", **STALE_PRIMARY_MEMO)
    _write_memo(
        fixture["root"],
        "CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION_DRAFT.md",
        memo_id="CHANGE_MEMO_EXP1_006_TARGETED_PROMOTION_DRAFT",
        experiment_id="exp1_alignment_transfer",
        approved_status="pending_human_approval",
        targeted_paper_promotion_authorized="NO",
        authorized_promotion_scope="targeted_extension",
    )
    monkeypatch.setattr(promote, "PROJECT_ROOT", fixture["root"])

    authorization = promote.promotion_authorization()

    assert authorization["status"] == "PRESENT"
    assert authorization["memo_id"] == "CHANGE_MEMO_EXP1_005"
    assert promote._is_targeted_extension_memo(
        {"authorized_promotion_scope": "targeted_extension"}
    )
    assert not promote._is_targeted_extension_memo(
        {"paper_promotion_authorized": "YES"}
    )
