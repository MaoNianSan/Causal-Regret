from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from contracts import EXPERIMENT_ID, EXPERIMENT_SLUG, EXPERIMENT_TITLE, SCHEMA_VERSION

from ..raw_data import canonical_json_hash, file_sha256, load_config, write_json
from ..validation import validate_frozen_configuration


@dataclass(frozen=True)
class RunPaths:
    root: Path
    derived: Path
    figures: Path
    tables: Path
    audit: Path
    logs: Path
    manifest: Path


@dataclass
class RunContext:
    mode: str
    project_root: Path
    config_file: Path
    config: dict[str, Any]
    paths: RunPaths
    run_id: str
    config_hash: str
    code_identity: str
    table_format: str
    manifest: dict[str, Any]


def now_local() -> datetime:
    return datetime.now().astimezone()


def _run_id(mode: str) -> str:
    return f"exp2-{mode}-{now_local().strftime('%Y%m%dT%H%M%S%z')}"


def code_identity(root: Path) -> str:
    files = sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return canonical_json_hash(
        {str(path.relative_to(root)): path.read_bytes().hex() for path in files}
    )


def create_paths(project_root: Path, mode: str) -> RunPaths:
    run_root = project_root / "outputs" / _run_id(mode)
    paths = RunPaths(
        root=run_root,
        derived=run_root / "derived",
        figures=run_root / "figures",
        tables=run_root / "tables",
        audit=run_root / "audit",
        logs=run_root / "logs",
        manifest=run_root / "run_manifest.json",
    )
    for directory in (paths.root, paths.derived, paths.figures, paths.tables, paths.audit, paths.logs):
        directory.mkdir(parents=True, exist_ok=False if directory == paths.root else True)
    return paths


def log_stage(index: int, total: int, title: str) -> None:
    print(f"\n[{index}/{total}] {title}", flush=True)


def write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def initialize_context(
    mode: str,
    *,
    config_path: str | Path | None,
    input_path: str | Path | None,
    n_bootstrap: int | None,
    n_jobs: str | int | None,
) -> RunContext:
    project_root = Path(__file__).resolve().parents[2]
    config_file = Path(config_path) if config_path is not None else project_root / "config.yaml"
    config = load_config(config_file)
    validate_frozen_configuration(config)
    paths = create_paths(project_root, mode)
    config_hash = canonical_json_hash(config)
    identity = code_identity(project_root)
    table_format = str(
        config["storage"]["fast_large_table_format" if mode == "fast" else "full_large_table_format"]
    )
    manifest: dict[str, Any] = {
        "run_id": paths.root.name,
        "experiment_id": EXPERIMENT_ID,
        "experiment_slug": EXPERIMENT_SLUG,
        "experiment_title": EXPERIMENT_TITLE,
        "schema_version": SCHEMA_VERSION,
        "run_tier": mode,
        "paper_result": False,
        "status": "RUNNING",
        "engineering_status": "PENDING",
        "scientific_status": "PENDING",
        "paper_promotion_status": "INELIGIBLE_FAST" if mode == "fast" else "PENDING",
        "started_at": now_local().isoformat(),
        "code_identity": identity,
        "config_path": (
            str(config_file.resolve().relative_to(project_root))
            if config_file.resolve().is_relative_to(project_root)
            else str(config_file.resolve())
        ),
        "config_hash": config_hash,
        "large_table_format": table_format,
        "development_override": n_bootstrap is not None or n_jobs is not None or input_path is not None,
    }
    write_json(manifest, paths.manifest)
    return RunContext(
        mode=mode,
        project_root=project_root,
        config_file=config_file,
        config=config,
        paths=paths,
        run_id=paths.root.name,
        config_hash=config_hash,
        code_identity=identity,
        table_format=table_format,
        manifest=manifest,
    )


def write_artifact_manifest(run_root: Path, output_path: Path) -> None:
    rows = []
    for path in sorted(run_root.rglob("*")):
        if not path.is_file() or path == output_path:
            continue
        rows.append(
            {
                "relative_path": path.relative_to(run_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    write_json(
        {"schema_version": SCHEMA_VERSION, "artifact_count": len(rows), "artifacts": rows},
        output_path,
    )
