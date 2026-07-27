"""End-to-end runner for the frozen Exp3 score--gap--ranking design."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from audit_design import freeze_audit_design, load_audit_design
from bootstrap_evaluation import run_user_cluster_bootstrap
from config import DEFAULT_CONFIG, ExperimentConfig, ensure_output_dirs
from code_version import code_version
from construct_delayed_targets import add_delayed_targets, attach_pseudo_arrivals_and_carriers
from dependence_diagnostics import write_data_dependence_diagnostics
from evaluation_arrays import build_evaluation_arrays
from evaluate_recoverability import compute_metrics
from evaluation_artifacts import (
    load_evaluation_arrays,
    load_point_estimates,
    write_point_estimates,
)
from plot_appendix_results import plot_appendix_figures
from plot_main_results import plot_main_figure
from preprocess_events import prepare_events, required_input_paths
from proxy_routes import fit_proxy_routes
from run_registry import (
    new_run_id,
    resolve_latest_audited_pass_run,
    resolve_latest_completed_run,
    resolve_latest_resumable_run,
    resolve_latest_run,
    resolve_run_id,
)
from run_reporting import (
    full_design_support_ready,
    readiness_fields,
    scientific_uncertainty_status,
    synchronize_run_outputs,
    write_run_report,
)
from support_preflight import run_full_design_support_preflight
from synthetic_data import create_fast_fixture
from utilities import build_artifact_manifest, read_frame, save_frame, save_json, set_run_metadata, sha256_file


STAGES = (
    "Validate input schema",
    "Normalize events and freeze actions",
    "Construct source-indexed delayed targets",
    "Freeze history-only audit design",
    "Fit observable proxy routes",
    "Build cross-fitted evaluation arrays",
    "Evaluate score, gap, and ranking",
    "Run user-cluster bootstrap",
    "Render frozen paper interfaces",
    "Finalize manifests and report",
)


def _print_stage(index: int, message: str) -> None:
    print(f"[{index}/{len(STAGES)}] {message}", flush=True)


def _clean_active_output(output_dir: Path) -> None:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if bool(existing.get("paper_result", False)):
            raise RuntimeError("Refusing to clean a promoted paper result.")
    legacy = output_dir / "legacy"
    backup = None
    if legacy.exists() and any(legacy.iterdir()):
        backup = output_dir.parent / f".{output_dir.name}_legacy_backup"
        if backup.exists():
            shutil.rmtree(backup)
        shutil.copytree(legacy, backup)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_output_dirs(output_dir)
    if backup is not None:
        shutil.copytree(backup, output_dir / "legacy", dirs_exist_ok=True)
        shutil.rmtree(backup)


def _input_manifest(paths: list[Path], input_root: Path) -> pd.DataFrame:
    rows = []
    for path in paths:
        rows.append(
            {
                "file_name": path.name,
                "relative_path": path.relative_to(input_root).as_posix() if path.is_relative_to(input_root) else str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": sha256_file(path) if path.exists() else "",
            }
        )
    return pd.DataFrame(rows)


def _finalize_run(
    output_dir: Path,
    run_manifest: dict[str, object],
    design,
    run_tier: str,
    bootstrap_diagnostics: dict[str, object],
    cfg: ExperimentConfig,
    *,
    history_target_audit: dict[str, object] | None = None,
    evaluation_target_audit: dict[str, object] | None = None,
    full_design_preflight: dict[str, object] | None = None,
) -> None:
    support = pd.read_csv(output_dir / "tables" / "exp3_support_coverage.csv").iloc[0]
    pipeline_support_status = str(support["scientific_support_status"])
    if run_tier == "full":
        scientific_status = "PENDING_SELF_CHECK"
    elif bool(run_manifest.get("synthetic_fixture", False)):
        scientific_status = "NOT_EVALUATED_FAST_FIXTURE"
    else:
        scientific_status = "NOT_EVALUATED_FAST_REAL"
    run_manifest.update(
        {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_execution_status": "PASS",
            "independent_self_check_status": "NOT_RUN",
            "final_engineering_status": "PENDING_SELF_CHECK",
            "engineering_status": "PENDING_SELF_CHECK",
            "scientific_status": scientific_status,
            "scientific_contract_status": "PENDING_SELF_CHECK",
            "pipeline_scientific_support_status": pipeline_support_status,
            "paper_result": False,
            "selected_user_group_count": design.user_group_count,
            "support_min_events_per_fold": design.support_min_events_per_fold,
            "near_tie_threshold": design.near_tie_threshold,
            "candidate_action_count": len(design.candidate_actions),
            "bootstrap_repetitions": cfg.bootstrap_repetitions(run_tier),
            "valid_bootstrap_fraction": bootstrap_diagnostics["valid_bootstrap_fraction"],
        }
    )
    if history_target_audit is not None:
        run_manifest["history_target_audit"] = history_target_audit
    if evaluation_target_audit is not None:
        run_manifest["evaluation_target_audit"] = evaluation_target_audit
    split_manifest_path = output_dir / "design" / "exp3_split_manifest.json"
    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    quarantine_count = int(split_manifest.get("history_events_excluded_before_start", 0)) + int(
        split_manifest.get("evaluation_events_excluded_before_boundary", 0)
    )
    input_boundary_status = "PASS_WITH_BOUNDARY_QUARANTINE" if quarantine_count else "PASS"
    run_manifest["input_boundary_status"] = input_boundary_status
    run_manifest["input_audit_status"] = "PENDING_SELF_CHECK"
    run_manifest["boundary_quarantine_event_count"] = quarantine_count
    if full_design_preflight is not None:
        run_manifest["full_design_support_preflight"] = full_design_preflight
        run_manifest["full_design_support_ready"] = full_design_support_ready(full_design_preflight)
    run_manifest["resampling_range_method"] = bootstrap_diagnostics.get("displayed_range_method")
    run_manifest["resampling_output_role"] = bootstrap_diagnostics.get("resampling_output_role")
    run_manifest["formal_ci_validated"] = bool(bootstrap_diagnostics.get("formal_ci_validated", False))
    run_manifest["resampling_centering_status"] = bootstrap_diagnostics.get("resampling_centering_status")
    run_manifest["scientific_uncertainty_status"] = scientific_uncertainty_status(bootstrap_diagnostics)
    run_manifest["figure_data_contract_status"] = "PENDING_SELF_CHECK"
    run_manifest.update(readiness_fields(run_manifest))
    run_manifest["archival_integrity_check_status"] = "NOT_RUN"
    run_manifest["artifact_manifest_status"] = "PASS"
    synchronize_run_outputs(output_dir, run_manifest)
    build_artifact_manifest(output_dir)
    print("\nEXP3 RUN SUMMARY")
    print("-" * 58)
    print(f"Run ID                    {run_manifest['run_id']}")
    print(f"Output directory           {output_dir}")
    print(f"Run tier                  {run_tier}")
    print(f"Pipeline execution        PASS")
    print(f"Final engineering         PENDING_SELF_CHECK")
    print(f"Scientific status         {scientific_status}")
    print(f"Scientific contract       PENDING_SELF_CHECK")
    print(f"Scientific uncertainty    {run_manifest['scientific_uncertainty_status']}")
    print(f"Paper eligible            false")
    print(f"Action coverage           {float(support.action_coverage):.3f}")
    print(f"Pair coverage             {float(support.pair_coverage):.3f}")
    print(f"Audit-unit coverage       {float(support.audit_unit_coverage):.3f}")
    print("-" * 58)


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
    version = code_version(project_root)

    if resume_bootstrap:
        if output_dir is None:
            output_dir = resolve_latest_resumable_run(project_root, run_tier)
        output_dir = output_dir.resolve()
        manifest_path = output_dir / "metadata" / "run_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Resume requires an existing run manifest: {manifest_path}")
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if str(run_manifest.get("run_tier")) != run_tier:
            raise RuntimeError("Resume run tier does not match the existing manifest.")
        if any(run_manifest.get(key) != value for key, value in version.items()):
            raise RuntimeError("Resume source-tree hash is incompatible with the existing run.")
        set_run_metadata(
            {
                "run_id": run_manifest["run_id"],
                "run_tier": run_tier,
                "paper_result": False,
                "analysis_tier": "primary",
                "experiment_id": cfg.experiment_id,
                "config_hash": run_manifest.get("config_hash", "unknown"),
                "input_manifest_hash": run_manifest.get("input_manifest_hash", "unknown"),
                **version,
            }
        )
        design = load_audit_design(output_dir)
        arrays = load_evaluation_arrays(output_dir)
        point_result = load_point_estimates(output_dir)
        dependence_table = output_dir / "tables" / "exp3_data_dependence_structure.csv"
        if not dependence_table.exists():
            history_targeted = read_frame(output_dir / "processed" / "exp3_history_events_with_targets.parquet")
            evaluation_targeted = read_frame(output_dir / "processed" / "exp3_evaluation_events_with_targets.parquet")
            write_data_dependence_diagnostics(history_targeted, evaluation_targeted, output_dir, cfg)
        _print_stage(8, STAGES[7] + " (resume)")
        _, _, _, bootstrap_diagnostics = run_user_cluster_bootstrap(
            arrays,
            design,
            point_result,
            output_dir,
            run_tier,
            cfg,
            n_jobs=n_jobs,
            resume=True,
        )
        _print_stage(9, STAGES[8])
        plot_main_figure(output_dir, run_tier, paper_result=False)
        plot_appendix_figures(output_dir, run_tier, paper_result=False)
        _print_stage(10, STAGES[9])
        _finalize_run(output_dir, run_manifest, design, run_tier, bootstrap_diagnostics, cfg)
        return output_dir

    run_id = run_id or new_run_id(
        "fixture" if run_tier == "fast" and synthetic_fixture else run_tier
    )
    output_dir = (output_dir or (project_root / "outputs" / run_id)).resolve()
    if clean_output:
        _clean_active_output(output_dir)
    else:
        ensure_output_dirs(output_dir)
        active_files = [path for path in output_dir.rglob("*") if path.is_file() and "legacy" not in path.parts]
        if active_files:
            raise RuntimeError("Active output files already exist. Use a new run ID or --clean-output.")

    if run_tier == "full" and synthetic_fixture:
        raise ValueError("--synthetic-fixture is valid only for the fast run tier.")

    if run_tier == "fast" and synthetic_fixture:
        requested_input_root = project_root / "inputs" / "_fast_fixture"
        create_fast_fixture(requested_input_root, cfg)
        required = required_input_paths(requested_input_root, cfg)
    else:
        requested_input_root = input_root or (project_root / "inputs" / "KuaiRand-1K")
        required = required_input_paths(requested_input_root, cfg)
        missing = [path for path in required if not path.exists()]
        if missing:
            if run_tier == "fast":
                raise FileNotFoundError(
                    "Fast Exp3 uses the frozen KuaiRand inputs by default. Missing: "
                    + ", ".join(map(str, missing))
                    + ". For a software-only smoke test, rerun with --synthetic-fixture."
                )
            raise FileNotFoundError(
                "Full Exp3 requires the frozen KuaiRand inputs. Missing: "
                + ", ".join(map(str, missing))
            )

    run_manifest: dict[str, object] = {
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
        **version,
    }
    save_json(run_manifest, output_dir / "metadata" / "run_manifest.json")
    save_json(cfg.to_dict(), output_dir / "metadata" / "run_config_snapshot.json")

    _print_stage(1, STAGES[0])
    input_manifest = _input_manifest(required, requested_input_root)
    save_frame(input_manifest, output_dir / "metadata" / "input_data_manifest.csv")
    config_hash = hashlib.sha256(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()
    input_manifest_hash = hashlib.sha256("|".join(input_manifest.sort_values("file_name")["sha256"].astype(str)).encode()).hexdigest()
    run_manifest["config_hash"] = config_hash
    run_manifest["input_manifest_hash"] = input_manifest_hash
    save_json(run_manifest, output_dir / "metadata" / "run_manifest.json")
    set_run_metadata(
        {
            "run_id": run_id,
            "run_tier": run_tier,
            "paper_result": False,
            "analysis_tier": "primary",
            "experiment_id": cfg.experiment_id,
            "config_hash": config_hash,
            "input_manifest_hash": input_manifest_hash,
            **version,
        }
    )

    _print_stage(2, STAGES[1])
    prepared = prepare_events(requested_input_root, output_dir, run_tier, cfg)
    _print_stage(3, STAGES[2])
    history_targets, history_target_audit = add_delayed_targets(
        prepared.history_events, int(prepared.split_manifest["history_end_time_exclusive"]), "history", output_dir, cfg, n_jobs=n_jobs
    )
    evaluation_targets, evaluation_target_audit = add_delayed_targets(
        prepared.evaluation_events, int(prepared.split_manifest["evaluation_end_time_exclusive"]), "evaluation", output_dir, cfg, n_jobs=n_jobs
    )
    evaluation_arrivals, _ = attach_pseudo_arrivals_and_carriers(evaluation_targets, output_dir, cfg)
    write_data_dependence_diagnostics(history_targets, evaluation_targets, output_dir, cfg)
    full_design_preflight = run_full_design_support_preflight(
        history_targets,
        evaluation_arrivals,
        prepared.full_design_actions,
        output_dir,
        cfg,
        synthetic_fixture=synthetic_fixture,
    )

    _print_stage(4, STAGES[3])
    design, history_designed, evaluation_designed = freeze_audit_design(
        history_targets, evaluation_arrivals, prepared.candidate_actions, output_dir, run_tier, cfg
    )
    design_path = output_dir / "design" / "exp3_design_freeze.json"
    design_payload = json.loads(design_path.read_text(encoding="utf-8"))
    design_payload.update(version)
    save_json(design_payload, design_path)
    save_frame(history_designed, output_dir / "processed" / "exp3_history_events_designed.parquet")
    save_frame(evaluation_designed, output_dir / "processed" / "exp3_evaluation_events_designed.parquet")

    _print_stage(5, STAGES[4])
    fitted = fit_proxy_routes(history_designed, evaluation_designed, design, output_dir, cfg)
    _print_stage(6, STAGES[5])
    arrays = build_evaluation_arrays(evaluation_designed, design, fitted, output_dir, cfg)
    _print_stage(7, STAGES[6])
    point_result = compute_metrics(arrays, design, cfg=cfg)
    write_point_estimates(point_result, output_dir)
    _print_stage(8, STAGES[7])
    _, _, _, bootstrap_diagnostics = run_user_cluster_bootstrap(
        arrays, design, point_result, output_dir, run_tier, cfg, n_jobs=n_jobs, resume=False
    )
    _print_stage(9, STAGES[8])
    plot_main_figure(output_dir, run_tier, paper_result=False)
    plot_appendix_figures(output_dir, run_tier, paper_result=False)
    _print_stage(10, STAGES[9])
    _finalize_run(
        output_dir,
        run_manifest,
        design,
        run_tier,
        bootstrap_diagnostics,
        cfg,
        history_target_audit=history_target_audit,
        evaluation_target_audit=evaluation_target_audit,
        full_design_preflight=full_design_preflight,
    )
    return output_dir
