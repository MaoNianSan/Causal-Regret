"""Run directories, metadata, hashes, and artifact storage utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable
import uuid

import pandas as pd

import config


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_tier: str
    run_dir: Path
    code_commit: str
    config_hash: str
    input_manifest_hash: str
    result_schema: str = config.RESULT_SCHEMA
    paper_result: bool = False

    def common_metadata(
        self,
        module_id: str,
        analysis_tier: str,
        configuration_id: str,
        seed_or_replication: int | str,
    ) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "run_tier": self.run_tier,
            "paper_result": self.paper_result,
            "analysis_tier": analysis_tier,
            "experiment_id": config.EXPERIMENT_ID,
            "module_id": module_id,
            "configuration_id": configuration_id,
            "seed_or_replication": seed_or_replication,
            "code_commit": self.code_commit,
            "config_hash": self.config_hash,
            "input_manifest_hash": self.input_manifest_hash,
            "result_schema": self.result_schema,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "UNAVAILABLE"


def create_run_context(run_tier: str) -> RunContext:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_tier}_{timestamp}_{uuid.uuid4().hex[:8]}"
    run_dir = config.OUTPUT_ROOT / run_id
    for relative in [
        "raw/trajectories",
        "raw/route_maps",
        "derived",
        "figures/pdf",
        "figures/png",
        "figures/data",
        "figures/metadata",
        "tables",
        "checks",
        "reports",
        "logs",
    ]:
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    return RunContext(
        run_id=run_id,
        run_tier=run_tier,
        run_dir=run_dir,
        code_commit=git_commit(config.BASE_DIR),
        config_hash=config.config_hash(),
        input_manifest_hash=config.synthetic_input_manifest_hash(),
    )


def attach_metadata(
    frame: pd.DataFrame,
    run_context: RunContext,
    module_id: str,
    analysis_tier: str,
    configuration_id: str | None = None,
    seed_or_replication_column: str | None = None,
) -> pd.DataFrame:
    output = frame.copy()
    output.insert(0, "run_id", run_context.run_id)
    output.insert(1, "run_tier", run_context.run_tier)
    output.insert(2, "paper_result", run_context.paper_result)
    output.insert(3, "analysis_tier", analysis_tier)
    output.insert(4, "experiment_id", config.EXPERIMENT_ID)
    output.insert(5, "module_id", module_id)
    if configuration_id is not None and "configuration_id" not in output.columns:
        output.insert(6, "configuration_id", configuration_id)
    if "seed_or_replication" not in output.columns:
        if seed_or_replication_column and seed_or_replication_column in output.columns:
            position = min(7, len(output.columns))
            output.insert(
                position,
                "seed_or_replication",
                output[seed_or_replication_column],
            )
        else:
            position = min(7, len(output.columns))
            output.insert(position, "seed_or_replication", "aggregate")
    output["code_commit"] = run_context.code_commit
    output["config_hash"] = run_context.config_hash
    output["input_manifest_hash"] = run_context.input_manifest_hash
    output["result_schema"] = run_context.result_schema
    return output


def require_pyarrow() -> tuple[object, object]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError(
            "The frozen output contract requires Parquet. Install dependencies with "
            "`python -m pip install -r requirements.txt` before running Exp4."
        ) from exc
    return pa, pq


def write_parquet(frame: pd.DataFrame, output_path: Path) -> None:
    pa, pq = require_pyarrow()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    pq.write_table(table, output_path, compression="zstd")


class ParquetBatchWriter:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = None
        self._pa, self._pq = require_pyarrow()

    def write(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        table = self._pa.Table.from_pandas(frame, preserve_index=False)
        if self._writer is None:
            self._writer = self._pq.ParquetWriter(
                self.output_path, table.schema, compression="zstd"
            )
        self._writer.write_table(table)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def __enter__(self) -> "ParquetBatchWriter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(payload: object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_run_config(run_context: RunContext, mode_settings: dict[str, object]) -> None:
    payload = {
        "run_id": run_context.run_id,
        "run_tier": run_context.run_tier,
        "paper_result": False,
        "is_paper_eligible": False,
        "experiment_id": config.EXPERIMENT_ID,
        "experiment_display_name": config.EXPERIMENT_DISPLAY_NAME,
        "result_schema": config.RESULT_SCHEMA,
        "code_commit": run_context.code_commit,
        "config_hash": run_context.config_hash,
        "input_manifest_hash": run_context.input_manifest_hash,
        "generated_at": utc_now_iso(),
        "mode_settings": mode_settings,
        "frozen_configuration": config.frozen_config_payload(),
    }
    write_json(payload, run_context.run_dir / "logs" / "run_config.json")


def write_output_manifest(run_dir: Path) -> None:
    files: list[dict[str, object]] = []
    for path in sorted(candidate for candidate in run_dir.rglob("*") if candidate.is_file()):
        if path.name in {"output_manifest.json", "output_manifest.csv"}:
            continue
        files.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_json(
        {"run_dir": str(run_dir), "files": files},
        run_dir / "logs" / "output_manifest.json",
    )
    pd.DataFrame(files).to_csv(
        run_dir / "logs" / "output_manifest.csv", index=False
    )


def file_hash_mapping(paths: Iterable[Path]) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in paths}
