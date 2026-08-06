"""Public facade for fresh and resumable Exp3 pipelines."""
from __future__ import annotations

from pathlib import Path

from config import DEFAULT_CONFIG, ExperimentConfig
from pipeline_contract import STAGES, _clean_active_output, _input_manifest
from pipeline_fresh_run import fresh_pipeline
from pipeline_resume import resume_pipeline
from run_finalization import _finalize_run
from run_registry import (
    new_run_id,
    resolve_latest_audited_pass_run,
    resolve_latest_completed_run,
    resolve_latest_resumable_run,
    resolve_latest_run,
    resolve_run_id,
)


def _print_stage(index: int, message: str) -> None:
    from pipeline_contract import print_stage

    print_stage(index, message)


def run_pipeline(
    project_root: Path,
    run_tier: str,
    *,
    input_root: Path | None = None,
    output_dir: Path | None = None,
    run_id: str | None = None,
    n_jobs: int = 1,
    clean_output: bool = False,
    resume_bootstrap: bool = False,
    synthetic_fixture: bool = False,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> Path:
    if run_tier not in {"fast", "full"}:
        raise ValueError("run_tier must be 'fast' or 'full'")
    project_root = project_root.resolve()
    if resume_bootstrap:
        return resume_pipeline(project_root, run_tier, output_dir, n_jobs, cfg)
    run_id = run_id or new_run_id(
        "fixture" if run_tier == "fast" and synthetic_fixture else run_tier
    )
    target = (output_dir or project_root / "outputs" / run_id).resolve()
    return fresh_pipeline(
        project_root,
        run_tier,
        target,
        run_id,
        input_root,
        n_jobs,
        clean_output,
        synthetic_fixture,
        cfg,
    )


__all__ = [
    "STAGES",
    "new_run_id",
    "resolve_latest_audited_pass_run",
    "resolve_latest_completed_run",
    "resolve_latest_resumable_run",
    "resolve_latest_run",
    "resolve_run_id",
    "run_pipeline",
]
