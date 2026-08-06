"""Auto-generated Exp4 v2 implementation status from the run registry.

The status report is derived from committed run configs, check payloads, and a
read-only provenance audit, so it cannot silently claim FULL_RUN_EXECUTED=NO
while a full run exists.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from exp4.outputs.writers import SOURCE_HASH_ALGORITHM_VERSION
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
        json.loads(engineering_path.read_text(encoding="utf-8")).get("status", "MISSING")
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
        "result_status_paper_promotion": str(result_status.get("paper_promotion", "NOT_RUN")),
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
    latest = {tier: runs.get(tier, {}).get("run_id", "NONE") for tier in ("fast", "middle", "full")}
    full_run_id = latest.get("full")
    full_dir = base_dir / "outputs" / "runs" / full_run_id if full_run_id != "NONE" else None

    full_engineering = "NONE"
    full_scientific = "NONE"
    paper_promotion_status = "NOT_RUN"
    paper_result = False
    provenance: dict[str, object] = {}
    if full_dir is not None and full_dir.exists():
        full_engineering = str(runs["full"].get("engineering_status", "MISSING"))
        full_scientific = str(runs["full"].get("scientific_status", "MISSING"))
        paper_promotion_status = str(runs["full"].get("result_status_paper_promotion", "NOT_RUN"))
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

    reuse_decision = str(provenance.get("full_simulation_reuse_decision", "UNKNOWN"))
    simulation_rerun_required = reuse_decision != "REUSE"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "latest_fast_run": latest["fast"],
        "latest_middle_run": latest["middle"],
        "latest_full_run": latest["full"],
        "full_run_engineering_status": full_engineering,
        "full_run_scientific_status": full_scientific,
        "full_run_checks_stale": checks_stale,
        "paper_promotion_status": paper_promotion_status,
        "paper_result": paper_result,
        "full_simulation_reuse_decision": reuse_decision,
        "FULL_SIMULATION_RERUN_REQUIRED": simulation_rerun_required,
        "provenance_status": "VERIFIED" if provenance.get("source_hash_match") else "UNVERIFIED",
        "table_status": table_status,
        "monte_carlo_precision_status": precision_status,
        "FULL_RUN_EXECUTED": "YES" if full_run_id != "NONE" else "NO",
        "FULL_SIMULATION_REUSED": "YES" if reuse_decision == "REUSE" else "NO",
        "DOWNSTREAM_ARTIFACTS_REBUILT": "YES" if reuse_decision == "REUSE" else "NO",
        "PAPER_PROMOTION_EXECUTED": "YES" if paper_promotion_status == "PASS" else "NO",
    }


def write_implementation_status(base_dir: Path, path: Path) -> dict[str, object]:
    status = build_implementation_status(base_dir)
    lines = [
        "# Exp4 v2 Implementation Status",
        "",
        f"Status date: {status['generated_at']}",
        f"Schema: `exp4_controlled_route_audit_v2`",
        f"Source hash algorithm: `{status['source_hash_algorithm_version']}`",
        f"Scope: `exp4_controlled_route_audit` only",
        "",
        "## Run Registry",
        "",
        f"- Latest fast run: `{status['latest_fast_run']}`",
        f"- Latest middle run: `{status['latest_middle_run']}`",
        f"- Latest full run: `{status['latest_full_run']}`",
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
        f"- Simulation reuse decision: `{status['full_simulation_reuse_decision']}`",
        "",
        "## Execution Flags",
        "",
        f"FULL_RUN_EXECUTED={status['FULL_RUN_EXECUTED']}",
        f"FULL_SIMULATION_REUSED={status['FULL_SIMULATION_REUSED']}",
        f"FULL_SIMULATION_RERUN_REQUIRED={'YES' if status['FULL_SIMULATION_RERUN_REQUIRED'] else 'NO'}",
        f"DOWNSTREAM_ARTIFACTS_REBUILT={status['DOWNSTREAM_ARTIFACTS_REBUILT']}",
        f"PAPER_PROMOTION_EXECUTED={status['PAPER_PROMOTION_EXECUTED']}",
        "GIT_COMMIT_EXECUTED=NO",
        "GIT_PUSH_EXECUTED=NO",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status
