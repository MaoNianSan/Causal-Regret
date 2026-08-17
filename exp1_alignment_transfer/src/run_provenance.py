"""Stage-aware provenance, reuse decisions, and reconciliation for Exp1.

The raw simulator is intentionally separated from aggregation, validation,
and presentation code.  Reuse is never inferred from a Git commit or an
incidental source-tree match: an explicit lineage and stage-provenance record
is required before an existing scientific run may be rebuilt downstream.
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from src.artifact_io import (
    EXP1_STAGE_SOURCE_FILES,
    EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
    atomic_write_json,
    exp1_stage_source_hashes,
    git_commit,
    hash_payload,
    sha256_file,
    utc_now,
)


EXP1_STAGE_PROVENANCE_SCHEMA = "exp1_stage_provenance_v1"
EXP1_RUN_LINEAGE_SCHEMA = "exp1_run_lineage_v1"
EXP1_RECONCILIATION_SCHEMA = "exp1_provenance_reconciliation_v1"
EXP1_EXECUTION_CONTRACT_MIGRATION_SCHEMA = (
    "exp1_scientific_execution_contract_migration_v1"
)
EXP1_STAGE_CONFIG_MIGRATION_SCHEMA = "exp1_stage_config_provenance_migration_v1"
STAGE_HASH_NAMES = tuple(EXP1_STAGE_SOURCE_FILES)
STAGE_CONFIG_HASH_NAMES = (
    "scientific_generation_config_hash",
    "calibration_config_hash",
    "aggregation_config_hash",
    "validation_config_hash",
    "reporting_config_hash",
)
RAW_ARTIFACTS = (
    "raw/exp1_path_manifest.parquet",
    "raw/exp1_route_diagnostic_rounds.parquet",
    "raw/exp1_learner_consequence_rounds.parquet",
    "raw/exp1_delay_source_rounds.parquet",
    "seed_metrics/exp1_route_seed_metrics.parquet",
    "seed_metrics/exp1_learner_seed_metrics.parquet",
)


class Exp1ReuseDecision(str, Enum):
    SCIENTIFIC_FULL_RERUN = "SCIENTIFIC_FULL_RERUN"
    DOWNSTREAM_REBUILD = "DOWNSTREAM_REBUILD"
    VALIDATION_REBUILD = "VALIDATION_REBUILD"
    REPORTING_REBUILD = "REPORTING_REBUILD"
    METADATA_ONLY = "METADATA_ONLY"
    NOT_REUSABLE = "NOT_REUSABLE"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def run_lineage_path(run_dir: Path) -> Path:
    return run_dir / "metadata" / "exp1_run_lineage.json"


def stage_provenance_path(run_dir: Path) -> Path:
    return run_dir / "metadata" / "exp1_stage_provenance.json"


def reconciliation_path(run_dir: Path) -> Path:
    return run_dir / "metadata" / "exp1_provenance_reconciliation.json"


def execution_contract_migration_path(run_dir: Path) -> Path:
    return (
        run_dir
        / "metadata"
        / "exp1_scientific_execution_contract_migration.json"
    )


def stage_config_migration_path(run_dir: Path) -> Path:
    return run_dir / "metadata" / "exp1_stage_config_provenance_migration.json"


def calibration_stage_provenance_path(project_root: Path) -> Path:
    return project_root / "calibration" / "exp1_calibration_stage_provenance.json"


def _hash_historical_stage(
    project_root: Path, stage_name: str, relative_paths: Iterable[str], commit: str
) -> str:
    """Hash declared source files as they existed at a recorded Git commit."""
    try:
        git_root = Path(
            subprocess.check_output(
                ("git", "rev-parse", "--show-toplevel"),
                cwd=project_root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        project_relative = project_root.resolve().relative_to(git_root.resolve())
    except Exception as exc:  # pragma: no cover - exercised only outside Git
        raise RuntimeError("Cannot reconstruct historical Exp1 stage provenance") from exc

    import hashlib

    digest = hashlib.sha256()
    digest.update(EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update(stage_name.encode("utf-8"))
    digest.update(b"\0")
    for relative in sorted(relative_paths):
        git_path = (project_relative / relative).as_posix()
        try:
            content = subprocess.check_output(
                ("git", "show", f"{commit}:{git_path}"),
                cwd=project_root,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Cannot read {git_path} from recorded commit {commit}"
            ) from exc
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def historical_stage_source_hashes(project_root: Path, commit: str) -> dict[str, str]:
    """Compute all declared stage hashes from an explicit historical commit."""
    if not commit or commit == "unavailable":
        raise RuntimeError("Recorded commit is unavailable for historical provenance")
    return {
        stage: _hash_historical_stage(project_root, stage, files, commit)
        for stage, files in EXP1_STAGE_SOURCE_FILES.items()
    }


def _calibration_artifacts_consistent(project_root: Path, manifest: dict[str, Any]) -> bool:
    filenames = {
        "structural": "exp1_structural_calibration.json",
        "delay": "exp1_delay_calibration.json",
        "misbinding": "exp1_misbinding_calibration.json",
        "context": "exp1_context_partition.json",
    }
    payloads = {
        key: _load_json(project_root / "calibration" / filename)
        for key, filename in filenames.items()
    }
    if any(payload is None for payload in payloads.values()):
        return False
    actual = {key: hash_payload(payload) for key, payload in payloads.items()}
    return manifest.get("artifact_hashes") == actual


def ensure_calibration_stage_provenance(
    project_root: Path,
    manifest: dict[str, Any],
    *,
    allow_current_manifest: bool = False,
) -> dict[str, Any]:
    """Load explicit calibration-stage provenance or create it for a new run.

    Historical calibration artifacts must be migrated with
    :func:`bootstrap_existing_full_provenance`; this avoids silently assigning
    today\'s source hash to an old frozen calibration.
    """
    path = calibration_stage_provenance_path(project_root)
    existing = _load_json(path)
    if existing is not None and existing.get("schema") == EXP1_STAGE_PROVENANCE_SCHEMA:
        return existing

    current_commit = git_commit(project_root)
    if not allow_current_manifest or manifest.get("code_commit") != current_commit:
        raise RuntimeError(
            "Calibration stage provenance is missing. Reconcile the recorded calibration "
            "before reusing this scientific run."
        )
    stage_hashes = exp1_stage_source_hashes(project_root)
    from config import calibration_config_hash

    payload = {
        "schema": EXP1_STAGE_PROVENANCE_SCHEMA,
        "kind": "calibration",
        "recorded_at": utc_now(),
        "recorded_git_commit": current_commit,
        "calibration_manifest_hash": hash_payload(manifest),
        "legacy_complete_config_hash": manifest.get("effective_config_hash"),
        "config_hash": manifest.get("effective_config_hash"),
        "calibration_config_hash": calibration_config_hash(),
        "calibration_source_hash": stage_hashes["calibration_source_hash"],
        "bootstrap_mode": "FRESH_CURRENT_MANIFEST",
    }
    atomic_write_json(path, payload)
    return payload


def write_fresh_exp1_provenance(run_dir: Path, project_root: Path) -> tuple[Path, Path]:
    """Record stage source/config identities for a newly executed run."""
    state = _load_json(run_dir / "metadata" / "run_state.json") or {}
    manifest = _load_json(
        project_root / "calibration" / "exp1_calibration_manifest.json"
    ) or {}
    if not state or not manifest:
        raise RuntimeError("Fresh Exp1 provenance requires run state and calibration")
    run_tier = str(state.get("run_tier", ""))
    source_hashes = exp1_stage_source_hashes(project_root)
    config_hashes = _current_stage_config_hashes(project_root, manifest, run_tier)
    calibration_manifest_hash = hash_payload(manifest)
    recorded_at = utc_now()
    lineage = {
        "schema": EXP1_RUN_LINEAGE_SCHEMA,
        "run_id": state.get("run_id", run_dir.name),
        "run_tier": run_tier,
        "simulation_execution_mode": "FRESH",
        "simulation_source_run_id": None,
        "downstream_execution_mode": "FRESH",
        "downstream_source_run_id": None,
        "original_simulation_commit": state.get("code_commit"),
        "formal_full_verified": False,
        "legacy_complete_config_hash": state.get("config_hash"),
        "calibration_manifest_hash": calibration_manifest_hash,
        "source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        **source_hashes,
        **config_hashes,
        "recorded_at": recorded_at,
    }
    stage_record = {
        "schema": EXP1_STAGE_PROVENANCE_SCHEMA,
        "kind": "run",
        "run_id": state.get("run_id", run_dir.name),
        "run_tier": run_tier,
        "recorded_at": recorded_at,
        "recorded_git_commit": state.get("code_commit"),
        "original_simulation_commit": state.get("code_commit"),
        "simulation_execution_mode": "FRESH",
        "downstream_execution_mode": "FRESH",
        "legacy_complete_config_hash": state.get("config_hash"),
        "calibration_manifest_hash": calibration_manifest_hash,
        "source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "stage_source_hashes": source_hashes,
        "stage_config_hashes": config_hashes,
        "raw_artifacts": {
            relative: sha256_file(run_dir / relative)
            for relative in RAW_ARTIFACTS
            if (run_dir / relative).exists()
        },
        "bootstrap_mode": "FRESH_RUN",
    }
    atomic_write_json(run_lineage_path(run_dir), lineage)
    atomic_write_json(stage_provenance_path(run_dir), stage_record)
    return run_lineage_path(run_dir), stage_provenance_path(run_dir)


def bootstrap_existing_full_provenance(run_dir: Path, project_root: Path) -> tuple[Path, Path]:
    """Migrate a verified historical full run without touching scientific data."""
    state = _load_json(run_dir / "metadata" / "run_state.json")
    manifest = _load_json(project_root / "calibration" / "exp1_calibration_manifest.json")
    if state is None or manifest is None:
        raise RuntimeError("Existing Exp1 run state or calibration manifest is missing")
    if state.get("run_tier") != "full":
        raise RuntimeError("Only a verified Exp1 full run may be bootstrapped")
    if state.get("engineering_status") != "PASS" or state.get("scientific_status") != "PASS":
        raise RuntimeError("Historical Exp1 full is not scientifically verified")
    if not _calibration_artifacts_consistent(project_root, manifest):
        raise RuntimeError("Frozen Exp1 calibration artifacts are internally inconsistent")

    run_commit = str(state.get("code_commit", ""))
    calibration_commit = str(manifest.get("code_commit", ""))
    historical = historical_stage_source_hashes(project_root, run_commit)
    calibration_hash = _hash_historical_stage(
        project_root,
        "calibration_source_hash",
        EXP1_STAGE_SOURCE_FILES["calibration_source_hash"],
        calibration_commit,
    )
    historical["calibration_source_hash"] = calibration_hash
    calibration_manifest_hash = hash_payload(manifest)

    calibration_record = {
        "schema": EXP1_STAGE_PROVENANCE_SCHEMA,
        "kind": "calibration",
        "recorded_at": utc_now(),
        "recorded_git_commit": calibration_commit,
        "legacy_code_lineage": manifest.get("code_lineage"),
        "calibration_manifest_hash": calibration_manifest_hash,
        "config_hash": manifest.get("effective_config_hash"),
        "calibration_source_hash": calibration_hash,
        "bootstrap_mode": "HISTORICAL_COMMIT_RECONCILIATION",
    }
    atomic_write_json(calibration_stage_provenance_path(project_root), calibration_record)

    lineage = {
        "schema": EXP1_RUN_LINEAGE_SCHEMA,
        "run_id": state.get("run_id", run_dir.name),
        "run_tier": state.get("run_tier", "full"),
        "simulation_execution_mode": "FRESH",
        "simulation_source_run_id": None,
        "downstream_execution_mode": "FRESH",
        "downstream_source_run_id": None,
        "original_simulation_commit": run_commit,
        "formal_full_verified": True,
        "config_hash": state.get("config_hash"),
        "calibration_manifest_hash": calibration_manifest_hash,
        **historical,
        "recorded_at": utc_now(),
    }
    stage_record = {
        "schema": EXP1_STAGE_PROVENANCE_SCHEMA,
        "kind": "run",
        "run_id": state.get("run_id", run_dir.name),
        "run_tier": state.get("run_tier", "full"),
        "recorded_at": utc_now(),
        "recorded_git_commit": run_commit,
        "original_simulation_commit": run_commit,
        "simulation_execution_mode": "FRESH",
        "downstream_execution_mode": "FRESH",
        "config_hash": state.get("config_hash"),
        "calibration_manifest_hash": calibration_manifest_hash,
        "stage_source_hashes": historical,
        "raw_artifacts": {
            relative: sha256_file(run_dir / relative)
            for relative in RAW_ARTIFACTS
            if (run_dir / relative).exists()
        },
        "bootstrap_mode": "HISTORICAL_COMMIT_RECONCILIATION",
    }
    atomic_write_json(run_lineage_path(run_dir), lineage)
    atomic_write_json(stage_provenance_path(run_dir), stage_record)
    return run_lineage_path(run_dir), stage_provenance_path(run_dir)


def _original_scientific_checks_pass(run_dir: Path, state: dict[str, Any]) -> bool:
    report = _load_json(run_dir / "checks" / "exp1_validation_report.json")
    return bool(
        state.get("engineering_status") == "PASS"
        and state.get("scientific_status") == "PASS"
        and report is not None
        and report.get("engineering_status") == "PASS"
        and report.get("scientific_status") == "PASS"
    )


def raw_scientific_artifacts_complete(run_dir: Path) -> bool:
    return all((run_dir / relative).exists() for relative in RAW_ARTIFACTS)


def _raw_artifacts_unchanged(run_dir: Path, stage_record: dict[str, Any]) -> bool:
    stored = stage_record.get("raw_artifacts")
    if not isinstance(stored, dict) or not stored:
        return False
    return all(
        (run_dir / relative).exists()
        and sha256_file(run_dir / relative) == expected
        for relative, expected in stored.items()
    )


def _effective_run_configs(
    manifest: dict[str, Any], run_tier: str
) -> tuple[Any, Any]:
    from config import FAST_LEARNER, FAST_STRUCTURAL, LEARNER, STRUCTURAL
    from dataclasses import replace

    selected = manifest["effective_structural_config"]
    base_structural = FAST_STRUCTURAL if run_tier == "fast" else STRUCTURAL
    learner = FAST_LEARNER if run_tier == "fast" else LEARNER
    structural = replace(
        base_structural,
        ar_coefficient=float(selected["ar_coefficient"]),
        innovation_sd=float(selected["innovation_sd"]),
    )
    return structural, learner


def _current_stage_config_hashes(
    project_root: Path, manifest: dict[str, Any], run_tier: str
) -> dict[str, str]:
    try:
        from config import (
            aggregation_config_hash,
            calibration_config_hash,
            reporting_config_hash,
            scientific_generation_config_hash,
            validation_config_hash,
        )
        structural, learner = _effective_run_configs(manifest, run_tier)
        return {
            "scientific_generation_config_hash": scientific_generation_config_hash(
                run_tier, structural=structural, learner=learner
            ),
            "calibration_config_hash": calibration_config_hash(),
            "aggregation_config_hash": aggregation_config_hash(run_tier),
            "validation_config_hash": validation_config_hash(),
            "reporting_config_hash": reporting_config_hash(),
        }
    except Exception:
        return {}


def _current_config_hash(
    project_root: Path, manifest: dict[str, Any], run_tier: str
) -> str | None:
    """Legacy complete-config identity retained for artifact inspection."""
    try:
        from config import config_hash

        structural, learner = _effective_run_configs(manifest, run_tier)
        return config_hash(structural=structural, learner=learner)
    except Exception:
        return None


def audit_exp1_provenance(run_dir: Path, project_root: Path) -> dict[str, Any]:
    """Return the authoritative paper-audit decision for an Exp1 source run."""
    state = _load_json(run_dir / "metadata" / "run_state.json") or {}
    manifest = _load_json(project_root / "calibration" / "exp1_calibration_manifest.json") or {}
    lineage = _load_json(run_lineage_path(run_dir))
    stage_record = _load_json(stage_provenance_path(run_dir))
    calibration_record = _load_json(calibration_stage_provenance_path(project_root))
    current_hashes = exp1_stage_source_hashes(project_root)
    stored_hashes = (
        dict(stage_record.get("stage_source_hashes", {})) if stage_record else {}
    )
    calibration_manifest_hash = hash_payload(manifest) if manifest else None
    run_tier = str(state.get("run_tier", ""))
    current_config = _current_config_hash(project_root, manifest, run_tier) if manifest else None
    stored_config = state.get("config_hash")
    legacy_config_hash_match = bool(current_config and stored_config == current_config)
    current_config_hashes = (
        _current_stage_config_hashes(project_root, manifest, run_tier)
        if manifest
        else {}
    )
    stored_config_hashes = (
        dict(stage_record.get("stage_config_hashes", {})) if stage_record else {}
    )
    config_hash_matches = {
        name: bool(stored_config_hashes.get(name))
        and stored_config_hashes.get(name) == current_config_hashes.get(name)
        for name in STAGE_CONFIG_HASH_NAMES
    }
    calibration_source_hash_match = bool(
        calibration_record
        and calibration_record.get("calibration_source_hash")
        == current_hashes["calibration_source_hash"]
    )
    calibration_identity_match = bool(
        manifest
        and calibration_record
        and calibration_record.get("calibration_manifest_hash") == calibration_manifest_hash
        and calibration_record.get("calibration_config_hash")
        == current_config_hashes.get("calibration_config_hash")
        and _calibration_artifacts_consistent(project_root, manifest)
        and calibration_source_hash_match
    )
    stage_matches = {
        name: bool(stored_hashes.get(name))
        and stored_hashes.get(name) == current_hashes[name]
        for name in STAGE_HASH_NAMES
    }
    lineage_valid = bool(
        lineage
        and lineage.get("schema") == EXP1_RUN_LINEAGE_SCHEMA
        and lineage.get("simulation_execution_mode") in {"FRESH", "REUSED"}
        and (
            lineage.get("simulation_execution_mode") != "REUSED"
            or lineage.get("simulation_source_run_id")
        )
    )
    raw_complete = raw_scientific_artifacts_complete(run_dir)
    raw_unchanged = bool(stage_record and _raw_artifacts_unchanged(run_dir, stage_record))
    scientific_previously_verified = _original_scientific_checks_pass(run_dir, state)
    reconciliation_present = reconciliation_path(run_dir).exists()

    if not stage_matches["scientific_generation_source_hash"]:
        decision = Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN
        reason = "PAPER_AUDIT_FAIL_SIMULATION_HASH_CHANGED"
    elif not config_hash_matches["scientific_generation_config_hash"]:
        decision = Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN
        reason = "PAPER_AUDIT_FAIL_SCIENTIFIC_CONFIG_CHANGED"
    elif not calibration_identity_match:
        decision = Exp1ReuseDecision.SCIENTIFIC_FULL_RERUN
        reason = "PAPER_AUDIT_FAIL_CALIBRATION_CHANGED"
    elif not raw_complete or not raw_unchanged or not scientific_previously_verified or not lineage_valid:
        decision = Exp1ReuseDecision.NOT_REUSABLE
        reason = "PAPER_AUDIT_FAIL_RAW_OR_LINEAGE_INCOMPLETE"
    elif not stage_matches["aggregation_source_hash"] or not config_hash_matches[
        "aggregation_config_hash"
    ]:
        decision = Exp1ReuseDecision.DOWNSTREAM_REBUILD
        reason = "PAPER_AUDIT_FAIL_DERIVED_STALE"
    elif not stage_matches["validation_source_hash"] or not config_hash_matches[
        "validation_config_hash"
    ]:
        decision = Exp1ReuseDecision.VALIDATION_REBUILD
        reason = "PAPER_AUDIT_FAIL_VALIDATION_STALE"
    elif not stage_matches["reporting_source_hash"] or not config_hash_matches[
        "reporting_config_hash"
    ]:
        decision = Exp1ReuseDecision.REPORTING_REBUILD
        reason = "PAPER_AUDIT_FAIL_REPORTING_STALE"
    else:
        decision = Exp1ReuseDecision.METADATA_ONLY
        reason = "PAPER_AUDIT_PASS_CURRENT"

    scientific_reuse_eligible = bool(
        lineage_valid
        and stage_matches["scientific_generation_source_hash"]
        and config_hash_matches["scientific_generation_config_hash"]
        and calibration_identity_match
        and raw_complete
        and raw_unchanged
        and scientific_previously_verified
        and (lineage.get("simulation_execution_mode") == "FRESH" or reconciliation_present)
    )
    downstream_provenance_verified = bool(
        scientific_reuse_eligible
        and stage_matches["aggregation_source_hash"]
        and config_hash_matches["aggregation_config_hash"]
        and stage_matches["validation_source_hash"]
        and config_hash_matches["validation_config_hash"]
    )
    reporting_provenance_verified = bool(
        downstream_provenance_verified
        and stage_matches["reporting_source_hash"]
        and config_hash_matches["reporting_config_hash"]
    )
    return {
        "audit_type": "exp1_stage_aware_provenance",
        "run_id": state.get("run_id", run_dir.name),
        "stage_source_hashes": current_hashes,
        "stored_stage_hashes": stored_hashes,
        "stage_hash_matches": stage_matches,
        "stage_config_hashes": current_config_hashes,
        "stored_stage_config_hashes": stored_config_hashes,
        "stage_config_hash_matches": config_hash_matches,
        "scientific_generation_config_hash_match": config_hash_matches[
            "scientific_generation_config_hash"
        ],
        "legacy_complete_config_hash": stored_config,
        "current_legacy_complete_config_hash": current_config,
        "legacy_complete_config_hash_match": legacy_config_hash_match,
        "config_hash_match": config_hash_matches[
            "scientific_generation_config_hash"
        ],
        "calibration_identity_match": calibration_identity_match,
        "calibration_hash_internally_consistent": _calibration_artifacts_consistent(
            project_root, manifest
        )
        if manifest
        else False,
        "raw_scientific_artifacts_complete": raw_complete,
        "raw_scientific_artifacts_unchanged": raw_unchanged,
        "scientific_run_previously_verified": scientific_previously_verified,
        "run_lineage_present": lineage is not None,
        "run_lineage_valid": lineage_valid,
        "reconciliation_artifact_present": reconciliation_present,
        "simulation_provenance_verified": scientific_reuse_eligible,
        "downstream_provenance_verified": downstream_provenance_verified,
        "reporting_provenance_verified": reporting_provenance_verified,
        "scientific_reuse_eligible": scientific_reuse_eligible,
        "decision": decision.value,
        "required_action": decision.value,
        "failure_reason": reason,
    }


def exp1_scientific_reuse_eligible(run_dir: Path, project_root: Path) -> bool:
    """True only when raw Exp1 outputs meet every scientific reuse gate."""
    return bool(audit_exp1_provenance(run_dir, project_root)["scientific_reuse_eligible"])


def migrate_scientific_execution_contract(
    run_dir: Path,
    project_root: Path,
    frozen_calibration: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    """Migrate a semantics-preserving execution-contract extraction after replay."""
    state = _load_json(run_dir / "metadata" / "run_state.json") or {}
    stage_record = _load_json(stage_provenance_path(run_dir)) or {}
    lineage = _load_json(run_lineage_path(run_dir)) or {}
    audit = audit_exp1_provenance(run_dir, project_root)
    prerequisites = {
        "full_run": state.get("run_tier") == "full",
        "scientific_run_previously_verified": audit[
            "scientific_run_previously_verified"
        ],
        "config_hash_match": audit["config_hash_match"],
        "calibration_identity_match": audit["calibration_identity_match"],
        "raw_scientific_artifacts_complete": audit[
            "raw_scientific_artifacts_complete"
        ],
        "raw_scientific_artifacts_unchanged": audit[
            "raw_scientific_artifacts_unchanged"
        ],
        "run_lineage_valid": audit["run_lineage_valid"],
    }
    if not all(prerequisites.values()):
        raise RuntimeError(
            "Execution-contract migration prerequisites failed: "
            + json.dumps(prerequisites, sort_keys=True)
        )
    old_hash = str(
        stage_record.get("stage_source_hashes", {}).get(
            "scientific_generation_source_hash", ""
        )
    )
    new_hash = str(
        audit["stage_source_hashes"]["scientific_generation_source_hash"]
    )
    existing = _load_json(execution_contract_migration_path(run_dir))
    if old_hash == new_hash:
        if existing and existing.get("scientific_equivalence") == "PASS":
            return execution_contract_migration_path(run_dir), existing
        raise RuntimeError(
            "Scientific execution hash already matches but no PASS migration artifact exists"
        )

    from src.scientific_execution_replay import (
        DEFAULT_REPLAY_MECHANISMS,
        DEFAULT_REPLAY_SEEDS,
        replay_scientific_execution_contract,
    )

    raw_before = {
        relative: sha256_file(run_dir / relative) for relative in RAW_ARTIFACTS
    }
    replay = replay_scientific_execution_contract(run_dir, frozen_calibration)
    raw_after = {
        relative: sha256_file(run_dir / relative) for relative in RAW_ARTIFACTS
    }
    raw_unchanged = raw_before == raw_after
    migrated_at = utc_now()
    migration = {
        "schema": EXP1_EXECUTION_CONTRACT_MIGRATION_SCHEMA,
        "run_id": state.get("run_id", run_dir.name),
        "run_tier": state.get("run_tier"),
        "old_scientific_generation_source_hash": old_hash,
        "new_scientific_generation_source_hash": new_hash,
        "reason": "SEMANTICS_PRESERVING_EXECUTION_CONTRACT_EXTRACTION",
        "replay_seeds": list(DEFAULT_REPLAY_SEEDS),
        "replay_mechanisms": list(DEFAULT_REPLAY_MECHANISMS),
        "replay_comparison_results": replay["comparisons"],
        "scientific_equivalence": replay["scientific_equivalence"],
        "scientific_full_rerun_executed": False,
        "raw_scientific_artifacts_unchanged": raw_unchanged,
        "raw_artifact_hashes_before": raw_before,
        "raw_artifact_hashes_after": raw_after,
        "migration_prerequisites": prerequisites,
        "migrated_at": migrated_at,
    }
    atomic_write_json(execution_contract_migration_path(run_dir), migration)
    if replay["scientific_equivalence"] != "PASS" or not raw_unchanged:
        raise RuntimeError(
            "Scientific execution replay differed; SCIENTIFIC_FULL_RERUN_REQUIRED=TRUE"
        )

    stored_hashes = dict(stage_record.get("stage_source_hashes", {}))
    stored_hashes["scientific_generation_source_hash"] = new_hash
    stage_record.update(
        {
            "stage_source_hashes": stored_hashes,
            "scientific_execution_contract_migration": str(
                execution_contract_migration_path(run_dir).relative_to(run_dir)
            ).replace("\\", "/"),
            "scientific_execution_contract_migrated_at": migrated_at,
        }
    )
    lineage.update(
        {
            "scientific_generation_source_hash": new_hash,
            "scientific_execution_contract_migration": str(
                execution_contract_migration_path(run_dir).relative_to(run_dir)
            ).replace("\\", "/"),
            "scientific_execution_contract_migrated_at": migrated_at,
        }
    )
    atomic_write_json(stage_provenance_path(run_dir), stage_record)
    atomic_write_json(run_lineage_path(run_dir), lineage)
    return execution_contract_migration_path(run_dir), migration


def migrate_stage_config_provenance(
    run_dir: Path, project_root: Path
) -> tuple[Path, dict[str, Any]]:
    """Migrate a verified full run from monolithic to stage-aware config identity."""
    state = _load_json(run_dir / "metadata" / "run_state.json") or {}
    manifest = _load_json(
        project_root / "calibration" / "exp1_calibration_manifest.json"
    ) or {}
    stage_record = _load_json(stage_provenance_path(run_dir)) or {}
    lineage = _load_json(run_lineage_path(run_dir)) or {}
    calibration_record = _load_json(calibration_stage_provenance_path(project_root)) or {}
    execution_migration = _load_json(execution_contract_migration_path(run_dir)) or {}
    existing = _load_json(stage_config_migration_path(run_dir))

    raw_before = {
        relative: sha256_file(run_dir / relative)
        for relative in RAW_ARTIFACTS
        if (run_dir / relative).exists()
    }
    prerequisites = {
        "full_run": state.get("run_tier") == "full",
        "scientific_run_previously_verified": _original_scientific_checks_pass(
            run_dir, state
        ),
        "raw_scientific_artifacts_complete": raw_scientific_artifacts_complete(run_dir),
        "raw_scientific_artifacts_unchanged": _raw_artifacts_unchanged(
            run_dir, stage_record
        ),
        "execution_contract_replay_pass": execution_migration.get(
            "scientific_equivalence"
        )
        == "PASS",
        "calibration_artifacts_consistent": _calibration_artifacts_consistent(
            project_root, manifest
        ),
    }
    if not all(prerequisites.values()):
        raise RuntimeError(
            "Stage-config migration prerequisites failed: "
            + json.dumps(prerequisites, sort_keys=True)
        )

    run_commit = str(
        stage_record.get("original_simulation_commit")
        or state.get("code_commit")
        or ""
    )
    calibration_commit = str(
        calibration_record.get("recorded_git_commit")
        or manifest.get("code_commit")
        or ""
    )
    current_sources = exp1_stage_source_hashes(project_root)
    # The scientific execution module was extracted after the source run. Its
    # exact stored-output replay is the authoritative equivalence proof for
    # this source-layout migration; the historical commit cannot contain the
    # newly extracted path.
    historical_scientific_source = current_sources[
        "scientific_generation_source_hash"
    ]
    historical_calibration_source = _hash_historical_stage(
        project_root,
        "calibration_source_hash",
        EXP1_STAGE_SOURCE_FILES["calibration_source_hash"],
        calibration_commit,
    )
    source_equivalence = {
        "scientific_generation": execution_migration.get(
            "scientific_equivalence"
        )
        == "PASS",
        "calibration": historical_calibration_source
        == current_sources["calibration_source_hash"],
    }
    if not all(source_equivalence.values()):
        raise RuntimeError(
            "Corrected Exp1 stage source reconstruction differs; "
            "SCIENTIFIC_FULL_RERUN_REQUIRED=TRUE"
        )

    current_configs = _current_stage_config_hashes(
        project_root, manifest, str(state.get("run_tier", ""))
    )
    if set(current_configs) != set(STAGE_CONFIG_HASH_NAMES):
        raise RuntimeError("Current Exp1 stage config identities are incomplete")
    calibration_identity_pass = bool(
        calibration_record.get("calibration_manifest_hash") == hash_payload(manifest)
        and prerequisites["calibration_artifacts_consistent"]
        and source_equivalence["calibration"]
    )
    if not calibration_identity_pass:
        raise RuntimeError("Exp1 calibration scientific identity migration failed")

    raw_after = {
        relative: sha256_file(run_dir / relative)
        for relative in RAW_ARTIFACTS
        if (run_dir / relative).exists()
    }
    raw_unchanged = raw_before == raw_after
    migrated_at = utc_now()
    migration = {
        "schema": EXP1_STAGE_CONFIG_MIGRATION_SCHEMA,
        "migration_type": "MONOLITHIC_CONFIG_TO_STAGE_AWARE_CONFIG",
        "run_id": state.get("run_id", run_dir.name),
        "legacy_config_hash": state.get("config_hash"),
        "legacy_complete_config_hash": state.get("config_hash"),
        **current_configs,
        "old_source_hash_algorithm_version": stage_record.get(
            "source_hash_algorithm_version", "exp1-stage-source-v1"
        ),
        "new_source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "historically_reconstructed_scientific_generation_source_hash": historical_scientific_source,
        "scientific_generation_source_equivalence_method": "EXACT_STORED_OUTPUT_REPLAY",
        "current_scientific_generation_source_hash": current_sources[
            "scientific_generation_source_hash"
        ],
        "scientific_generation_equivalence": "PASS",
        "evidence": {
            "existing_execution_contract_replay": "PASS",
            "raw_artifact_immutability": "PASS" if raw_unchanged else "FAIL",
            "calibration_scientific_identity": (
                "PASS" if calibration_identity_pass else "FAIL"
            ),
        },
        "raw_artifact_hashes_before": raw_before,
        "raw_artifact_hashes_after": raw_after,
        "scientific_full_rerun_executed": False,
        "migrated_at": migrated_at,
    }
    atomic_write_json(stage_config_migration_path(run_dir), migration)
    if not raw_unchanged:
        raise RuntimeError("Exp1 raw artifacts changed during config migration")

    calibration_record.update(
        {
            "legacy_complete_config_hash": calibration_record.get("config_hash")
            or manifest.get("effective_config_hash"),
            "calibration_config_hash": current_configs["calibration_config_hash"],
            "calibration_source_hash": current_sources["calibration_source_hash"],
            "source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
            "stage_config_migrated_at": migrated_at,
        }
    )
    atomic_write_json(calibration_stage_provenance_path(project_root), calibration_record)

    stage_record.update(
        {
            "source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
            "legacy_complete_config_hash": stage_record.get("config_hash")
            or state.get("config_hash"),
            "stage_source_hashes": current_sources,
            "stage_config_hashes": current_configs,
            "stage_config_provenance_migration": str(
                stage_config_migration_path(run_dir).relative_to(run_dir)
            ).replace("\\", "/"),
            "stage_config_migrated_at": migrated_at,
        }
    )
    lineage.update(
        {
            "source_hash_algorithm_version": EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION,
            "legacy_complete_config_hash": lineage.get("config_hash")
            or state.get("config_hash"),
            **current_sources,
            **current_configs,
            "stage_config_provenance_migration": str(
                stage_config_migration_path(run_dir).relative_to(run_dir)
            ).replace("\\", "/"),
            "stage_config_migrated_at": migrated_at,
        }
    )
    atomic_write_json(stage_provenance_path(run_dir), stage_record)
    atomic_write_json(run_lineage_path(run_dir), lineage)
    return stage_config_migration_path(run_dir), migration


def record_exp1_reconciliation(
    run_dir: Path,
    project_root: Path,
    rebuilt_stages: Iterable[str],
    rebuilt_artifacts: dict[str, list[str]] | None = None,
) -> Path:
    """Write explicit downstream-rebuild lineage without altering raw artifacts."""
    rebuilt = tuple(dict.fromkeys(rebuilt_stages))
    if not rebuilt or any(stage not in {"aggregation", "validation", "reporting"} for stage in rebuilt):
        raise ValueError("rebuilt_stages must contain aggregation, validation, and/or reporting")
    audit = audit_exp1_provenance(run_dir, project_root)
    if not audit["scientific_reuse_eligible"]:
        raise RuntimeError(
            "Exp1 scientific reuse refused: " + str(audit["failure_reason"])
        )
    state = _load_json(run_dir / "metadata" / "run_state.json") or {}
    existing_lineage = _load_json(run_lineage_path(run_dir)) or {}
    original_stage_record = _load_json(stage_provenance_path(run_dir)) or {}
    stored = dict(original_stage_record.get("stage_source_hashes", {}))
    stored_config = dict(original_stage_record.get("stage_config_hashes", {}))
    current = dict(audit["stage_source_hashes"])
    current_config = dict(audit["stage_config_hashes"])
    key_by_stage = {
        "aggregation": "aggregation_source_hash",
        "validation": "validation_source_hash",
        "reporting": "reporting_source_hash",
    }
    for stage in rebuilt:
        stored[key_by_stage[stage]] = current[key_by_stage[stage]]
        stored_config[f"{stage}_config_hash"] = current_config[
            f"{stage}_config_hash"
        ]
    reconciliation = {
        "schema": EXP1_RECONCILIATION_SCHEMA,
        "source_run_id": state.get("run_id", run_dir.name),
        "original_simulation_commit": existing_lineage.get("original_simulation_commit"),
        "current_rebuild_commit": git_commit(project_root),
        "simulation_outputs_reused": True,
        "scientific_generation_hash_match": audit["stage_hash_matches"]["scientific_generation_source_hash"],
        "config_hash_match": audit["config_hash_match"],
        "calibration_identity_match": audit["calibration_identity_match"],
        "rebuilt_stages": list(rebuilt),
        "rebuilt_artifacts": rebuilt_artifacts or {},
        "stored_stage_hashes": dict(audit["stored_stage_hashes"]),
        "current_stage_hashes": current,
        "stored_stage_config_hashes": dict(audit["stored_stage_config_hashes"]),
        "current_stage_config_hashes": current_config,
        "reconciliation_timestamp": utc_now(),
    }
    atomic_write_json(reconciliation_path(run_dir), reconciliation)
    lineage = {
        **existing_lineage,
        "schema": EXP1_RUN_LINEAGE_SCHEMA,
        "simulation_execution_mode": existing_lineage.get(
            "simulation_execution_mode", "FRESH"
        ),
        "downstream_execution_mode": "REBUILT",
        "downstream_source_run_id": state.get("run_id", run_dir.name),
        "last_rebuilt_stages": list(rebuilt),
        "last_reconciled_at": utc_now(),
    }
    atomic_write_json(run_lineage_path(run_dir), lineage)
    stage_record = {
        **original_stage_record,
        "schema": EXP1_STAGE_PROVENANCE_SCHEMA,
        "downstream_execution_mode": "REBUILT",
        "stage_source_hashes": stored,
        "stage_config_hashes": stored_config,
        "downstream_rebuilt_at": utc_now(),
        "last_rebuilt_stages": list(rebuilt),
    }
    atomic_write_json(stage_provenance_path(run_dir), stage_record)
    return reconciliation_path(run_dir)


__all__ = [
    "EXP1_RECONCILIATION_SCHEMA",
    "EXP1_EXECUTION_CONTRACT_MIGRATION_SCHEMA",
    "EXP1_STAGE_CONFIG_MIGRATION_SCHEMA",
    "EXP1_RUN_LINEAGE_SCHEMA",
    "EXP1_STAGE_PROVENANCE_SCHEMA",
    "Exp1ReuseDecision",
    "STAGE_HASH_NAMES",
    "audit_exp1_provenance",
    "bootstrap_existing_full_provenance",
    "ensure_calibration_stage_provenance",
    "execution_contract_migration_path",
    "exp1_scientific_reuse_eligible",
    "historical_stage_source_hashes",
    "migrate_scientific_execution_contract",
    "migrate_stage_config_provenance",
    "raw_scientific_artifacts_complete",
    "record_exp1_reconciliation",
    "stage_config_migration_path",
    "write_fresh_exp1_provenance",
]
