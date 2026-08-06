"""Stage and final output manifests."""

from __future__ import annotations

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
        {"run_dir": str(run_dir), "file_count": len(records), "files": records},
        run_dir / "logs" / "output_manifest.json",
    )
    pd.DataFrame(records).to_csv(run_dir / "logs" / "output_manifest.csv", index=False)
