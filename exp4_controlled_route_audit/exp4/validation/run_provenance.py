"""Stage-level provenance and source-hash audit for Exp4 v2 runs.

A full Exp4 run has four downstream stages after the raw simulation:
aggregation, reporting, validation, and (implicitly) the pipeline wiring.
The single legacy ``source_code_hash`` covers all ``exp4/**/*.py`` files, which
cannot distinguish "simulation changed" from "reporting changed". This module
adds stage-level source hashes so a reused raw simulation can be reconciled
with rebuilt downstream stages without pretending the reporting hash is the
simulation hash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from exp4.outputs.writers import (
    SOURCE_HASH_ALGORITHM_VERSION,
    compute_exp4_source_code_hash,
    hash_files,
    write_json,
)

# Stage file-set definitions (relative to the experiment base dir).
# Configuration is a shared dependency of every stage and is included in every
# stage hash so that a frozen-config change is detected by all stages.
_SHARED_PREFIXES = ("exp4/configuration/",)

SIMULATION_STAGE_PREFIXES = _SHARED_PREFIXES + (
    "exp4/simulation/",
    "exp4/routes/",
    "exp4/audit/",
    "exp4/calibration/",
    "exp4/modules/",
    "exp4/execution/calibration_stage.py",
    "exp4/execution/module_a_stage.py",
    "exp4/execution/module_bc_stage.py",
    "exp4/execution/common.py",
)
SIMULATION_STAGE_FILES = (
    "exp4/metrics/action_gaps.py",
)

AGGREGATION_STAGE_PREFIXES = _SHARED_PREFIXES + (
    "exp4/reporting/aggregate_module_a.py",
    "exp4/reporting/aggregate_module_b.py",
    "exp4/reporting/aggregate_module_c.py",
    "exp4/execution/aggregation_stage.py",
)
AGGREGATION_STAGE_FILES = (
    "exp4/metrics/monte_carlo.py",
    "exp4/outputs/writers.py",
)

REPORTING_STAGE_PREFIXES = _SHARED_PREFIXES + (
    "exp4/reporting/",
    "exp4/outputs/writers.py",
    "exp4/outputs/manifests.py",
    "exp4/pipeline.py",
)
REPORTING_STAGE_FILES: tuple[str, ...] = ()

VALIDATION_STAGE_PREFIXES = _SHARED_PREFIXES + (
    "exp4/validation/",
    "exp4/outputs/writers.py",
    "exp4/pipeline.py",
)
VALIDATION_STAGE_FILES: tuple[str, ...] = ()

STAGE_SPECS = (
    ("simulation_source_hash", SIMULATION_STAGE_PREFIXES, SIMULATION_STAGE_FILES),
    ("aggregation_source_hash", AGGREGATION_STAGE_PREFIXES, AGGREGATION_STAGE_FILES),
    ("reporting_source_hash", REPORTING_STAGE_PREFIXES, REPORTING_STAGE_FILES),
    ("validation_source_hash", VALIDATION_STAGE_PREFIXES, VALIDATION_STAGE_FILES),
)


def _match(base_dir: Path, path: Path, prefixes: Iterable[str], files: Iterable[str]) -> bool:
    relative = path.relative_to(base_dir).as_posix()
    if relative in files:
        return True
    return any(relative.startswith(prefix) for prefix in prefixes)


def compute_stage_source_hashes(base_dir: Path) -> dict[str, str]:
    """Compute per-stage source hashes over the current working tree."""
    all_files = list((base_dir / "exp4").rglob("*.py"))
    hashes: dict[str, str] = {}
    for name, prefixes, files in STAGE_SPECS:
        stage_files = [path for path in all_files if _match(base_dir, path, prefixes, files)]
        hashes[name] = hash_files(stage_files)
    return hashes


def audit_run_provenance(run_dir: Path, base_dir: Path) -> dict[str, object]:
    """Read-only provenance audit for a completed run."""
    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    stored_source_hash = str(run_config.get("source_code_hash", ""))
    current_source_hash = compute_exp4_source_code_hash(base_dir)
    stage_hashes = compute_stage_source_hashes(base_dir)
    config_hash_match = str(run_config.get("config_hash", "")) == _current_config_hash(base_dir)
    worktree_dirty = _exp4_worktree_dirty(base_dir)
    return {
        "audit_type": "exp4_run_provenance",
        "run_id": run_config["run_id"],
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
        "exp4_worktree_dirty": worktree_dirty,
        "stage_source_hashes": stage_hashes,
        "full_simulation_reuse_decision": (
            "REUSE" if stored_source_hash == current_source_hash and config_hash_match else "DO_NOT_REUSE"
        ),
    }


def write_provenance_reconciliation(
    run_dir: Path, base_dir: Path, downstream_stages_rebuilt: bool = True
) -> Path:
    """Write a reconciliation artifact without overwriting original metadata."""
    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    audit = audit_run_provenance(run_dir, base_dir)
    stage_hashes = dict(audit["stage_source_hashes"])
    reconciliation = {
        "original_run_id": run_config["run_id"],
        "original_recorded_commit": run_config.get("code_commit"),
        "stored_simulation_source_hash": run_config.get("source_code_hash"),
        "verified_pre_fix_source_hash": audit["current_pre_fix_source_code_hash"],
        "current_post_fix_commit": audit["current_git_head_commit"],
        "post_fix_reporting_source_hash": stage_hashes.get("reporting_source_hash"),
        "post_fix_aggregation_source_hash": stage_hashes.get("aggregation_source_hash"),
        "post_fix_validation_source_hash": stage_hashes.get("validation_source_hash"),
        "simulation_outputs_reused": True,
        "downstream_stages_rebuilt": downstream_stages_rebuilt,
        "verification_timestamp": _utc_now_iso(),
        "file_level_hash_comparison": {
            "simulation_source_hash": stage_hashes.get("simulation_source_hash"),
            "config_hash_match": audit["config_hash_match"],
        },
    }
    path = run_dir / "logs" / "exp4_provenance_reconciliation.json"
    write_json(reconciliation, path)
    return path


def write_stage_provenance_record(run_dir: Path, base_dir: Path) -> Path:
    """Record current stage-level source hashes for a run (downstream rebuilds).

    The simulation_source_hash is only meaningful if the raw simulation was
    produced by the same simulation source; for a fresh run the pipeline writes
    this record after all stages complete.
    """
    stage_hashes = compute_stage_source_hashes(base_dir)
    payload = {
        "source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "current_git_head_commit": _current_git_commit(base_dir),
        "verification_timestamp": _utc_now_iso(),
        **stage_hashes,
    }
    path = run_dir / "logs" / "exp4_stage_provenance.json"
    write_json(payload, path)
    return path


def _current_config_hash(base_dir: Path) -> str:
    from exp4.outputs.writers import config_hash

    return config_hash()


def _current_git_commit(base_dir: Path) -> str:
    from exp4.outputs.writers import git_commit

    return git_commit(base_dir)


def _exp4_worktree_dirty(base_dir: Path) -> bool:
    import subprocess

    result = subprocess.run(
        ("git", "status", "--porcelain", "--", "exp4_controlled_route_audit"),
        cwd=base_dir,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _utc_now_iso() -> str:
    from exp4.outputs.writers import utc_now_iso

    return utc_now_iso()
