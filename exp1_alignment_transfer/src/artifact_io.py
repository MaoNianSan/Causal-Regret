from __future__ import annotations

"""Atomic artifact I/O, schema checks, and content hashing."""

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable

import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # paper/full runs will fail explicitly when streaming is used
    pa = None
    pq = None

from src.contracts import ArtifactError, ContractError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json_bytes(payload: Any) -> bytes:
    if is_dataclass(payload):
        payload = asdict(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def hash_payload(payload: Any) -> str:
    return sha256_bytes(stable_json_bytes(payload))


def _json_default(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )
    tmp.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def validate_columns(frame: pd.DataFrame, required: Iterable[str], artifact_name: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ContractError(f"{artifact_name} missing required columns: {missing}")


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    tmp.replace(path)


def atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    """Write parquet or fail explicitly.

    Development environments without a parquet engine may set
    ``EXP1_DEV_CSV_FALLBACK=1``.  This writes a sibling CSV, marks the run as
    non-paper, and never masquerades as a parquet artifact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        frame.to_parquet(tmp, index=False)
        tmp.replace(path)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        if os.environ.get("EXP1_DEV_CSV_FALLBACK") != "1":
            raise ArtifactError(
                "Parquet output requires pyarrow or fastparquet. Install the declared "
                "dependency; no silent fallback is permitted."
            ) from exc
        csv_path = path.with_suffix(".dev.csv")
        atomic_write_csv(csv_path, frame)
        marker = {
            "requested_artifact": str(path.name),
            "development_fallback": str(csv_path.name),
            "paper_result": False,
            "reason": "parquet_engine_unavailable",
            "generated_at": utc_now(),
        }
        atomic_write_json(path.with_suffix(path.suffix + ".fallback.json"), marker)


def read_frame(path: Path) -> pd.DataFrame:
    if path.exists():
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".csv":
            return pd.read_csv(path)
    dev = path.with_suffix(".dev.csv") if path.suffix == ".parquet" else None
    if dev is not None and dev.exists() and os.environ.get("EXP1_DEV_CSV_FALLBACK") == "1":
        return pd.read_csv(dev)
    raise ArtifactError(f"Artifact not found: {path}")


EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION = "exp1-stage-source-v1"

# The stage definitions deliberately exclude orchestration and generic I/O.
# Those files can change provenance or artifact layout without changing a raw
# trajectory, seed-level metric, or frozen calibration value.
EXP1_STAGE_SOURCE_FILES: dict[str, tuple[str, ...]] = {
    "scientific_generation_source_hash": (
        "config.py",
        "src/contracts.py",
        "src/delay_mechanisms.py",
        "src/delayed_exp3.py",
        "src/metrics.py",
        "src/path_generator.py",
        "src/route_maps.py",
        "src/runner.py",
        "src/scientific_execution.py",
        "src/structural_process.py",
    ),
    "calibration_source_hash": (
        "config.py",
        "calibrate.py",
        "src/contracts.py",
        "src/delay_mechanisms.py",
        "src/metrics.py",
        "src/route_maps.py",
        "src/structural_process.py",
    ),
    "aggregation_source_hash": ("src/derived.py",),
    "validation_source_hash": (
        "self_check.py",
        "targeted.py",
        "src/theory_sweeps.py",
        "src/scientific_execution_replay.py",
    ),
    "reporting_source_hash": ("plot_main.py", "plot_appendix.py", "promote.py"),
}


def _hash_relative_source_bytes(
    project_root: Path, stage_name: str, relative_paths: Iterable[str]
) -> str:
    """Hash a declared source stage with paths independent of the checkout."""
    digest = hashlib.sha256()
    digest.update(EXP1_STAGE_SOURCE_HASH_ALGORITHM_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update(stage_name.encode("utf-8"))
    digest.update(b"\0")
    for relative in sorted(relative_paths):
        path = project_root / relative
        if not path.exists():
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def exp1_stage_source_hashes(project_root: Path) -> dict[str, str]:
    """Return authoritative stage hashes for Exp1 reuse decisions.

    A hash change in aggregation, validation, or reporting is intentionally
    not evidence that a scientific simulation has changed.
    """
    root = project_root.resolve()
    return {
        stage: _hash_relative_source_bytes(root, stage, files)
        for stage, files in EXP1_STAGE_SOURCE_FILES.items()
    }


def source_tree_fingerprint(project_root: Path) -> str:
    """Legacy package-wide fingerprint retained for historical artifacts.

    New reuse and calibration decisions use :func:`exp1_stage_source_hashes`.
    This value remains available only so older run metadata can be inspected
    without being silently reinterpreted as a scientific-stage hash.
    """
    h = hashlib.sha256()
    candidates = [
        project_root / "config.py",
        project_root / "calibrate.py",
        project_root / "main.py",
        project_root / "self_check.py",
        project_root / "targeted.py",
        project_root / "plot_main.py",
        project_root / "plot_appendix.py",
        project_root / "promote.py",
    ] + sorted((project_root / "src").glob("*.py"))
    for file_path in candidates:
        if file_path.exists():
            h.update(str(file_path.relative_to(project_root)).encode("utf-8"))
            h.update(file_path.read_bytes())
    return "tree:" + h.hexdigest()


def git_commit(project_root: Path) -> str:
    """Return the containing repository commit for provenance, when available."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unavailable"


def code_lineage(project_root: Path) -> str:
    """Return the legacy package-local lineage used by pre-stage artifacts."""
    return source_tree_fingerprint(project_root)


class ParquetStreamWriter:
    """Write DataFrame chunks without retaining all rounds.

    Paper/full execution requires pyarrow and writes one parquet file. A development
    environment may set EXP1_DEV_CSV_FALLBACK=1; chunks are then appended to the
    explicitly marked sibling ``.dev.csv`` artifact and can never be promoted.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp = path.with_suffix(path.suffix + ".tmp")
        self.writer = None
        self.schema = None
        self.dev_mode = pa is None or pq is None
        if self.dev_mode and os.environ.get("EXP1_DEV_CSV_FALLBACK") != "1":
            raise ArtifactError("Streaming parquet output requires pyarrow")
        self.dev_path = path.with_suffix(".dev.csv")
        self.dev_tmp = self.dev_path.with_suffix(self.dev_path.suffix + ".tmp")
        self._dev_header_written = False

    def write(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        if self.dev_mode:
            frame.to_csv(
                self.dev_tmp,
                mode="a",
                index=False,
                header=not self._dev_header_written,
            )
            self._dev_header_written = True
            return
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if self.writer is None:
            self.schema = table.schema
            self.writer = pq.ParquetWriter(self.tmp, self.schema, compression="snappy")
        else:
            try:
                table = table.cast(self.schema)
            except Exception as exc:
                raise ArtifactError(f"Parquet chunk schema changed for {self.path.name}") from exc
        self.writer.write_table(table)

    def close(self) -> None:
        if self.dev_mode:
            if not self._dev_header_written:
                raise ArtifactError(f"No rows were written to {self.path}")
            self.dev_tmp.replace(self.dev_path)
            atomic_write_json(
                self.path.with_suffix(self.path.suffix + ".fallback.json"),
                {
                    "requested_artifact": self.path.name,
                    "development_fallback": self.dev_path.name,
                    "paper_result": False,
                    "reason": "parquet_engine_unavailable",
                    "generated_at": utc_now(),
                },
            )
            return
        if self.writer is None:
            raise ArtifactError(f"No rows were written to {self.path}")
        self.writer.close()
        self.writer = None
        self.tmp.replace(self.path)

    def abort(self) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        for candidate in (self.tmp, self.dev_tmp):
            if candidate.exists():
                candidate.unlink()


def write_manifest(path: Path, files: Iterable[Path], extra: dict[str, Any], root: Path | None = None) -> None:
    records = []
    root = root or path.parent.parent
    for file_path in sorted(files):
        if not file_path.exists() or file_path == path:
            continue
        try:
            display_path = str(file_path.relative_to(root))
        except ValueError:
            display_path = file_path.name
        records.append(
            {
                "path": display_path.replace("\\", "/"),
                "size_bytes": int(file_path.stat().st_size),
                "sha256": sha256_file(file_path),
            }
        )
    atomic_write_json(
        path,
        {
            **extra,
            "generated_at": utc_now(),
            "artifacts": records,
        },
    )


def refresh_output_manifest(output_root: Path, extra: dict[str, Any] | None = None) -> Path:
    state_path = output_root / "metadata" / "run_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    manifest_path = output_root / "metadata" / "artifact_manifest.json"
    write_manifest(
        manifest_path,
        [p for p in output_root.rglob("*") if p.is_file()],
        {
            "run_id": state.get("run_id"),
            "run_tier": state.get("run_tier", output_root.name),
            "paper_result": bool(state.get("paper_result", False)),
            "config_hash": state.get("config_hash"),
            **(extra or {}),
        },
        root=output_root,
    )
    return manifest_path
