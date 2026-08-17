"""Typed run context and deterministic artifact writers."""

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

from exp4.configuration.parameters import parameter_payload
from exp4.configuration.registries import (
    AUDIT_DESIGN_REGISTRY,
    CONTROL_REGISTRY,
    ROUTE_REGISTRY,
)
from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import (
    EXPERIMENT_DISPLAY_NAME,
    EXPERIMENT_ID,
    RESULT_SCHEMA,
)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_tier: str
    run_dir: Path
    code_commit: str
    config_hash: str
    source_code_hash: str
    n_jobs: int
    paper_result: bool = False
    exp4_worktree_clean_at_start: bool = True
    stage_source_hashes: dict[str, str] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_files(paths: Iterable[Path], *, root: Path, algorithm_version: str) -> str:
    digest = hashlib.sha256()
    root = root.resolve()
    normalized: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for path in paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"path {resolved} is outside root {root}") from exc
        if relative in seen:
            raise ValueError(f"duplicate normalized path: {relative}")
        seen.add(relative)
        normalized.append((relative, resolved))

    digest.update(algorithm_version.encode("utf-8"))
    digest.update(b"\0")

    for relative, resolved in sorted(normalized):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(resolved.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


# Version tag for the source-code hash algorithm. It is recorded in run
# configs, provenance audits, and promotion checks so that a future algorithm
# change cannot silently invalidate or re-interpret stored hashes.
SOURCE_HASH_ALGORITHM_VERSION = "exp4-source-code-v2"


def compute_exp4_source_code_hash(base_dir: Path) -> str:
    """Canonical Exp4 v3 source-code hash.

    This single function is the source of truth for the full Exp4 source hash:
    run creation, provenance audit, and promotion validation all use it.
    """
    return source_code_hash(base_dir)


def source_code_hash(base_dir: Path) -> str:
    base = base_dir.resolve()
    files = list((base / "exp4").rglob("*.py"))
    return hash_files(
        files,
        root=base,
        algorithm_version=SOURCE_HASH_ALGORITHM_VERSION,
    )


# Stage-level source-hash definitions. Configuration is a shared dependency of
# every stage and is included in every stage hash so that a frozen-config
# change is detected by all stages.
_STAGE_SHARED_PREFIXES = ("exp4/configuration/",)

_STAGE_SPECS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "simulation_source_hash",
        _STAGE_SHARED_PREFIXES
        + (
            "exp4/simulation/",
            "exp4/routes/",
            "exp4/audit/",
            "exp4/calibration/",
            "exp4/modules/",
            "exp4/execution/calibration_stage.py",
            "exp4/execution/module_a_stage.py",
            "exp4/execution/module_bc_stage.py",
            "exp4/execution/common.py",
        ),
        ("exp4/metrics/action_gaps.py",),
    ),
    (
        "aggregation_source_hash",
        _STAGE_SHARED_PREFIXES
        + (
            "exp4/reporting/aggregate_module_a.py",
            "exp4/reporting/aggregate_module_b.py",
            "exp4/reporting/aggregate_module_c.py",
            "exp4/execution/aggregation_stage.py",
        ),
        ("exp4/metrics/monte_carlo.py", "exp4/outputs/writers.py"),
    ),
    (
        "reporting_source_hash",
        _STAGE_SHARED_PREFIXES
        + (
            "exp4/reporting/",
            "exp4/outputs/writers.py",
            "exp4/outputs/manifests.py",
            "exp4/pipeline.py",
        ),
        (),
    ),
    (
        "validation_source_hash",
        _STAGE_SHARED_PREFIXES
        + (
            "exp4/validation/",
            "exp4/outputs/writers.py",
            "exp4/pipeline.py",
        ),
        (),
    ),
)


def _stage_file_matches(
    base_dir: Path, path: Path, prefixes: tuple[str, ...], files: tuple[str, ...]
) -> bool:
    relative = path.relative_to(base_dir).as_posix()
    if relative in files:
        return True
    return any(relative.startswith(prefix) for prefix in prefixes)


def compute_stage_source_hashes(base_dir: Path) -> dict[str, str]:
    """Per-stage source hashes over the current working tree.

    This is the single source of truth for stage hashes: run creation, the
    stage provenance record, and the provenance audit all use it.
    """
    base = base_dir.resolve()
    all_files = list((base / "exp4").rglob("*.py"))
    hashes: dict[str, str] = {}
    for name, prefixes, files in _STAGE_SPECS:
        stage_files = [
            path
            for path in all_files
            if _stage_file_matches(base, path, prefixes, files)
        ]
        hashes[name] = hash_files(
            stage_files,
            root=base,
            algorithm_version=SOURCE_HASH_ALGORITHM_VERSION,
        )
    return hashes


def frozen_config_payload() -> dict[str, object]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment_display_name": EXPERIMENT_DISPLAY_NAME,
        "result_schema": RESULT_SCHEMA,
        "parameters": parameter_payload(),
        "route_registry": ROUTE_REGISTRY,
        "audit_design_registry": AUDIT_DESIGN_REGISTRY,
        "control_registry": CONTROL_REGISTRY,
    }


def config_hash() -> str:
    serialized = json.dumps(
        frozen_config_payload(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def git_commit(base_dir: Path) -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "UNAVAILABLE"


def git_commit_available(base_dir: Path) -> bool:
    """A formal run needs a resolvable non-placeholder commit."""
    commit = git_commit(base_dir)
    return (
        bool(commit)
        and commit not in {"UNAVAILABLE", "UNKNOWN", ""}
        and len(commit) >= 7
    )


def _git_root(base_dir: Path) -> Path | None:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        root = result.stdout.strip()
        return Path(root) if root else None
    except Exception:
        return None


def exp4_dirty_files(base_dir: Path) -> list[str]:
    """Relative paths of uncommitted Exp4 changes (empty when clean/unknown)."""
    git_root = _git_root(base_dir)
    if git_root is None:
        return []
    try:
        relative = base_dir.resolve().relative_to(git_root.resolve())
    except ValueError:
        relative = Path(".")
    try:
        result = subprocess.run(
            ("git", "status", "--porcelain", "--", str(relative)),
            cwd=git_root,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def exp4_worktree_clean(base_dir: Path) -> bool:
    """True only when the Exp4 worktree has no uncommitted changes.

    ``base_dir`` is the experiment directory (may be a subdirectory of the
    git work tree). Returns False when git is unavailable (conservative).
    """
    return not exp4_dirty_files(base_dir)


def write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")


class ParquetBatchWriter:
    def __init__(self, path: Path) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._pa = pa
        self._pq = pq
        self._writer = None

    def write(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        table = self._pa.Table.from_pandas(frame, preserve_index=False)
        if self._writer is None:
            self._writer = self._pq.ParquetWriter(
                self.path, table.schema, compression="zstd"
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


def _run_directories(run_dir: Path) -> None:
    for relative in (
        "raw/trajectories",
        "raw/route_maps",
        "derived/calibration",
        "derived/module_a",
        "derived/module_b",
        "derived/module_c",
        "figures/pdf",
        "figures/png",
        "figures/data",
        "figures/metadata",
        "tables",
        "checks",
        "reports",
        "logs/stages",
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)


def create_run_context(base_dir: Path, run_tier: str, n_jobs: int) -> RunContext:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_tier}_{timestamp}_{uuid.uuid4().hex[:8]}"
    run_dir = base_dir / "outputs" / "runs" / run_id
    _run_directories(run_dir)
    context = RunContext(
        run_id=run_id,
        run_tier=run_tier,
        run_dir=run_dir,
        code_commit=git_commit(base_dir),
        config_hash=config_hash(),
        source_code_hash=source_code_hash(base_dir),
        n_jobs=max(1, int(n_jobs)),
        exp4_worktree_clean_at_start=exp4_worktree_clean(base_dir),
        stage_source_hashes=compute_stage_source_hashes(base_dir),
    )
    write_run_config(context)
    return context


def load_run_context(
    base_dir: Path, run_dir: Path, n_jobs: int | None = None
) -> RunContext:
    payload = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    return RunContext(
        run_id=payload["run_id"],
        run_tier=payload["run_tier"],
        run_dir=run_dir,
        code_commit=payload["code_commit"],
        config_hash=payload["config_hash"],
        source_code_hash=payload["source_code_hash"],
        n_jobs=int(n_jobs if n_jobs is not None else payload.get("n_jobs", 1)),
        paper_result=bool(payload.get("paper_result", False)),
        exp4_worktree_clean_at_start=bool(
            payload.get("exp4_worktree_clean_at_start", False)
        ),
        stage_source_hashes={
            key: str(payload[key])
            for key in (
                "simulation_source_hash",
                "aggregation_source_hash",
                "reporting_source_hash",
                "validation_source_hash",
            )
            if payload.get(key)
        }
        or None,
    )


def write_run_config(context: RunContext) -> None:
    settings = mode_settings(context.run_tier)
    stage_hashes = context.stage_source_hashes or {}
    write_json(
        {
            "run_id": context.run_id,
            "run_tier": context.run_tier,
            "paper_result": False,
            "is_paper_eligible": False,
            "experiment_id": EXPERIMENT_ID,
            "experiment_display_name": EXPERIMENT_DISPLAY_NAME,
            "result_schema": RESULT_SCHEMA,
            "code_commit": context.code_commit,
            "config_hash": context.config_hash,
            "source_code_hash": context.source_code_hash,
            "source_hash_algorithm_version": SOURCE_HASH_ALGORITHM_VERSION,
            "formal_full_clean_worktree_required": context.run_tier == "full",
            "exp4_worktree_clean_at_start": context.exp4_worktree_clean_at_start,
            "simulation_stage_hash": stage_hashes.get("simulation_source_hash", ""),
            "aggregation_stage_hash": stage_hashes.get("aggregation_source_hash", ""),
            "reporting_stage_hash": stage_hashes.get("reporting_source_hash", ""),
            "validation_stage_hash": stage_hashes.get("validation_source_hash", ""),
            "generated_at": utc_now_iso(),
            "n_jobs": context.n_jobs,
            "mode_settings": settings.as_dict(),
            "frozen_configuration": frozen_config_payload(),
        },
        context.run_dir / "logs" / "run_config.json",
    )


def attach_metadata(
    frame: pd.DataFrame,
    context: RunContext,
    module_id: str,
    analysis_tier: str | None = None,
    task_column: str | None = None,
    calibration_hash: str | None = None,
) -> pd.DataFrame:
    output = frame.copy()
    output["run_id"] = context.run_id
    output["run_tier"] = context.run_tier
    output["paper_result"] = False
    output["experiment_id"] = EXPERIMENT_ID
    output["module_id"] = module_id
    if analysis_tier is not None:
        # Preserve an existing per-row analysis_tier column when the caller does
        # not supply a blanket tier (e.g. the Module C control summary, whose
        # rows carry per-control tiers from the frozen control registry).
        output["analysis_tier"] = analysis_tier
    output["code_commit"] = context.code_commit
    output["config_hash"] = context.config_hash
    output["source_code_hash"] = context.source_code_hash
    output["calibration_hash"] = calibration_hash
    output["result_schema"] = RESULT_SCHEMA
    output["seed_or_replication"] = (
        output[task_column]
        if task_column and task_column in output.columns
        else "aggregate"
    )
    return output
