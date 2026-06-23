"""Run orchestration and provenance for Exp3."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np
import pandas as pd

from build_delayed_outcomes import add_future_engagement_targets
from config import DEFAULT_CONFIG, ExperimentConfig, ensure_output_dirs
from data_preprocess import prepare_logs, required_input_paths
from plot_results import plot_all
from recoverability import run_recoverability_experiment
from synthetic_data import create_fast_fixture
from utils import (
    sha256_file,
    save_dataframe,
    stable_json_hash,
    write_artifact_manifest,
    write_json,
)
from bootstrap_analysis import run_user_bootstrap
from report_tables import build_partial_label_sensitivity_table, build_proxy_static_control_table

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_n_jobs(mode: str, requested: int | None) -> int:
    """Resolve a safe worker count and use it in target construction."""
    if requested is not None:
        return max(1, int(requested))
    available = max(1, os.cpu_count() or 1)
    cap = 16 if mode == "fast" else 32
    return min(available, cap)


def find_real_input_root(cfg: ExperimentConfig = DEFAULT_CONFIG) -> Path | None:
    candidates = [ROOT / "inputs" / "KuaiRand-1K", ROOT / "inputs"]
    for candidate in candidates:
        if all(path.exists() for path in required_input_paths(candidate, cfg)):
            return candidate
    return None


def _mode_config(mode: str) -> ExperimentConfig:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be 'fast' or 'full'.")
    return DEFAULT_CONFIG


def _output_dir(mode: str) -> Path:
    return ROOT / "outputs" / mode


def _write_environment(output_dir: Path, n_jobs: int) -> None:
    ensure_output_dirs(output_dir)
    payload = (
        f"python={sys.version}\n"
        f"platform={platform.platform()}\n"
        f"numpy={np.__version__}\n"
        f"pandas={pd.__version__}\n"
        f"n_jobs={n_jobs}\n"
    )
    (output_dir / "metadata" / "environment.txt").write_text(payload, encoding="utf-8")


def _input_manifest(root: Path, cfg: ExperimentConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in required_input_paths(root, cfg):
        rows.append({
            "input_path": str(path),
            "file_name": path.name,
            "required_for_primary": True,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    optional = root / "data" / cfg.random_log
    if not optional.exists():
        optional = root / cfg.random_log
    rows.append({
        "input_path": str(optional),
        "file_name": cfg.random_log,
        "required_for_primary": False,
        "size_bytes": optional.stat().st_size if optional.exists() else np.nan,
        "sha256": sha256_file(optional) if optional.exists() else "not_present",
    })
    return pd.DataFrame(rows)


def _proxy_quality_table(
    calibration_raw: pd.DataFrame,
    calibration_summary: pd.DataFrame,
    metric_summary: pd.DataFrame,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary = cfg.primary_delay_condition
    for method, frame in calibration_raw[calibration_raw["delay_condition"] == primary].groupby("method_id", sort=False):
        spearman = frame["predicted_long_value_log"].corr(frame["observed_long_value_log"], method="spearman")
        calibration = calibration_summary[
            (calibration_summary["delay_condition"] == primary)
            & (calibration_summary["method_id"] == method)
        ]
        calibration_error = (
            float(np.mean(np.abs(
                calibration["mean_predicted_long_value_log"]
                - calibration["mean_observed_long_value_log"]
            )))
            if not calibration.empty
            else np.nan
        )
        metric = metric_summary[
            (metric_summary["delay_condition"] == primary)
            & (metric_summary["method_id"] == method)
        ]
        rows.append({
            "method_id": method,
            "held_out_proxy_score_target_spearman": float(spearman) if pd.notna(spearman) else np.nan,
            "proxy_calibration_error": calibration_error,
            "top_10_overlap_with_source_aware_reference": (
                float(metric["top_k_overlap_with_source_aware_reference"].iloc[0]) if not metric.empty else np.nan
            ),
            "ranking_regret_per_time_bin": float(metric["point_estimate"].iloc[0]) if not metric.empty else np.nan,
            "fit_split": "history_standard_only",
            "evaluation_split": "main_standard_only",
            "target_context": "same_split_standard_log_only",
            "main_feature_information": "completed_history_plus_earlier_main_bins_only",
            "primary_horizon": cfg.primary_horizon,
        })
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, manifest: dict[str, Any], cfg: ExperimentConfig) -> None:
    text = f"""# Experiment 3 completion report

## Status

- Run mode: `{manifest['run_mode']}`
- Input status: `{manifest['input_data_status']}`
- Run id: `{manifest['run_id']}`
- Paper-result gate: `false` until `python self_check.py --mode full --promote-paper-result` passes on a real-data full run.
- Primary target: `long_value_log` over the next 6 hours after a main-standard source exposure.

## Implemented design decisions

1. The target is a split-consistent constructed future-engagement outcome from the same standard-log stream. It is not a native KuaiRand delayed-feedback timestamp, platform utility, or causal effect of the source exposure.
2. The random-exposure stream is excluded from the primary target because there is no matched historical random stream for proxy fitting.
3. The fixed action vocabulary is constructed from history only. Missing and residual tags remain in update accounting but are not candidate actions.
4. Arrival-time carrier assignment uses the most recent same-user standard exposure at or before feedback arrival. Future exposures are never used as carriers.
5. Partial source-label routes use deterministic event-level mask trajectories. Labelled outcomes update their source action; unlabelled outcomes update the arrival carrier.
6. Ridge proxy coefficients are fit only on history standard and evaluated on main standard. Main-period proxy states use completed history and earlier main bins only; no full-main fallback statistic is used.
7. User-cluster resampling replays empirical dynamic routes. Partial-label intervals additionally sample from a finite bank of independent event-level mask trajectories. Proxy score paths and candidate support remain fixed.
8. `history_mean_static` ranks actions only by completed-history 6h target means. It is a diagnostic control for stable action-category persistence and never uses main-period short-term signals, arrivals, or labels.
9. The run writes `oracle_action_dynamics_summary.csv`, `paired_mechanism_contrast.csv`, and `paired_effect_vs_history_mean_static.csv`. The latter isolates the paired decision-level comparison of each route against the static history control.
10. The source-label sensitivity result is emitted as a table with the absolute expected number of labelled outcomes rather than as a monotonicity-looking curve. Arrival-mechanism contrasts remain CSV-only audits because the current daily-bin evidence does not support a general mechanism claim.

## Interpretation boundary

The package evaluates offline recoverability of a constructed 6h target on logged support under a semi-synthetic pseudo-arrival mechanism. It does not establish native delayed feedback, online causal policy improvement, off-policy policy value, or an official platform utility.
"""
    (output_dir / "reports" / "experiment_refactor_completion_report.md").write_text(text, encoding="utf-8")


def run(mode: str, n_jobs: int | None = None) -> int:
    """Execute one reproducible Exp3 run."""
    cfg = _mode_config(mode)
    workers = resolve_n_jobs(mode, n_jobs)
    output_dir = _output_dir(mode)
    _write_environment(output_dir, workers)

    real_root = find_real_input_root(cfg)
    if mode == "full" and real_root is None:
        manifest = {
            "project_id": "exp3_long_term_recoverability",
            "run_mode": mode,
            "status": "blocked_missing_input",
            "input_data_status": "missing",
            "paper_result": False,
            "error": "Full mode requires standard KuaiRand-1K input files; no synthetic fallback is allowed.",
        }
        write_json(output_dir / "metadata" / "run_manifest.json", manifest)
        print("[BLOCKED] full mode requires real KuaiRand-1K standard logs under inputs/KuaiRand-1K/data/.")
        return 2

    if real_root is None:
        input_root = create_fast_fixture(output_dir / "_synthetic_input", cfg)
        input_status = "synthetic_test_fixture"
    else:
        input_root = real_root
        input_status = "real_kuairand_1k"

    config_payload = asdict(cfg)
    config_hash = stable_json_hash(config_payload)
    run_id = f"{mode}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{config_hash[:10]}"
    manifest: dict[str, Any] = {
        "project_id": "exp3_long_term_recoverability",
        "run_id": run_id,
        "run_mode": mode,
        "status": "running",
        "started_at_utc": utc_now(),
        "input_data_status": input_status,
        "paper_result": False,
        "paper_result_candidate": bool(mode == "full" and input_status == "real_kuairand_1k"),
        "primary_horizon": cfg.primary_horizon,
        "primary_outcome_id": cfg.primary_outcome_id,
        "n_jobs": workers,
        "config_hash": config_hash,
        "uncertainty_design": "user-cluster resampling of empirical update routes; partial-label routes pair each draw with one event-level trajectory from a finite mask bank; history-fitted proxy scores and support masks fixed",
        "target_context": "same_split_standard_log_only",
        "action_vocabulary_source": "history_standard_only",
        "carrier_rule": "most_recent_same_user_standard_exposure_at_or_before_arrival",
        "main_feature_information": "completed_history_plus_earlier_main_bins_only",
        "config": config_payload,
    }
    write_json(output_dir / "metadata" / "run_manifest.json", manifest)

    try:
        save_dataframe(_input_manifest(input_root, cfg), output_dir / "metadata" / "input_data_manifest.csv")
        sample_users = cfg.fast_users if mode == "fast" else cfg.full_users
        logs = prepare_logs(input_root, output_dir, cfg, sample_users)
        history = add_future_engagement_targets(logs.history_standard, output_dir, "history_standard", cfg, n_jobs=workers)
        main = add_future_engagement_targets(logs.main_standard, output_dir, "main_standard", cfg, n_jobs=workers)
        results = run_recoverability_experiment(
            main,
            history,
            logs.actions,
            logs.candidate_action_indices,
            output_dir,
            cfg,
            replication_seeds=(cfg.fast_replication_seeds if mode == "fast" else cfg.full_replication_seeds),
        )
        n_bootstrap = cfg.fast_bootstrap_n if mode == "fast" else cfg.full_bootstrap_n
        metric_summary, _, calibration_summary = run_user_bootstrap(
            results["raw"],
            results["prepared"],
            output_dir,
            cfg,
            n_bootstrap=n_bootstrap,
        )
        calibration_raw = pd.read_csv(output_dir / "raw" / "proxy_calibration_cells_raw.csv")
        arrival_effects = pd.read_csv(output_dir / "summaries" / "paired_effect_vs_arrival_time.csv")
        static_effects = pd.read_csv(output_dir / "summaries" / "paired_effect_vs_history_mean_static.csv")
        arrival_summary = pd.read_csv(output_dir / "summaries" / "arrival_mechanism_summary.csv")
        save_dataframe(
            _proxy_quality_table(calibration_raw, calibration_summary, metric_summary, cfg),
            output_dir / "tables" / "tbl_app_exp3_proxy_score_quality.csv",
        )
        save_dataframe(
            build_partial_label_sensitivity_table(metric_summary, arrival_summary, arrival_effects, cfg),
            output_dir / "tables" / "tbl_app_exp3_source_label_sensitivity.csv",
        )
        save_dataframe(
            build_proxy_static_control_table(metric_summary, static_effects, cfg),
            output_dir / "tables" / "tbl_app_exp3_proxy_static_control.csv",
        )
        plot_all(output_dir, mode, False, cfg, input_data_status=input_status)
        manifest.update({
            "status": "complete_pending_external_checks",
            "finished_at_utc": utc_now(),
            "n_main_standard_source_events": int(len(main)),
            "n_main_users": int(main[cfg.user_col].nunique()),
            "n_action_buckets_including_residual": int(len(logs.actions)),
            "n_candidate_action_buckets": int(len(logs.candidate_action_indices)),
            "n_bootstrap": n_bootstrap,
            "n_label_mask_trajectories": len(cfg.fast_replication_seeds if mode == "fast" else cfg.full_replication_seeds),
            "primary_figures": ["fig_exp3_long_term_recoverability"],
            "appendix_figures": ["fig_app_exp3_horizon_eligibility"],
            "appendix_tables": [
                "tbl_app_exp3_source_label_sensitivity",
                "tbl_app_exp3_proxy_static_control",
                "tbl_app_exp3_proxy_score_quality",
            ],
            "retired_figure_interfaces": [
                "fig_app_exp3_arrival_mechanism_contrast",
                "fig_app_exp3_source_label_coverage",
                "fig_app_exp3_horizon_saturation",
            ],
        })
        write_json(output_dir / "metadata" / "run_manifest.json", manifest)
        _write_report(output_dir, manifest, cfg)
        write_artifact_manifest(output_dir)
        print(f"[SUCCESS] {mode} completed: {output_dir}")
        return 0
    except Exception as exc:
        manifest.update({
            "status": "failed",
            "finished_at_utc": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
        })
        write_json(output_dir / "metadata" / "run_manifest.json", manifest)
        write_artifact_manifest(output_dir)
        raise
