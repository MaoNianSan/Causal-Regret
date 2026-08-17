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
import hashlib
import ast
from pathlib import Path
import subprocess

from exp4.outputs.run_lineage import (
    RunLineage,
    lineage_valid,
    load_run_lineage,
    mark_downstream_rebuilt,
)
from exp4.outputs.writers import (
    SOURCE_HASH_ALGORITHM_VERSION,
    STAGE_SOURCE_FILES,
    STAGE_SOURCE_HASH_ALGORITHM_VERSION,
    compute_exp4_source_code_hash,
    compute_stage_source_hashes as writers_compute_stage_source_hashes,
    exp4_worktree_clean,
    git_commit,
    sha256_file,
    utc_now_iso,
    write_json,
)
from exp4.configuration.provenance import stage_config_hashes
from exp4.validation.provenance_checks import manifest_paths_are_relative_and_exist

STAGE_PROVENANCE_SCHEMA = "exp4_stage_provenance_v3"
LEGACY_STAGE_PROVENANCE_SCHEMA = "exp4_stage_provenance_v2"
STAGE_HASH_MIGRATION_SCHEMA = "exp4_stage_hash_migration_v1"

# Stage display names mapped to the flat source-hash keys.
STAGE_KEYS = {
    "simulation": "simulation_source_hash",
    "aggregation": "aggregation_source_hash",
    "reporting": "reporting_source_hash",
    "validation": "validation_source_hash",
}
DOWNSTREAM_STAGE_NAMES = ("aggregation", "reporting", "validation")
STAGE_CONFIG_KEYS = {
    "simulation": "scientific_config_hash",
    "aggregation": "aggregation_config_hash",
    "reporting": "reporting_config_hash",
    "validation": "validation_config_hash",
}


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


def _hash_historical_stage(base_dir: Path, key: str, commit: str) -> str:
    try:
        git_root = Path(
            subprocess.check_output(
                ("git", "rev-parse", "--show-toplevel"),
                cwd=base_dir,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        base_relative = base_dir.resolve().relative_to(git_root.resolve())
    except Exception as exc:
        raise RuntimeError("Cannot locate historical Exp4 source tree") from exc
    digest = hashlib.sha256()
    digest.update(STAGE_SOURCE_HASH_ALGORITHM_VERSION.encode("utf-8"))
    digest.update(b"\0")
    for relative in sorted(STAGE_SOURCE_FILES[key]):
        git_path = (base_relative / relative).as_posix()
        try:
            content = subprocess.check_output(
                ("git", "show", f"{commit}:{git_path}"),
                cwd=base_dir,
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


def historical_stage_source_hashes(base_dir: Path, commit: str) -> dict[str, str]:
    return {
        key: _hash_historical_stage(base_dir, key, commit) for key in STAGE_SOURCE_FILES
    }


def _historical_registry_order(
    base_dir: Path, commit: str, constant_name: str
) -> tuple[str, ...]:
    git_root = Path(
        subprocess.check_output(
            ("git", "rev-parse", "--show-toplevel"),
            cwd=base_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    )
    relative = (
        base_dir.resolve().relative_to(git_root.resolve())
        / "exp4/configuration/registries.py"
    ).as_posix()
    source = subprocess.check_output(
        ("git", "show", f"{commit}:{relative}"),
        cwd=base_dir,
        text=True,
        stderr=subprocess.DEVNULL,
    )
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == constant_name
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return tuple(str(item) for item in value)
    raise RuntimeError(f"Historical registry order missing: {constant_name}")


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


def _current_stage_config_hashes(run_tier: str) -> dict[str, str]:
    return stage_config_hashes(run_tier)


def _current_git_commit(base_dir: Path) -> str:
    return git_commit(base_dir)


def _exp4_worktree_dirty(base_dir: Path) -> bool:
    return not exp4_worktree_clean(base_dir)


def _utc_now_iso() -> str:
    return utc_now_iso()


def _alg_version_consistent(
    run_config: dict[str, object], stage_record: dict[str, object] | None = None
) -> bool:
    recorded = str(
        (stage_record or {}).get("source_hash_algorithm_version")
        or run_config.get("source_hash_algorithm_version", "")
    )
    return bool(recorded) and recorded == STAGE_SOURCE_HASH_ALGORITHM_VERSION


def load_stage_provenance_record(run_dir: Path) -> dict[str, object] | None:
    """Load the v2 stage provenance record; returns None for legacy layouts."""
    payload = _load_json(run_dir / "logs" / "exp4_stage_provenance.json")
    if payload is None or payload.get("schema") not in {
        STAGE_PROVENANCE_SCHEMA,
        LEGACY_STAGE_PROVENANCE_SCHEMA,
    }:
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


def _compare_stage_configs(
    run_config: dict[str, object],
    stage_record: dict[str, object] | None,
    current_hashes: dict[str, str],
) -> dict[str, dict[str, object]]:
    comparisons: dict[str, dict[str, object]] = {}
    recorded = (
        stage_record.get("stage_config_hashes", {}) if stage_record is not None else {}
    )
    for name, key in STAGE_CONFIG_KEYS.items():
        stored = str(recorded.get(key) or run_config.get(key) or "")
        current = current_hashes.get(key, "")
        comparisons[name] = {
            "stored_hash": stored,
            "current_hash": current,
            "hash_match": bool(stored) and stored == current,
            "record_present": bool(recorded.get(key)),
        }
    artifact_key = "artifact_metadata_config_hash"
    artifact_stored = str(recorded.get(artifact_key) or run_config.get(artifact_key) or "")
    comparisons["artifact_metadata"] = {
        "stored_hash": artifact_stored,
        "current_hash": current_hashes.get(artifact_key, ""),
        "hash_match": bool(artifact_stored)
        and artifact_stored == current_hashes.get(artifact_key, ""),
        "record_present": bool(recorded.get(artifact_key)),
    }
    return comparisons


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
    run_tier = str(run_config.get("run_tier", "full"))
    current_config_hashes = _current_stage_config_hashes(run_tier)
    legacy_config_hash_match = str(run_config.get("config_hash", "")) == _current_config_hash(base_dir)
    stored_calibration_hash = _stored_calibration_hash(run_dir, run_config)
    calibration_hash_consistent = _calibration_hash_consistent(run_dir, stored_calibration_hash)
    calibration_recompute_match: bool | None = None
    if (
        recompute_calibration
        and stored_calibration_hash
        and stored_source_hash
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
    stage_configs = _compare_stage_configs(
        run_config, stage_record, current_config_hashes
    )
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
        and stage_configs["simulation"]["record_present"]
        and stage_configs["simulation"]["hash_match"]
        and calibration_hash_consistent
        and raw_simulation_artifacts_complete(run_dir)
        and lineage_present
        and simulation_mode != "UNKNOWN"
        and _alg_version_consistent(run_config, stage_record)
        and (simulation_mode == "FRESH" or _reconciliation_present(run_dir))
    )
    simulation_provenance_verified = bool(simulation_reuse_eligible and lineage_ok)
    downstream_provenance_verified = bool(
        all(entry["record_present"] for entry in downstream_stages)
        and all(entry["hash_match"] for entry in downstream_stages)
        and all(
            stage_configs[name]["record_present"]
            and stage_configs[name]["hash_match"]
            for name in DOWNSTREAM_STAGE_NAMES
        )
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
    elif not stage_configs["simulation"]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.SCIENTIFIC_FULL_RERUN
        paper_audit_reason = "PAPER_AUDIT_FAIL_SCIENTIFIC_CONFIG_CHANGED"
    elif not calibration_hash_consistent:
        paper_audit_decision = Exp4ReuseDecision.SCIENTIFIC_FULL_RERUN
        paper_audit_reason = "PAPER_AUDIT_FAIL_CALIBRATION_CHANGED"
    elif not raw_simulation_artifacts_complete(run_dir):
        paper_audit_decision = Exp4ReuseDecision.NOT_REUSABLE
        paper_audit_reason = "PAPER_AUDIT_FAIL_RAW_OR_LINEAGE_INCOMPLETE"
    elif not stages["aggregation"]["hash_match"] or not stage_configs[
        "aggregation"
    ]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.DOWNSTREAM_REBUILD
        paper_audit_reason = "PAPER_AUDIT_FAIL_DERIVED_STALE"
    elif not stages["validation"]["hash_match"] or not stage_configs[
        "validation"
    ]["hash_match"]:
        paper_audit_decision = Exp4ReuseDecision.DOWNSTREAM_REBUILD
        paper_audit_reason = "PAPER_AUDIT_FAIL_VALIDATION_STALE"
    elif not stages["reporting"]["hash_match"] or not stage_configs[
        "reporting"
    ]["hash_match"]:
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
            (stage_record or {}).get("source_hash_algorithm_version")
            or run_config.get("source_hash_algorithm_version")
        ),
        "source_hash_algorithm_version": (stage_record or {}).get(
            "source_hash_algorithm_version"
        )
        or run_config.get("source_hash_algorithm_version", "UNKNOWN"),
        "expected_source_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "stage_config_hashes": current_config_hashes,
        "stage_configs": stage_configs,
        "scientific_config_hash_match": stage_configs["simulation"]["hash_match"],
        "legacy_complete_config_hash_match": legacy_config_hash_match,
        "config_hash_match": stage_configs["simulation"]["hash_match"],
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


def migrate_stage_hash_and_config_provenance(
    run_dir: Path, base_dir: Path
) -> tuple[Path, dict[str, object]]:
    """Migrate the August 17 full from v2 hashes/config to corrected identities."""
    run_config = _load_json(run_dir / "logs" / "run_config.json") or {}
    stage_record = load_stage_provenance_record(run_dir) or {}
    lineage = load_run_lineage(run_dir)
    if str(run_config.get("run_tier")) != "full":
        raise RuntimeError("Only a verified Exp4 full run may be migrated")
    if not raw_simulation_artifacts_complete(run_dir):
        raise RuntimeError("Exp4 raw simulation/path manifests are incomplete")

    raw_paths = [
        path
        for path in (
            *sorted((run_dir / "raw").rglob("*")),
            run_dir / "logs" / "exp4_module_a_path_manifest.csv",
            run_dir / "logs" / "exp4_module_bc_path_manifest.csv",
        )
        if path.is_file()
    ]
    raw_before = {path.relative_to(run_dir).as_posix(): sha256_file(path) for path in raw_paths}

    original_commit = str(
        (lineage.created_from_commit if lineage is not None else "")
        or run_config.get("code_commit", "")
    )
    recorded_stage_commit = str(stage_record.get("recorded_git_commit") or original_commit)
    historical_original = historical_stage_source_hashes(base_dir, original_commit)
    historical_recorded = historical_stage_source_hashes(base_dir, recorded_stage_commit)
    current_sources = compute_stage_source_hashes(base_dir)
    source_comparisons = {
        "simulation": {
            "historical": historical_original["simulation_source_hash"],
            "current": current_sources["simulation_source_hash"],
        },
        "aggregation": {
            "historical": historical_recorded["aggregation_source_hash"],
            "current": current_sources["aggregation_source_hash"],
        },
        "reporting": {
            "historical": historical_recorded["reporting_source_hash"],
            "current": current_sources["reporting_source_hash"],
        },
        "validation": {
            "historical": historical_recorded["validation_source_hash"],
            "current": current_sources["validation_source_hash"],
        },
    }
    source_equivalence = all(
        item["historical"] == item["current"] for item in source_comparisons.values()
    )

    frozen = run_config.get("frozen_configuration", {})
    stored_params = frozen.get("parameters", {}) if isinstance(frozen, dict) else {}
    stored_routes = frozen.get("route_registry", {}) if isinstance(frozen, dict) else {}
    stored_designs = (
        frozen.get("audit_design_registry", {}) if isinstance(frozen, dict) else {}
    )
    stored_controls = frozen.get("control_registry", {}) if isinstance(frozen, dict) else {}
    from exp4.configuration.provenance import scientific_config_payload
    from exp4.configuration.registries import (
        AUDIT_DESIGN_ORDER,
        AUDIT_DESIGN_REGISTRY,
        CONTROL_ORDER,
        ROUTE_ORDER,
        ROUTE_REGISTRY,
    )

    current_payload = json.loads(json.dumps(scientific_config_payload("full")))
    stored_scientific_payload = {
        **current_payload,
        "parameters": {
            "shared_dgp": stored_params.get("shared_dgp"),
            "module_a": stored_params.get("module_a"),
            "module_b": stored_params.get("module_b"),
            "calibration": stored_params.get("calibration"),
            "raw_pairwise_discrepancy_epsilon": stored_params.get("reporting", {}).get(
                "raw_pairwise_discrepancy_epsilon"
            ),
        },
        "route_registry_semantics": {
            key: {field: value for field, value in value.items() if field != "display_name"}
            for key, value in stored_routes.items()
        },
        "audit_design_registry_semantics": {
            key: {field: value for field, value in value.items() if field != "display_name"}
            for key, value in stored_designs.items()
        },
        "run_mode": {
            "module_a_seed_count": run_config.get("mode_settings", {}).get(
                "module_a_seed_count"
            ),
            "module_b_replications": run_config.get("mode_settings", {}).get(
                "module_b_replications"
            ),
        },
    }
    order_checks = {
        "route_order": _historical_registry_order(base_dir, original_commit, "ROUTE_ORDER")
        == ROUTE_ORDER,
        "audit_design_order": _historical_registry_order(
            base_dir, original_commit, "AUDIT_DESIGN_ORDER"
        )
        == AUDIT_DESIGN_ORDER,
        "control_order": _historical_registry_order(
            base_dir, original_commit, "CONTROL_ORDER"
        )
        == CONTROL_ORDER,
    }
    scientific_config_equivalence = bool(
        stored_scientific_payload["parameters"] == current_payload["parameters"]
        and stored_scientific_payload["route_registry_semantics"]
        == current_payload["route_registry_semantics"]
        and stored_scientific_payload["audit_design_registry_semantics"]
        == current_payload["audit_design_registry_semantics"]
        and set(stored_controls) == set(CONTROL_ORDER)
        and all(order_checks.values())
        and frozen.get("result_schema") == current_payload["scientific_contract_version"]
    )
    if not source_equivalence:
        migration = {
            "schema": STAGE_HASH_MIGRATION_SCHEMA,
            "old_hash_algorithm_version": run_config.get(
                "source_hash_algorithm_version", "UNKNOWN"
            ),
            "new_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
            "source_comparisons": source_comparisons,
            "ranking_diagnostics_inclusion": True,
            "scientific_simulation_equivalence": "FAIL",
            "human_decision_required": True,
            "scientific_full_rerun_executed": False,
        }
        path = run_dir / "logs" / "exp4_stage_hash_migration.json"
        write_json(migration, path)
        raise RuntimeError(
            "Corrected historical Exp4 simulation hash differs; HUMAN_DECISION_REQUIRED=YES"
        )
    if not scientific_config_equivalence:
        raise RuntimeError(
            "Recorded Exp4 scientific config differs from current scientific config"
        )

    current_configs = stage_config_hashes("full")
    raw_after = {path.relative_to(run_dir).as_posix(): sha256_file(path) for path in raw_paths}
    raw_unchanged = raw_before == raw_after
    migration = {
        "schema": STAGE_HASH_MIGRATION_SCHEMA,
        "old_hash_algorithm_version": run_config.get(
            "source_hash_algorithm_version", "UNKNOWN"
        ),
        "new_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "old_simulation_source_hash": stage_record.get("stages", {})
        .get("simulation", {})
        .get("source_hash"),
        "historically_reconstructed_new_simulation_hash": historical_original[
            "simulation_source_hash"
        ],
        "current_new_simulation_hash": current_sources["simulation_source_hash"],
        "ranking_diagnostics_inclusion": True,
        "scientific_simulation_equivalence": "PASS",
        "scientific_config_hash": current_configs["scientific_config_hash"],
        "recorded_scientific_config_matches": True,
        "raw_artifact_hashes_before": raw_before,
        "raw_artifact_hashes_after": raw_after,
        "raw_artifacts_unchanged": raw_unchanged,
        "scientific_full_rerun_executed": False,
        "human_decision_required": False,
        "migrated_at": _utc_now_iso(),
    }
    path = run_dir / "logs" / "exp4_stage_hash_migration.json"
    write_json(migration, path)
    if not raw_unchanged:
        raise RuntimeError("Exp4 raw artifacts changed during hash migration")

    config_migration = {
        "schema": "exp4_stage_config_provenance_migration_v1",
        "migration_type": "MONOLITHIC_CONFIG_TO_STAGE_AWARE_CONFIG",
        "legacy_config_hash": run_config.get("config_hash"),
        "scientific_config_hash": current_configs["scientific_config_hash"],
        "aggregation_config_hash": current_configs["aggregation_config_hash"],
        "validation_config_hash": current_configs["validation_config_hash"],
        "reporting_config_hash": current_configs["reporting_config_hash"],
        "artifact_metadata_config_hash": current_configs[
            "artifact_metadata_config_hash"
        ],
        "recorded_scientific_config_matches": True,
        "scientific_full_rerun_executed": False,
        "migrated_at": _utc_now_iso(),
    }
    config_path = run_dir / "logs" / "exp4_stage_config_migration.json"
    write_json(config_migration, config_path)

    stages = stage_record.get("stages", {})
    migrated_stages: dict[str, dict[str, object]] = {}
    for name, key in STAGE_KEYS.items():
        previous = stages.get(name, {})
        migrated_stages[name] = {
            "source_hash": current_sources[key],
            "execution_mode": previous.get("execution_mode", "UNKNOWN"),
            **(
                {"source_run_id": previous.get("source_run_id")}
                if name == "simulation"
                else {}
            ),
        }
    stage_record.update(
        {
            "schema": STAGE_PROVENANCE_SCHEMA,
            "source_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
            "complete_source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
            "stage_config_hashes": current_configs,
            "stages": migrated_stages,
            "stage_hash_migration": "logs/exp4_stage_hash_migration.json",
            "stage_config_migration": "logs/exp4_stage_config_migration.json",
            "migrated_at": _utc_now_iso(),
        }
    )
    write_json(stage_record, run_dir / "logs" / "exp4_stage_provenance.json")
    return path, migration


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
    config_hashes = dict(current_audit["stage_config_hashes"])
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
        "stored_stage_config_hashes": {
            key: current_audit["stage_configs"][name]["stored_hash"]
            for name, key in STAGE_CONFIG_KEYS.items()
        },
        "current_stage_config_hashes": config_hashes,
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
    config_hashes = _current_stage_config_hashes(
        str(run_config.get("run_tier", "full"))
    )
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
    stored_config_hashes = dict(
        existing.get("stage_config_hashes", {}) if existing is not None else {}
    )
    for name, key in STAGE_CONFIG_KEYS.items():
        if name == "simulation" and rebuild and stored_config_hashes.get(key):
            continue
        if rebuild and name not in rebuilt_stages and stored_config_hashes.get(key):
            continue
        stored_config_hashes[key] = config_hashes[key]
    stored_config_hashes["artifact_metadata_config_hash"] = config_hashes[
        "artifact_metadata_config_hash"
    ]
    payload = {
        "schema": STAGE_PROVENANCE_SCHEMA,
        "source_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "complete_source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "recorded_git_commit": _current_git_commit(base_dir),
        "recorded_at": _utc_now_iso(),
        "complete_source_hash": compute_exp4_source_code_hash(base_dir),
        "config_hash": run_config.get("config_hash") or _current_config_hash(base_dir),
        "legacy_complete_config_hash": run_config.get("config_hash")
        or _current_config_hash(base_dir),
        "stage_config_hashes": stored_config_hashes,
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
    "LEGACY_STAGE_PROVENANCE_SCHEMA",
    "STAGE_KEYS",
    "STAGE_PROVENANCE_SCHEMA",
    "STAGE_HASH_MIGRATION_SCHEMA",
    "audit_run_provenance",
    "compute_stage_source_hashes",
    "load_stage_provenance_record",
    "historical_stage_source_hashes",
    "migrate_stage_hash_and_config_provenance",
    "raw_simulation_artifacts_complete",
    "recompute_calibration_hash",
    "record_downstream_rebuild",
    "write_provenance_reconciliation",
    "write_stage_provenance_record",
]
