"""Auto-generated Exp4 v3 implementation status from the run registry.

The status report is derived from committed run configs, check payloads, and a
read-only provenance audit, so it cannot silently claim FULL_RUN_EXECUTED=NO
while a full run exists.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from exp4.configuration.schema import RESULT_SCHEMA
from exp4.outputs.writers import STAGE_SOURCE_HASH_ALGORITHM_VERSION
from exp4.validation.run_provenance import audit_run_provenance


def _run_metadata(run_dir: Path) -> dict[str, object] | None:
    config_path = run_dir / "logs" / "run_config.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    run_id = str(payload.get("run_id", run_dir.name))
    generated_at = str(payload.get("generated_at", ""))
    try:
        timestamp = datetime.fromisoformat(generated_at)
    except Exception:
        timestamp = datetime.min
    status_path = run_dir / "logs" / "exp4_result_status.json"
    result_status = (
        json.loads(status_path.read_text(encoding="utf-8"))
        if status_path.exists()
        else {}
    )
    engineering_path = run_dir / "checks" / "exp4_engineering_checks.json"
    scientific_path = run_dir / "checks" / "exp4_scientific_checks.json"
    engineering_status = (
        json.loads(engineering_path.read_text(encoding="utf-8")).get(
            "status", "MISSING"
        )
        if engineering_path.exists()
        else "MISSING"
    )
    scientific_status = (
        json.loads(scientific_path.read_text(encoding="utf-8")).get("status", "MISSING")
        if scientific_path.exists()
        else "MISSING"
    )
    return {
        "run_id": run_id,
        "run_tier": str(payload.get("run_tier", "")),
        "generated_at": generated_at,
        "timestamp": timestamp,
        "paper_result": bool(payload.get("paper_result", False)),
        "result_schema": str(payload.get("result_schema", "MISSING")),
        "result_status_paper_promotion": str(
            result_status.get("paper_promotion", "NOT_RUN")
        ),
        "engineering_status": engineering_status,
        "scientific_status": scientific_status,
    }


def scan_runs(base_dir: Path) -> dict[str, dict[str, object]]:
    runs: dict[str, dict[str, object]] = {}
    runs_dir = base_dir / "outputs" / "runs"
    if not runs_dir.exists():
        return runs
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        metadata = _run_metadata(run_dir)
        if metadata is None:
            continue
        tier = str(metadata["run_tier"])
        current = runs.get(tier)
        if current is None or metadata["timestamp"] > current["timestamp"]:
            runs[tier] = metadata
    return runs


def _load_check(run_dir: Path, name: str) -> dict[str, object] | None:
    path = run_dir / "checks" / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_implementation_status(base_dir: Path) -> dict[str, object]:
    runs = scan_runs(base_dir)
    latest = {
        tier: runs.get(tier, {}).get("run_id", "NONE")
        for tier in ("fast", "middle", "full")
    }
    full_run_id = latest.get("full")
    full_dir = (
        base_dir / "outputs" / "runs" / full_run_id if full_run_id != "NONE" else None
    )

    full_engineering = "NONE"
    full_scientific = "NONE"
    full_result_schema = "NONE"
    paper_promotion_status = "NOT_RUN"
    paper_result = False
    provenance: dict[str, object] = {}
    if full_dir is not None and full_dir.exists():
        full_engineering = str(runs["full"].get("engineering_status", "MISSING"))
        full_scientific = str(runs["full"].get("scientific_status", "MISSING"))
        full_result_schema = str(runs["full"].get("result_schema", "MISSING"))
        paper_promotion_status = str(
            runs["full"].get("result_status_paper_promotion", "NOT_RUN")
        )
        paper_result = bool(runs["full"].get("paper_result", False))
        provenance = audit_run_provenance(full_dir, base_dir)

    table_status = "NOT_BUILT"
    precision_status = "NOT_BUILT"
    checks_stale = False
    if full_dir is not None and full_dir.exists():
        table_checks = _load_check(full_dir, "exp4_table_checks.json")
        if table_checks is not None:
            table_status = str(table_checks.get("status", "MISSING"))
        precision_checks = _load_check(full_dir, "exp4_precision_checks.json")
        if precision_checks is not None:
            precision_status = str(precision_checks.get("status", "MISSING"))
        # New-style check artifacts mark a full run as rebuilt with the
        # post-fix validation; their absence means the stored checks are stale.
        checks_stale = not (
            (full_dir / "checks" / "exp4_table_checks.json").exists()
            and (full_dir / "checks" / "exp4_precision_checks.json").exists()
            and (full_dir / "logs" / "exp4_stage_provenance.json").exists()
        )

    # Verification mirrors the promotion contract (promote_results.py): the
    # stage-hash audit proves the frozen simulation is still valid after a
    # downstream rebuild. ``source_unchanged_during_run`` is a simulation-time
    # fact that is intentionally recorded as False after any downstream
    # rebuild, so it is NOT part of the verification gate.
    full_provenance_verified = bool(
        provenance
        and provenance.get("run_lineage_valid")
        and provenance.get("simulation_provenance_verified")
        and provenance.get("downstream_provenance_verified")
        and provenance.get("reporting_provenance_verified")
    )
    simulation_execution_mode = str(
        provenance.get("simulation_execution_mode", "UNKNOWN")
        if provenance
        else "UNKNOWN"
    )
    simulation_source_run_id = (
        provenance.get("simulation_source_run_id") if provenance else None
    )
    downstream_execution_mode = str(
        provenance.get("downstream_execution_mode", "UNKNOWN")
        if provenance
        else "UNKNOWN"
    )
    downstream_source_run_id = (
        provenance.get("downstream_source_run_id") if provenance else None
    )
    reuse_eligibility = str(
        provenance.get("full_simulation_reuse_eligibility", "UNKNOWN")
        if provenance
        else "UNKNOWN"
    )
    simulation_rerun_required = not full_provenance_verified
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "latest_fast_run": latest["fast"],
        "latest_middle_run": latest["middle"],
        "latest_full_run": latest["full"],
        "latest_full_result_schema": full_result_schema,
        "latest_full_interface_status": (
            "CURRENT_V3"
            if full_result_schema == RESULT_SCHEMA
            else "LEGACY_V2_PENDING_V3_REGENERATION"
        ),
        "full_run_engineering_status": full_engineering,
        "full_run_scientific_status": full_scientific,
        "full_run_checks_stale": checks_stale,
        "paper_promotion_status": paper_promotion_status,
        "paper_result": paper_result,
        "full_simulation_reuse_eligibility": reuse_eligibility,
        "full_simulation_execution_mode": simulation_execution_mode,
        "full_simulation_source_run_id": simulation_source_run_id,
        "downstream_execution_mode": downstream_execution_mode,
        "downstream_source_run_id": downstream_source_run_id,
        "FULL_SIMULATION_RERUN_REQUIRED": simulation_rerun_required,
        "provenance_status": "VERIFIED" if full_provenance_verified else "UNVERIFIED",
        "table_status": table_status,
        "monte_carlo_precision_status": precision_status,
        "FULL_RUN_EXECUTED": "YES" if full_run_id != "NONE" else "NO",
        "FULL_SIMULATION_REUSE_ELIGIBLE": {
            "ELIGIBLE": "YES",
            "NOT_ELIGIBLE": "NO",
            "UNKNOWN": "UNKNOWN",
        }.get(reuse_eligibility, "UNKNOWN"),
        "FULL_SIMULATION_EXECUTION_MODE": simulation_execution_mode,
        "FULL_SIMULATION_SOURCE_RUN_ID": (
            simulation_source_run_id
            if simulation_source_run_id
            else ("NONE" if simulation_execution_mode == "FRESH" else "UNKNOWN")
        ),
        "DOWNSTREAM_ARTIFACTS_EXECUTION_MODE": downstream_execution_mode,
        "DOWNSTREAM_SOURCE_RUN_ID": (
            downstream_source_run_id
            if downstream_source_run_id
            else (
                "NONE"
                if downstream_execution_mode
                in {"INLINE_FRESH", "REBUILT_FROM_OWN_SIMULATION"}
                else "UNKNOWN"
            )
        ),
        "PAPER_PROMOTION_EXECUTED": "YES" if paper_promotion_status == "PASS" else "NO",
    }


def write_implementation_status(base_dir: Path, path: Path) -> dict[str, object]:
    status = build_implementation_status(base_dir)
    lines = [
        "# Exp4 v3 Implementation Status",
        "",
        f"Status date: {status['generated_at']}",
        f"Current interface schema: `{RESULT_SCHEMA}`",
        f"Source hash algorithm: `{status['source_hash_algorithm_version']}`",
        f"Scope: `exp4_controlled_route_audit` only",
        "",
        "## Run Registry",
        "",
        f"- Latest fast run: `{status['latest_fast_run']}`",
        f"- Latest middle run: `{status['latest_middle_run']}`",
        f"- Latest full run: `{status['latest_full_run']}`",
        f"- Latest full result schema: `{status['latest_full_result_schema']}`",
        f"- Latest full interface status: `{status['latest_full_interface_status']}`",
        "",
        "## Full Run Status",
        "",
        f"- Full run engineering: `{status['full_run_engineering_status']}`",
        f"- Full run scientific: `{status['full_run_scientific_status']}`",
        f"- Full run checks stale: `{status['full_run_checks_stale']}`",
        f"- Paper promotion: `{status['paper_promotion_status']}`",
        f"- Paper result: `{status['paper_result']}`",
        f"- Table semantic check: `{status['table_status']}`",
        f"- Monte Carlo precision check: `{status['monte_carlo_precision_status']}`",
        f"- Provenance: `{status['provenance_status']}`",
        f"- Simulation reuse eligibility: `{status['full_simulation_reuse_eligibility']}`",
        f"- Simulation execution mode: `{status['full_simulation_execution_mode']}`",
        f"- Simulation source run: `{status['full_simulation_source_run_id']}`",
        f"- Downstream execution mode: `{status['downstream_execution_mode']}`",
        "",
        "## Execution Flags",
        "",
        f"FULL_RUN_EXECUTED={status['FULL_RUN_EXECUTED']}",
        f"FULL_SIMULATION_REUSE_ELIGIBLE={status['FULL_SIMULATION_REUSE_ELIGIBLE']}",
        f"FULL_SIMULATION_EXECUTION_MODE={status['FULL_SIMULATION_EXECUTION_MODE']}",
        f"FULL_SIMULATION_SOURCE_RUN_ID={status['FULL_SIMULATION_SOURCE_RUN_ID']}",
        f"FULL_SIMULATION_RERUN_REQUIRED={'YES' if status['FULL_SIMULATION_RERUN_REQUIRED'] else 'NO'}",
        f"DOWNSTREAM_ARTIFACTS_EXECUTION_MODE={status['DOWNSTREAM_ARTIFACTS_EXECUTION_MODE']}",
        f"DOWNSTREAM_SOURCE_RUN_ID={status['DOWNSTREAM_SOURCE_RUN_ID']}",
        f"PAPER_PROMOTION_EXECUTED={status['PAPER_PROMOTION_EXECUTED']}",
        "GIT_COMMIT_EXECUTED=NO",
        "GIT_PUSH_EXECUTED=NO",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status
