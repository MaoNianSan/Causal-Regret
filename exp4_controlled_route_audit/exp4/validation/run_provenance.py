"""Stage-level provenance and source-hash audit for Exp4 v3 runs.

A full Exp4 run has four downstream stages after the raw simulation:
aggregation, reporting, validation, and (implicitly) the pipeline wiring.
The single legacy ``source_code_hash`` covers all ``exp4/**/*.py`` files, which
cannot distinguish "simulation changed" from "reporting changed". This module
adds stage-level source hashes so a reused raw simulation can be reconciled
with rebuilt downstream stages without pretending the reporting hash is the
simulation hash.

The audit separates *reuse eligibility* (a property of stored hashes and the
current source tree) from *actual execution* (which run really executed the
simulation), which is recorded only in the run-lineage artifact.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from exp4.outputs.run_lineage import (
    RunLineage,
    lineage_valid,
    load_run_lineage,
    mark_downstream_rebuilt,
)
from exp4.outputs.writers import (
    SOURCE_HASH_ALGORITHM_VERSION,
    compute_exp4_source_code_hash,
    compute_stage_source_hashes as writers_compute_stage_source_hashes,
    exp4_worktree_clean,
    git_commit,
    sha256_file,
    utc_now_iso,
    write_json,
)
from exp4.validation.provenance_checks import manifest_paths_are_relative_and_exist

STAGE_PROVENANCE_SCHEMA = "exp4_stage_provenance_v2"

# Stage display names mapped to the flat source-hash keys.
STAGE_KEYS = {
    "simulation": "simulation_source_hash",
    "aggregation": "aggregation_source_hash",
    "reporting": "reporting_source_hash",
    "validation": "validation_source_hash",
}
DOWNSTREAM_STAGE_NAMES = ("aggregation", "reporting", "validation")


class Exp4ReuseDecision(str, Enum):
    SCIENTIFIC_FULL_RERUN = "SCIENTIFIC_FULL_RERUN"
    DOWNSTREAM_REBUILD = "DOWNSTREAM_REBUILD"
    REPORTING_REBUILD = "REPORTING_REBUILD"
    METADATA_ONLY = "METADATA_ONLY"
    NOT_REUSABLE = "NOT_REUSABLE"


def compute_stage_source_hashes(base_dir: Path) -> dict[str, str]:
    """Per-stage source hashes over the current working tree.

    Re-export of the canonical implementation in ``exp4.outputs.writers``.
    """
    return writers_compute_stage_source_hashes(base_dir)


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _current_config_hash(base_dir: Path) -> str:
    from exp4.outputs.writers import config_hash

    return config_hash()


def _current_git_commit(base_dir: Path) -> str:
    return git_commit(base_dir)


def _exp4_worktree_dirty(base_dir: Path) -> bool:
    return not exp4_worktree_clean(base_dir)


def _utc_now_iso() -> str:
    return utc_now_iso()


def _alg_version_consistent(run_config: dict[str, object]) -> bool:
    recorded = str(run_config.get("source_hash_algorithm_version", ""))
    return bool(recorded) and recorded == SOURCE_HASH_ALGORITHM_VERSION


def load_stage_provenance_record(run_dir: Path) -> dict[str, object] | None:
    """Load the v2 stage provenance record; returns None for legacy layouts."""
    payload = _load_json(run_dir / "logs" / "exp4_stage_provenance.json")
    if payload is None or payload.get("schema") != STAGE_PROVENANCE_SCHEMA:
        return None
    return payload


def _stored_calibration_hash(run_dir: Path, run_config: dict[str, object]) -> str | None:
    stage_record = load_stage_provenance_record(run_dir)
    if stage_record and stage_record.get("calibration_hash"):
        return str(stage_record["calibration_hash"])
    calibration_path = run_dir / "derived" / "calibration" / "exp4_proxy_route_calibration.json"
    payload = _load_json(calibration_path)
    if payload and payload.get("calibration_hash"):
        return str(payload["calibration_hash"])
    if run_config.get("calibration_hash"):
        return str(run_config["calibration_hash"])
    return None


def _calibration_hash_consistent(run_dir: Path, stored_calibration_hash: str | None) -> bool:
    """Frozen calibration hash must equal the calibration artifact produced by the run."""
    if not stored_calibration_hash:
        return False
    calibration_path = run_dir / "derived" / "calibration" / "exp4_proxy_route_calibration.json"
    payload = _load_json(calibration_path)
    if payload is None or not payload.get("calibration_hash"):
        return False
    return str(payload["calibration_hash"]) == stored_calibration_hash


def raw_simulation_artifacts_complete(run_dir: Path) -> bool:
    manifests = [
        run_dir / "logs" / "exp4_module_a_path_manifest.csv",
        run_dir / "logs" / "exp4_module_bc_path_manifest.csv",
    ]
    if not all(path.exists() for path in manifests):
        return False
    ok, _ = manifest_paths_are_relative_and_exist(run_dir, manifests)
    return ok


def _reconciliation_present(run_dir: Path) -> bool:
    return (run_dir / "logs" / "exp4_provenance_reconciliation.json").exists()


def _compare_stages(
    run_config: dict[str, object],
    stage_record: dict[str, object] | None,
    current_hashes: dict[str, str],
) -> dict[str, dict[str, object]]:
    stages: dict[str, dict[str, object]] = {}
    for name, key in STAGE_KEYS.items():
        stored: str | None = None
        record_present = False
        execution_mode = "UNKNOWN"
        source_run_id: str | None = None
        if stage_record is not None and name in stage_record.get("stages", {}):
            entry = stage_record["stages"][name]
            stored = str(entry.get("source_hash") or "")
            record_present = bool(stored)
            execution_mode = str(entry.get("execution_mode") or "UNKNOWN")
            source_run_id = (
                str(entry["source_run_id"]) if entry.get("source_run_id") is not None else None
            )
        legacy_key = key.replace("_source_hash", "_stage_hash")
        if stored is None and run_config.get(key):
            # Informational only: legacy runs freeze stage hashes in the run
            # config, but without a v2 stage record they are not a record.
            stored = str(run_config[key])
        elif stored is None and run_config.get(legacy_key):
            stored = str(run_config[legacy_key])
        current = current_hashes.get(key, "")
        stages[name] = {
            "stored_hash": stored,
            "current_hash": current,
            "hash_match": bool(stored) and stored == current,
            "record_present": record_present,
            "execution_mode": execution_mode,
            "source_run_id": source_run_id,
        }
    return stages


def _source_unchanged_during_run(
    stage_record: dict[str, object] | None,
    current_source_hash: str,
    current_git: str,
) -> bool:
    if stage_record is None:
        return False
    if stage_record.get("source_unchanged_during_run") is not True:
        return False
    if str(stage_record.get("complete_source_hash", "")) != current_source_hash:
        return False
    if str(stage_record.get("recorded_git_commit", "")) != current_git:
        return False
    return True


def audit_run_provenance(
    run_dir: Path, base_dir: Path, recompute_calibration: bool = False
) -> dict[str, object]:
    """Read-only provenance audit for a completed run.

    ``recompute_calibration`` optionally reruns the calibration stage to
    independently reproduce the calibration hash; it is off by default because
    the audit is also invoked by lightweight status/promotion paths.
    """
    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = _load_json(run_config_path) or {}
    stored_source_hash = str(run_config.get("source_code_hash", ""))
    current_source_hash = compute_exp4_source_code_hash(base_dir)
    stage_hashes = compute_stage_source_hashes(base_dir)
    config_hash_match = str(run_config.get("config_hash", "")) == _current_config_hash(base_dir)
    stored_calibration_hash = _stored_calibration_hash(run_dir, run_config)
    calibration_hash_consistent = _calibration_hash_consistent(run_dir, stored_calibration_hash)
    calibration_recompute_match: bool | None = None
    if (
        recompute_calibration
        and stored_calibration_hash
        and stored_source_hash
        and config_hash_match
    ):
        try:
            recomputed = recompute_calibration_hash(
                stored_source_hash, str(run_config.get("config_hash", ""))
            )
            calibration_recompute_match = recomputed == stored_calibration_hash
        except Exception:
            calibration_recompute_match = None

    worktree_dirty = _exp4_worktree_dirty(base_dir)
    lineage = load_run_lineage(run_dir)
    lineage_present = lineage is not None
    lineage_ok, lineage_reason = lineage_valid(lineage)
    stage_record = load_stage_provenance_record(run_dir)
    stages = _compare_stages(run_config, stage_record, stage_hashes)
    simulation_stage = stages["simulation"]
    downstream_stages = [stages[name] for name in DOWNSTREAM_STAGE_NAMES]
    all_records_present = all(entry["record_present"] for entry in stages.values())
    all_hashes_match = all(entry["hash_match"] for entry in stages.values())

    simulation_mode = str(lineage.simulation_execution_mode) if lineage is not None else "UNKNOWN"
    simulation_source_run_id = lineage.simulation_source_run_id if lineage is not None else None
    downstream_mode = str(lineage.downstream_execution_mode) if lineage is not None else "UNKNOWN"
    downstream_source_run_id = lineage.downstream_source_run_id if lineage is not None else None

    simulation_reuse_eligible = bool(
        simulation_stage["record_present"]
        and simulation_stage["hash_match"]
        and config_hash_match
        and calibration_hash_consistent
        and raw_simulation_artifacts_complete(run_dir)
        and lineage_present
        and simulation_mode != "UNKNOWN"
        and _alg_version_consistent(run_config)
        and (simulation_mode == "FRESH" or _reconciliation_present(run_dir))
    )
    simulation_provenance_verified = bool(simulation_reuse_eligible and lineage_ok)
    downstream_provenance_verified = bool(
        all(entry["record_present"] for entry in downstream_stages)
        and all(entry["hash_match"] for entry in downstream_stages)
        and lineage_present
        and lineage_ok
        and (simulation_mode == "FRESH" or _reconciliation_present(run_dir))
    )
    reporting_provenance_verified = bool(
        downstream_provenance_verified and stages["reporting"]["hash_match"]
    )
    source_unchanged = _source_unchanged_during_run(
        stage_record, current_source_hash, _current_git_commit(base_dir)
    )
    formal_full_clean_worktree_required = bool(
        run_config.get("formal_full_clean_worktree_required")
    )
    formal_full_started_clean = bool(
        run_config.get("exp4_worktree_clean_at_start")
    ) and formal_full_clean_worktree_required

    if simulation_provenance_verified:
        reuse_eligibility = "ELIGIBLE"
    elif not lineage_present:
        reuse_eligibility = "UNKNOWN"
    else:
        reuse_eligibility = "NOT_ELIGIBLE"
    legacy_reuse_decision = {
        "ELIGIBLE": "REUSE",
        "NOT_ELIGIBLE": "DO_NOT_REUSE",
        "UNKNOWN": "UNKNOWN",
    }[reuse_eligibility]

    if not lineage_present or not all_records_present:
        paper_audit_decision = Exp4ReuseDecision.NOT_REUSABLE
        paper_audit_reason = "PAPER_AUDIT_FAIL_RAW_OR_LINEAGE_INCOMPLETE"
    elif not simulation_stage["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.SCIENTIFIC_FULL_RERUN
        paper_audit_reason = "PAPER_AUDIT_FAIL_SIMULATION_HASH_CHANGED"
    elif not config_hash_match:
        paper_audit_decision = Exp4ReuseDecision.SCIENTIFIC_FULL_RERUN
        paper_audit_reason = "PAPER_AUDIT_FAIL_CONFIG_CHANGED"
    elif not calibration_hash_consistent:
        paper_audit_decision = Exp4ReuseDecision.SCIENTIFIC_FULL_RERUN
        paper_audit_reason = "PAPER_AUDIT_FAIL_CALIBRATION_CHANGED"
    elif not raw_simulation_artifacts_complete(run_dir):
        paper_audit_decision = Exp4ReuseDecision.NOT_REUSABLE
        paper_audit_reason = "PAPER_AUDIT_FAIL_RAW_OR_LINEAGE_INCOMPLETE"
    elif not stages["aggregation"]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.DOWNSTREAM_REBUILD
        paper_audit_reason = "PAPER_AUDIT_FAIL_DERIVED_STALE"
    elif not stages["validation"]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.DOWNSTREAM_REBUILD
        paper_audit_reason = "PAPER_AUDIT_FAIL_VALIDATION_STALE"
    elif not stages["reporting"]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.REPORTING_REBUILD
        paper_audit_reason = "PAPER_AUDIT_FAIL_REPORTING_STALE"
    else:
        paper_audit_decision = Exp4ReuseDecision.METADATA_ONLY
        paper_audit_reason = "PAPER_AUDIT_PASS_CURRENT"

    return {
        "audit_type": "exp4_run_provenance",
        "run_id": str(run_config.get("run_id", run_dir.name)),
        "stored_git_head_commit": str(run_config.get("code_commit", "")),
        "current_git_head_commit": _current_git_commit(base_dir),
        "stored_source_code_hash": stored_source_hash,
        "current_pre_fix_source_code_hash": current_source_hash,
        "source_hash_match": stored_source_hash == current_source_hash,
        "source_hash_algorithm_version_present": bool(
            run_config.get("source_hash_algorithm_version")
        ),
        "source_hash_algorithm_version": run_config.get(
            "source_hash_algorithm_version", "UNKNOWN"
        ),
        "expected_source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "config_hash_match": config_hash_match,
        "stored_calibration_hash": stored_calibration_hash,
        "calibration_hash_consistent": calibration_hash_consistent,
        "calibration_recompute_match": calibration_recompute_match,
        "exp4_worktree_dirty": worktree_dirty,
        "stage_source_hashes": stage_hashes,
        # --- Run lineage (actual execution, never inferred from hashes) ---
        "run_lineage_present": lineage_present,
        "run_lineage_valid": bool(lineage_ok),
        "run_lineage_reason": lineage_reason,
        "simulation_execution_mode": simulation_mode,
        "simulation_source_run_id": simulation_source_run_id,
        "downstream_execution_mode": downstream_mode,
        "downstream_source_run_id": downstream_source_run_id,
        # --- Formal Full gate ---
        "formal_full_clean_worktree_required": formal_full_clean_worktree_required,
        "formal_full_started_clean": formal_full_started_clean,
        # --- Stage comparisons ---
        "stages": stages,
        "all_stage_records_present": all_records_present,
        "all_relevant_stage_hashes_match": all_hashes_match,
        # --- Overall status ---
        "simulation_reuse_eligible": simulation_reuse_eligible,
        "simulation_provenance_verified": simulation_provenance_verified,
        "downstream_provenance_verified": downstream_provenance_verified,
        "reporting_provenance_verified": reporting_provenance_verified,
        "source_unchanged_during_run": source_unchanged,
        "raw_simulation_artifacts_complete": raw_simulation_artifacts_complete(run_dir),
        "reconciliation_artifact_present": _reconciliation_present(run_dir),
        "full_simulation_reuse_eligibility": reuse_eligibility,
        # Legacy compatibility field (renamed semantics):
        "full_simulation_reuse_decision": legacy_reuse_decision,
        "paper_audit_decision": paper_audit_decision.value,
        "paper_audit_failure_reason": paper_audit_reason,
        "required_action": paper_audit_decision.value,
    }


def recompute_calibration_hash(source_code_hash_value: str, config_hash_value: str) -> str:
    """Independently reproduce the calibration hash with the current logic."""
    from exp4.simulation.calibration import calibrate_proxy_route

    calibration, _, _ = calibrate_proxy_route(source_code_hash_value, config_hash_value)
    return calibration.calibration_hash


def write_provenance_reconciliation(
    run_dir: Path,
    base_dir: Path,
    rebuilt_stages: tuple[str, ...] = DOWNSTREAM_STAGE_NAMES,
    pre_rebuild_audit: dict[str, object] | None = None,
) -> Path:
    """Write a reconciliation artifact without overwriting original metadata."""
    run_config = _load_json(run_dir / "logs" / "run_config.json") or {}
    current_audit = audit_run_provenance(run_dir, base_dir)
    audit = pre_rebuild_audit or current_audit
    stage_hashes = dict(current_audit["stage_source_hashes"])
    reconciliation = {
        "original_run_id": str(run_config.get("run_id", run_dir.name)),
        "original_recorded_commit": run_config.get("code_commit"),
        "original_simulation_commit": run_config.get("code_commit"),
        "stored_simulation_source_hash": run_config.get("source_code_hash"),
        "current_rebuild_commit": current_audit["current_git_head_commit"],
        "simulation_outputs_reused": True,
        "raw_simulation_artifacts_complete": raw_simulation_artifacts_complete(
            run_dir
        ),
        "raw_path_manifest_hashes": {
            path.name: sha256_file(path)
            for path in (
                run_dir / "logs" / "exp4_module_a_path_manifest.csv",
                run_dir / "logs" / "exp4_module_bc_path_manifest.csv",
            )
            if path.exists()
        },
        "scientific_generation_hash_match": audit["stages"]["simulation"]["hash_match"],
        "config_hash_match": audit["config_hash_match"],
        "calibration_identity_match": audit["calibration_hash_consistent"],
        "rebuilt_stages": list(rebuilt_stages),
        "stored_stage_hashes": {
            key: audit["stages"][name]["stored_hash"]
            for name, key in STAGE_KEYS.items()
        },
        "current_stage_hashes": stage_hashes,
        "reconciliation_timestamp": _utc_now_iso(),
    }
    path = run_dir / "logs" / "exp4_provenance_reconciliation.json"
    write_json(reconciliation, path)
    return path


def write_stage_provenance_record(
    run_dir: Path,
    base_dir: Path,
    lineage: RunLineage | None = None,
    calibration_hash: str | None = None,
    source_unchanged_during_run: bool = True,
    rebuild: bool = False,
    rebuilt_stages: tuple[str, ...] = DOWNSTREAM_STAGE_NAMES,
) -> Path:
    """Write the v2 stage provenance record.

    ``rebuild=True`` (downstream rebuild) preserves the frozen simulation
    stage record and refreshes only the downstream stage hashes and modes.
    """
    stage_hashes = compute_stage_source_hashes(base_dir)
    existing = load_stage_provenance_record(run_dir)
    if calibration_hash is None and existing is not None:
        recorded_calibration = existing.get("calibration_hash")
        calibration_hash = (
            str(recorded_calibration) if recorded_calibration is not None else None
        )
    run_config = _load_json(run_dir / "logs" / "run_config.json") or {}
    lineage = lineage or load_run_lineage(run_dir)
    if lineage is None:
        simulation_mode = "UNKNOWN"
        simulation_source_run_id: str | None = None
        downstream_mode = "UNKNOWN"
        worktree_clean = bool(run_config.get("exp4_worktree_clean_at_start", False))
    else:
        simulation_mode = lineage.simulation_execution_mode
        simulation_source_run_id = lineage.simulation_source_run_id
        downstream_mode = lineage.downstream_execution_mode
        worktree_clean = lineage.exp4_worktree_clean_at_start

    stages: dict[str, dict[str, object]] = {}
    for name, key in STAGE_KEYS.items():
        if name == "simulation":
            if rebuild and existing is not None and name in existing.get("stages", {}):
                previous = existing["stages"][name]
                stages[name] = {
                    "source_hash": str(previous.get("source_hash") or ""),
                    "execution_mode": str(previous.get("execution_mode") or simulation_mode),
                    "source_run_id": previous.get("source_run_id"),
                }
            else:
                stages[name] = {
                    "source_hash": stage_hashes[key],
                    "execution_mode": simulation_mode,
                    "source_run_id": simulation_source_run_id,
                }
        elif rebuild and existing is not None and name not in rebuilt_stages:
            previous = existing.get("stages", {}).get(name, {})
            stages[name] = {
                "source_hash": str(previous.get("source_hash") or ""),
                "execution_mode": str(previous.get("execution_mode") or downstream_mode),
            }
        else:
            stages[name] = {
                "source_hash": stage_hashes[key],
                "execution_mode": downstream_mode,
            }
    payload = {
        "schema": STAGE_PROVENANCE_SCHEMA,
        "source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "recorded_git_commit": _current_git_commit(base_dir),
        "recorded_at": _utc_now_iso(),
        "complete_source_hash": compute_exp4_source_code_hash(base_dir),
        "config_hash": _current_config_hash(base_dir),
        "calibration_hash": calibration_hash,
        "exp4_worktree_clean_at_start": worktree_clean,
        "source_unchanged_during_run": source_unchanged_during_run,
        "downstream_rebuilt_at": _utc_now_iso() if rebuild else None,
        "downstream_rebuilt_stages": list(rebuilt_stages) if rebuild else [],
        "stages": stages,
    }
    path = run_dir / "logs" / "exp4_stage_provenance.json"
    write_json(payload, path)
    return path


def record_downstream_rebuild(
    run_dir: Path,
    base_dir: Path,
    rebuilt_stages: tuple[str, ...] = DOWNSTREAM_STAGE_NAMES,
) -> Path:
    """Refresh lineage + stage records after rebuilding downstream stages.

    The original simulation stage record is preserved; only the downstream
    stage hashes and modes are updated, and the lineage downstream mode is set
    to ``REBUILT_FROM_*`` accordingly.
    """
    lineage = mark_downstream_rebuilt(run_dir, base_dir)
    return write_stage_provenance_record(
        run_dir,
        base_dir,
        lineage=lineage,
        source_unchanged_during_run=False,
        rebuild=True,
        rebuilt_stages=rebuilt_stages,
    )


__all__ = [
    "DOWNSTREAM_STAGE_NAMES",
    "Exp4ReuseDecision",
    "STAGE_KEYS",
    "STAGE_PROVENANCE_SCHEMA",
    "audit_run_provenance",
    "compute_stage_source_hashes",
    "load_stage_provenance_record",
    "raw_simulation_artifacts_complete",
    "recompute_calibration_hash",
    "record_downstream_rebuild",
    "write_provenance_reconciliation",
    "write_stage_provenance_record",
]
