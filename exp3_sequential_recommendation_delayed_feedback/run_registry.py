"""Immutable Exp3 run-ID creation and successful/resumable run resolution."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from code_version import code_version


def new_run_id(run_tier: str) -> str:
    return f"exp3-{run_tier}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _manifest_for_run(path: Path) -> dict[str, object] | None:
    manifest_path = path / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_latest(
    project_root: Path,
    run_tier: str,
    predicate,
    description: str,
) -> Path:
    valid: list[Path] = []
    for path in (project_root / "outputs").glob(f"exp3-{run_tier}-*"):
        if not path.is_dir():
            continue
        manifest = _manifest_for_run(path)
        if not manifest:
            continue
        if str(manifest.get("run_tier")) == run_tier and predicate(path, manifest):
            valid.append(path)
    if not valid:
        raise FileNotFoundError(
            f"No {description} Exp3 {run_tier} run exists under {project_root / 'outputs'}. "
            "Pass --output-dir to inspect a specific failed or historical run."
        )
    return max(valid, key=lambda path: path.name).resolve()


def resolve_latest_completed_run(project_root: Path, run_tier: str) -> Path:
    """Resolve the newest pipeline-completed run, including self-check failures."""
    return _resolve_latest(
        project_root,
        run_tier,
        lambda _path, manifest: bool(manifest.get("completed_at_utc"))
        and manifest.get("pipeline_execution_status", "PASS") == "PASS"
        and not bool(manifest.get("superseded", False)),
        "pipeline-completed",
    )


def resolve_latest_audited_pass_run(project_root: Path, run_tier: str) -> Path:
    """Resolve the newest independently audited engineering/scientific-contract pass."""
    def audited(path: Path, manifest: dict[str, object]) -> bool:
        self_check_path = path / "checks" / "exp3_self_check.json"
        self_check_pass = manifest.get("independent_self_check_status") == "PASS"
        if not self_check_pass and self_check_path.exists():
            try:
                check = json.loads(self_check_path.read_text(encoding="utf-8"))
                self_check_pass = (
                    check.get("independent_self_check_status") == "PASS"
                    or (
                        check.get("engineering_status") == "PASS"
                        and check.get("scientific_contract_status") == "PASS"
                    )
                )
            except (OSError, json.JSONDecodeError):
                self_check_pass = False
        final_pass = manifest.get("final_engineering_status", manifest.get("engineering_status")) == "PASS"
        return (
            bool(manifest.get("completed_at_utc"))
            and self_check_pass
            and final_pass
            and not bool(manifest.get("superseded", False))
        )

    return _resolve_latest(project_root, run_tier, audited, "independently audited PASS")


def resolve_latest_run(project_root: Path, run_tier: str) -> Path:
    """Backward-compatible alias for the latest independently audited PASS run."""
    return resolve_latest_audited_pass_run(project_root, run_tier)


def resolve_latest_resumable_run(project_root: Path, run_tier: str) -> Path:
    """Resolve the newest code-compatible run with all bootstrap resume inputs."""
    required = (
        "metadata/run_manifest.json",
        "metadata/run_config_snapshot.json",
        "design/exp3_design_freeze.json",
        "derived/exp3_evaluation_arrays.npz",
        "derived/exp3_route_metrics_point.csv",
        "checks/exp3_bootstrap_checkpoint.csv",
    )
    current = code_version(project_root)
    valid: list[Path] = []
    for path in (project_root / "outputs").glob(f"exp3-{run_tier}-*"):
        if not path.is_dir() or not all((path / relative).exists() for relative in required):
            continue
        manifest = _manifest_for_run(path)
        if not manifest or str(manifest.get("run_tier")) != run_tier:
            continue
        compatible = (
            manifest.get("code_version_type") == current["code_version_type"]
            and manifest.get("code_version") == current["code_version"]
        )
        if compatible:
            valid.append(path)
    if not valid:
        raise FileNotFoundError(
            f"No code-compatible resumable Exp3 {run_tier} run exists under "
            f"{project_root / 'outputs'}"
        )
    return max(valid, key=lambda path: path.name).resolve()


def resolve_run_id(project_root: Path, run_id: str, run_tier: str | None = None) -> Path:
    """Resolve an explicit immutable run ID without applying latest-run predicates."""
    path = (project_root / "outputs" / run_id).resolve()
    outputs = (project_root / "outputs").resolve()
    if path.parent != outputs or not path.is_dir():
        raise FileNotFoundError(f"Exp3 run ID does not exist: {run_id}")
    manifest = _manifest_for_run(path)
    if not manifest:
        raise FileNotFoundError(f"Exp3 run ID has no readable manifest: {run_id}")
    if run_tier is not None and str(manifest.get("run_tier")) != run_tier:
        raise RuntimeError(
            f"Run {run_id} has tier {manifest.get('run_tier')}, expected {run_tier}."
        )
    return path
