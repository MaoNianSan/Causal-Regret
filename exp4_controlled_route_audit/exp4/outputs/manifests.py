"""Stage and final output manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from exp4.outputs.writers import sha256_file, utc_now_iso, write_json


def stage_manifest_path(run_dir: Path, stage: str) -> Path:
    return run_dir / "logs" / "stages" / f"{stage}.json"


def stage_complete(run_dir: Path, stage: str) -> bool:
    path = stage_manifest_path(run_dir, stage)
    if not path.exists():
        return False
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("status") == "PASS"


def write_stage_manifest(
    run_dir: Path,
    stage: str,
    completed_tasks: int,
    artifacts: list[Path],
    metadata: dict[str, object] | None = None,
) -> None:
    write_json(
        {
            "stage": stage,
            "status": "PASS",
            "completed_tasks": int(completed_tasks),
            "completed_at": utc_now_iso(),
            "artifacts": {
                path.relative_to(run_dir).as_posix(): sha256_file(path)
                for path in artifacts
                if path.exists()
            },
            **(metadata or {}),
        },
        stage_manifest_path(run_dir, stage),
    )


def _run_lineage_summary(run_dir: Path) -> dict[str, object]:
    from exp4.outputs.run_lineage import load_run_lineage

    lineage = load_run_lineage(run_dir)
    if lineage is None:
        return {
            "run_lineage_schema": "MISSING",
            "simulation_execution_mode": "UNKNOWN",
            "simulation_source_run_id": None,
            "downstream_execution_mode": "UNKNOWN",
            "downstream_source_run_id": None,
        }
    return {
        "run_lineage_schema": "exp4_run_lineage_v1",
        "simulation_execution_mode": lineage.simulation_execution_mode,
        "simulation_source_run_id": lineage.simulation_source_run_id,
        "downstream_execution_mode": lineage.downstream_execution_mode,
        "downstream_source_run_id": lineage.downstream_source_run_id,
        "created_from_commit": lineage.created_from_commit,
        "exp4_worktree_clean_at_start": lineage.exp4_worktree_clean_at_start,
    }


def _find_base_dir(run_dir: Path) -> Path:
    for parent in run_dir.parents:
        if (parent / "exp4").is_dir():
            return parent
    return run_dir


def _provenance_summary(run_dir: Path) -> dict[str, object]:
    from exp4.outputs.writers import (
        SOURCE_HASH_ALGORITHM_VERSION,
        STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        compute_stage_source_hashes,
    )
    from exp4.validation.run_provenance import load_stage_provenance_record

    run_config_path = run_dir / "logs" / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8")) if run_config_path.exists() else {}
    stage_record = load_stage_provenance_record(run_dir)
    current = compute_stage_source_hashes(_find_base_dir(run_dir))
    return {
        "formal_full_clean_worktree_required": bool(
            run_config.get("formal_full_clean_worktree_required", False)
        ),
        "exp4_worktree_clean_at_start": bool(
            run_config.get("exp4_worktree_clean_at_start", False)
        ),
        "complete_source_hash": run_config.get("source_code_hash"),
        "simulation_stage_hash": current.get("simulation_source_hash"),
        "aggregation_stage_hash": current.get("aggregation_source_hash"),
        "reporting_stage_hash": current.get("reporting_source_hash"),
        "validation_stage_hash": current.get("validation_source_hash"),
        "source_hash_algorithm_version": STAGE_SOURCE_HASH_ALGORITHM_VERSION,
        "complete_source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
        "stage_provenance_schema": (
            str(stage_record.get("schema")) if stage_record is not None else "MISSING"
        ),
        "stage_config_hashes": (
            dict(stage_record.get("stage_config_hashes", {}))
            if stage_record is not None
            else {}
        ),
    }


def write_output_manifest(run_dir: Path) -> None:
    records: list[dict[str, object]] = []
    for path in sorted(candidate for candidate in run_dir.rglob("*") if candidate.is_file()):
        if path.name in {"output_manifest.json", "output_manifest.csv"}:
            continue
        records.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_json(
        {
            "run_dir": str(run_dir),
            "file_count": len(records),
            "files": records,
            "run_lineage": _run_lineage_summary(run_dir),
            "run_provenance": _provenance_summary(run_dir),
        },
        run_dir / "logs" / "output_manifest.json",
    )
    pd.DataFrame(records).to_csv(run_dir / "logs" / "output_manifest.csv", index=False)
