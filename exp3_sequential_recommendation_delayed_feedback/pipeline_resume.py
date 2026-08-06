"""Hash-compatible bootstrap/render/finalize resume path."""
from __future__ import annotations

import json
from pathlib import Path

from audit_design import load_audit_design
from bootstrap_evaluation import run_user_cluster_bootstrap
from config import ExperimentConfig
from dependence_diagnostics import write_data_dependence_diagnostics
from evaluation_artifacts import load_evaluation_arrays, load_point_estimates
from pipeline_contract import STAGES, print_stage, set_primary_run_metadata, validate_resume_compatibility
from plot_appendix_results import plot_appendix_figures
from plot_main_results import plot_main_figure
from run_finalization import finalize_run
from run_registry import resolve_latest_resumable_run
from utilities import read_frame


def resume_pipeline(
    project_root: Path,
    run_tier: str,
    output_dir: Path | None,
    n_jobs: int,
    cfg: ExperimentConfig,
) -> Path:
    output_dir = (output_dir or resolve_latest_resumable_run(project_root, run_tier)).resolve()
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Resume requires an existing run manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = validate_resume_compatibility(project_root, output_dir, manifest, run_tier, cfg)
    set_primary_run_metadata(manifest, cfg, version)
    design = load_audit_design(output_dir)
    arrays = load_evaluation_arrays(output_dir)
    point_result = load_point_estimates(output_dir)
    if not (output_dir / "tables" / "exp3_data_dependence_structure.csv").exists():
        history = read_frame(output_dir / "processed" / "exp3_history_events_with_targets.parquet")
        evaluation = read_frame(
            output_dir / "processed" / "exp3_evaluation_events_with_targets.parquet"
        )
        write_data_dependence_diagnostics(history, evaluation, output_dir, cfg)
    print_stage(8, STAGES[7] + " (resume)")
    _, _, _, diagnostics = run_user_cluster_bootstrap(
        arrays,
        design,
        point_result,
        output_dir,
        run_tier,
        cfg,
        n_jobs=n_jobs,
        resume=True,
    )
    print_stage(9, STAGES[8])
    plot_main_figure(output_dir, run_tier, paper_result=False)
    plot_appendix_figures(output_dir, run_tier, paper_result=False)
    print_stage(10, STAGES[9])
    finalize_run(output_dir, manifest, design, run_tier, diagnostics, cfg)
    return output_dir
