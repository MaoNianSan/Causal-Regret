"""Immutable run-lineage contract for Exp4 v2 runs.

The lineage separates *eligibility to reuse* (a property of the source tree
and stored hashes) from *actual execution* (which run really executed the
simulation and which run really rebuilt the downstream stages). It is written
by the pipeline / rebuild commands and never inferred from hash equality.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from exp4.outputs.writers import write_json

RUN_LINEAGE_SCHEMA = "exp4_run_lineage_v1"

SIMULATION_EXECUTION_MODES = ("FRESH", "REUSED", "UNKNOWN")
DOWNSTREAM_EXECUTION_MODES = (
    "INLINE_FRESH",
    "REBUILT_FROM_OWN_SIMULATION",
    "REBUILT_FROM_REUSED_SIMULATION",
    "UNKNOWN",
)


@dataclass(frozen=True)
class RunLineage:
    run_id: str
    run_tier: str
    simulation_execution_mode: str
    simulation_source_run_id: str | None
    downstream_execution_mode: str
    downstream_source_run_id: str | None
    created_from_commit: str
    exp4_worktree_clean_at_start: bool

    def validate(self) -> tuple[bool, str]:
        """Structural validation of the lineage (not a provenance verdict)."""
        if self.simulation_execution_mode not in SIMULATION_EXECUTION_MODES:
            return False, f"invalid simulation_execution_mode={self.simulation_execution_mode!r}"
        if self.downstream_execution_mode not in DOWNSTREAM_EXECUTION_MODES:
            return False, f"invalid downstream_execution_mode={self.downstream_execution_mode!r}"
        if self.simulation_execution_mode == "FRESH" and self.simulation_source_run_id is not None:
            return False, "FRESH simulation must have a null simulation_source_run_id"
        if self.simulation_execution_mode == "REUSED" and not self.simulation_source_run_id:
            return False, "REUSED simulation requires a nonempty simulation_source_run_id"
        if self.simulation_execution_mode == "UNKNOWN":
            return False, "UNKNOWN simulation mode cannot be promoted or reused"
        if self.simulation_execution_mode == "FRESH" and self.downstream_execution_mode == "REBUILT_FROM_REUSED_SIMULATION":
            return False, "FRESH simulation cannot have REBUILT_FROM_REUSED_SIMULATION downstream"
        if self.simulation_execution_mode == "REUSED" and self.downstream_execution_mode == "INLINE_FRESH":
            return False, "REUSED simulation cannot have INLINE_FRESH downstream"
        return True, "ok"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def fresh_lineage(
    run_id: str,
    run_tier: str,
    created_from_commit: str,
    worktree_clean: bool,
) -> RunLineage:
    """Lineage for a run that actually executed its own simulation inline."""
    return RunLineage(
        run_id=run_id,
        run_tier=run_tier,
        simulation_execution_mode="FRESH",
        simulation_source_run_id=None,
        downstream_execution_mode="INLINE_FRESH",
        downstream_source_run_id=None,
        created_from_commit=created_from_commit,
        exp4_worktree_clean_at_start=worktree_clean,
    )


def lineage_path(run_dir: Path) -> Path:
    return run_dir / "logs" / "exp4_run_lineage.json"


def write_run_lineage(run_dir: Path, lineage: RunLineage) -> Path:
    payload = {
        "schema": RUN_LINEAGE_SCHEMA,
        **lineage.as_dict(),
    }
    path = lineage_path(run_dir)
    write_json(payload, path)
    return path


def load_run_lineage(run_dir: Path) -> RunLineage | None:
    path = lineage_path(run_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != RUN_LINEAGE_SCHEMA:
            return None
        return RunLineage(
            run_id=str(payload["run_id"]),
            run_tier=str(payload["run_tier"]),
            simulation_execution_mode=str(payload["simulation_execution_mode"]),
            simulation_source_run_id=(
                str(payload["simulation_source_run_id"])
                if payload.get("simulation_source_run_id") is not None
                else None
            ),
            downstream_execution_mode=str(payload["downstream_execution_mode"]),
            downstream_source_run_id=(
                str(payload["downstream_source_run_id"])
                if payload.get("downstream_source_run_id") is not None
                else None
            ),
            created_from_commit=str(payload["created_from_commit"]),
            exp4_worktree_clean_at_start=bool(payload["exp4_worktree_clean_at_start"]),
        )
    except Exception:
        return None


def lineage_valid(lineage: RunLineage | None) -> tuple[bool, str]:
    if lineage is None:
        return False, "run lineage artifact missing"
    return lineage.validate()


def mark_downstream_rebuilt(run_dir: Path, base_dir: Path) -> RunLineage:
    """Record that downstream stages were rebuilt for an existing run.

    The simulation mode and source run id are preserved from the existing
    lineage (or set to UNKNOWN when the lineage is absent, e.g. legacy runs).
    """
    existing = load_run_lineage(run_dir)
    if existing is None:
        run_config_path = run_dir / "logs" / "run_config.json"
        run_config = (
            json.loads(run_config_path.read_text(encoding="utf-8"))
            if run_config_path.exists()
            else {}
        )
        run_id = str(run_config.get("run_id", run_dir.name))
        run_tier = str(run_config.get("run_tier", "UNKNOWN"))
        commit = str(run_config.get("code_commit", "UNKNOWN"))
        existing = RunLineage(
            run_id=run_id,
            run_tier=run_tier,
            simulation_execution_mode="UNKNOWN",
            simulation_source_run_id=None,
            downstream_execution_mode="UNKNOWN",
            downstream_source_run_id=None,
            created_from_commit=commit,
            exp4_worktree_clean_at_start=bool(run_config.get("exp4_worktree_clean_at_start", False)),
        )
    if existing.simulation_execution_mode == "REUSED":
        downstream_mode = "REBUILT_FROM_REUSED_SIMULATION"
        downstream_source = existing.simulation_source_run_id
    elif existing.simulation_execution_mode == "FRESH":
        downstream_mode = "REBUILT_FROM_OWN_SIMULATION"
        downstream_source = None
    else:
        downstream_mode = "UNKNOWN"
        downstream_source = None
    rebuilt = RunLineage(
        run_id=existing.run_id,
        run_tier=existing.run_tier,
        simulation_execution_mode=existing.simulation_execution_mode,
        simulation_source_run_id=existing.simulation_source_run_id,
        downstream_execution_mode=downstream_mode,
        downstream_source_run_id=downstream_source,
        created_from_commit=existing.created_from_commit,
        exp4_worktree_clean_at_start=existing.exp4_worktree_clean_at_start,
    )
    write_run_lineage(run_dir, rebuilt)
    return rebuilt


__all__ = [
    "DOWNSTREAM_EXECUTION_MODES",
    "RUN_LINEAGE_SCHEMA",
    "SIMULATION_EXECUTION_MODES",
    "RunLineage",
    "fresh_lineage",
    "lineage_path",
    "lineage_valid",
    "load_run_lineage",
    "mark_downstream_rebuilt",
    "write_run_lineage",
]
