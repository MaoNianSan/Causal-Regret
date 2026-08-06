"""Fresh immutable Exp3 run orchestration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from audit_design import freeze_audit_design
from bootstrap_evaluation import run_user_cluster_bootstrap
from code_version import code_version
from config import ExperimentConfig, ensure_output_dirs
from construct_delayed_targets import add_delayed_targets, attach_pseudo_arrivals_and_carriers
from dependence_diagnostics import write_data_dependence_diagnostics
from design_contract import EVALUATION_ARRAY_SCHEMA_VERSION, design_contract_hash, write_metric_registry
from evaluate_recoverability import compute_metrics
from evaluation_arrays import build_evaluation_arrays
from evaluation_artifacts import write_point_estimates
from pipeline_contract import (
    STAGES,
    clean_active_output,
    config_sha256,
    contract_hash_fields,
    input_manifest,
    input_manifest_sha256,
    print_stage,
    set_primary_run_metadata,
)
from plot_appendix_results import plot_appendix_figures
from plot_main_results import plot_main_figure
from preprocess_events import prepare_events, required_input_paths
from proxy_routes import fit_proxy_routes
from run_finalization import finalize_run
from support_preflight import run_full_design_support_preflight
from synthetic_data import create_fast_fixture
from target_audit import write_target_component_audit
from utilities import save_frame, save_json


def _resolve_inputs(
    project_root: Path,
    run_tier: str,
    input_root: Path | None,
    synthetic_fixture: bool,
    cfg: ExperimentConfig,
) -> tuple[Path, list[Path]]:
    if run_tier == "full" and synthetic_fixture:
        raise ValueError("--synthetic-fixture is valid only for the fast run tier.")
    if run_tier == "fast" and synthetic_fixture:
        root = project_root / "inputs" / "_fast_fixture"
        create_fast_fixture(root, cfg)
        return root, required_input_paths(root, cfg)
    root = input_root or (project_root / "inputs" / "KuaiRand-1K")
    required = required_input_paths(root, cfg)
    missing = [path for path in required if not path.exists()]
    if missing:
        message = (
            "Fast Exp3 uses the frozen KuaiRand inputs by default."
            if run_tier == "fast"
            else "Full Exp3 requires the frozen KuaiRand inputs."
        )
        suffix = " For a software-only smoke test, rerun with --synthetic-fixture." if run_tier == "fast" else ""
        raise FileNotFoundError(
            f"{message} Missing: "
            + ", ".join(map(str, missing))
            + suffix
        )
    return root, required


def fresh_pipeline(
    project_root: Path,
    run_tier: str,
    output_dir: Path,
    run_id: str,
    input_root: Path | None,
    n_jobs: int,
    clean_output: bool,
    synthetic_fixture: bool,
    cfg: ExperimentConfig,
) -> Path:
    version = code_version(project_root)
    if clean_output:
        clean_active_output(output_dir)
    else:
        ensure_output_dirs(output_dir)
        active = [p for p in output_dir.rglob("*") if p.is_file() and "legacy" not in p.parts]
        if active:
            raise RuntimeError("Active output files already exist. Use a new run ID or --clean-output.")
    requested_input_root, required = _resolve_inputs(
        project_root, run_tier, input_root, synthetic_fixture, cfg
    )
    manifest: dict[str, object] = {
        "run_id": run_id,
        "experiment_id": cfg.experiment_id,
        "experiment_slug": cfg.experiment_slug,
        "run_tier": run_tier,
        "analysis_tier": "primary",
        "paper_result": False,
        "synthetic_fixture": synthetic_fixture,
        "input_data_status": "synthetic_fixture" if synthetic_fixture else "original_kuairand_inputs",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_status": "RUNNING",
        "scientific_status": "NOT_EVALUATED",
        "config_hash": config_sha256(cfg),
        "design_contract_hash": design_contract_hash(),
        "evaluation_array_schema_version": EVALUATION_ARRAY_SCHEMA_VERSION,
        **version,
    }
    save_json(manifest, output_dir / "metadata" / "run_manifest.json")
    save_json(cfg.to_dict(), output_dir / "metadata" / "run_config_snapshot.json")
    print_stage(1, STAGES[0])
    inputs = input_manifest(required, requested_input_root)
    manifest["input_manifest_hash"] = input_manifest_sha256(inputs)
    save_frame(inputs, output_dir / "metadata" / "input_data_manifest.csv")
    save_json(manifest, output_dir / "metadata" / "run_manifest.json")
    set_primary_run_metadata(manifest, cfg, version)
    write_metric_registry(output_dir)

    print_stage(2, STAGES[1])
    prepared = prepare_events(requested_input_root, output_dir, run_tier, cfg)
    print_stage(3, STAGES[2])
    history_targets, history_audit = add_delayed_targets(
        prepared.history_events,
        int(prepared.split_manifest["history_end_time_exclusive"]),
        "history",
        output_dir,
        cfg,
        n_jobs=n_jobs,
    )
    evaluation_targets, evaluation_audit = add_delayed_targets(
        prepared.evaluation_events,
        int(prepared.split_manifest["evaluation_end_time_exclusive"]),
        "evaluation",
        output_dir,
        cfg,
        n_jobs=n_jobs,
    )
    write_target_component_audit(history_targets, evaluation_targets, output_dir, cfg)
    evaluation_arrivals, _ = attach_pseudo_arrivals_and_carriers(evaluation_targets, output_dir, cfg)
    write_data_dependence_diagnostics(history_targets, evaluation_targets, output_dir, cfg)
    preflight = run_full_design_support_preflight(
        history_targets,
        evaluation_arrivals,
        prepared.full_design_actions,
        output_dir,
        cfg,
        synthetic_fixture=synthetic_fixture,
    )

    print_stage(4, STAGES[3])
    design, history_designed, evaluation_designed = freeze_audit_design(
        history_targets,
        evaluation_arrivals,
        prepared.candidate_actions,
        output_dir,
        run_tier,
        cfg,
    )
    design_path = output_dir / "design" / "exp3_design_freeze.json"
    design_payload = json.loads(design_path.read_text(encoding="utf-8"))
    design_payload.update(
        {
            **version,
            "design_contract_hash": design_contract_hash(),
            "evaluation_array_schema_version": EVALUATION_ARRAY_SCHEMA_VERSION,
            "two_fold_contract": {
                "reference_action_source": "selection_fold",
                "route_action_source": "selection_fold",
                "route_gap_source": "selection_fold",
                "heldout_target_source": "opposite_evaluation_fold",
            },
        }
    )
    save_json(design_payload, design_path)
    save_frame(history_designed, output_dir / "processed" / "exp3_history_events_designed.parquet")
    save_frame(evaluation_designed, output_dir / "processed" / "exp3_evaluation_events_designed.parquet")

    print_stage(5, STAGES[4])
    fitted = fit_proxy_routes(history_designed, evaluation_designed, design, output_dir, cfg)
    manifest.update(contract_hash_fields(output_dir))
    manifest["selected_ridge_alpha"] = fitted.selected_alpha
    save_json(manifest, output_dir / "metadata" / "run_manifest.json")
    print_stage(6, STAGES[5])
    arrays = build_evaluation_arrays(evaluation_designed, design, fitted, output_dir, cfg)
    print_stage(7, STAGES[6])
    point_result = compute_metrics(arrays, design, cfg=cfg)
    write_point_estimates(point_result, output_dir)
    print_stage(8, STAGES[7])
    _, _, _, diagnostics = run_user_cluster_bootstrap(
        arrays, design, point_result, output_dir, run_tier, cfg, n_jobs=n_jobs, resume=False
    )
    print_stage(9, STAGES[8])
    plot_main_figure(output_dir, run_tier, paper_result=False)
    plot_appendix_figures(output_dir, run_tier, paper_result=False)
    print_stage(10, STAGES[9])
    finalize_run(
        output_dir,
        manifest,
        design,
        run_tier,
        diagnostics,
        cfg,
        history_target_audit=history_audit,
        evaluation_target_audit=evaluation_audit,
        full_design_preflight=preflight,
    )
    return output_dir
