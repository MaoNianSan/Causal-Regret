"""Independent engineering, scientific, and promotion checks for Exp3."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from artifact_integrity import verify_artifact_manifest
from code_version import code_version
from config import DEFAULT_CONFIG
from plot_appendix_results import plot_appendix_figures
from plot_main_results import plot_main_figure
from self_check_helpers import (
    add_check,
    arrival_figure_data_matches,
    boundary_quarantine_summary_matches,
    bootstrap_interval_audit_matches,
    dependence_structure_matches,
    dependence_figure_data_matches,
    figure_metadata_hashes_match,
    full_preflight_figure_data_matches,
    load_json,
    main_figure_data_matches,
    route_selection_diagnostics_match,
    target_reuse_summary_matches,
    target_contract_matches,
)
from run_reporting import (
    calculate_final_engineering_status,
    readiness_fields,
    scientific_uncertainty_status,
    synchronize_run_outputs,
)
from utilities import build_artifact_manifest, read_frame, save_json


def _required_artifacts(output_dir: Path) -> dict[str, Path]:
    return {
        "manifest": output_dir / "metadata" / "run_manifest.json",
        "config": output_dir / "metadata" / "run_config_snapshot.json",
        "design": output_dir / "design" / "exp3_design_freeze.json",
        "split_manifest": output_dir / "design" / "exp3_split_manifest.json",
        "model_manifest": output_dir / "metadata" / "exp3_model_manifest.json",
        "bootstrap": output_dir / "checks" / "exp3_bootstrap_diagnostics.json",
        "resampling_sensitivity_audit": output_dir / "checks" / "exp3_resampling_sensitivity_audit.csv",
        "primary_results": output_dir / "tables" / "exp3_primary_route_results.csv",
        "support": output_dir / "tables" / "exp3_support_coverage.csv",
        "support_cells": output_dir / "derived" / "exp3_evaluation_support_cells.csv",
        "route_selection": output_dir / "diagnostics" / "exp3_route_selection_diagnostics.csv",
        "full_preflight": output_dir / "diagnostics" / "exp3_full_design_support_preflight.json",
        "action_coverage": output_dir / "tables" / "exp3_action_space_coverage.csv",
        "target_reuse": output_dir / "tables" / "exp3_target_reuse_audit.csv",
        "data_dependence": output_dir / "tables" / "exp3_data_dependence_structure.csv",
        "resampling_structure": output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv",
        "boundary_quarantine": output_dir / "tables" / "exp3_boundary_quarantine_audit.csv",
        "main_figure_data": output_dir / "figures" / "data" / "exp3_main_score_gap_ranking_data.csv",
        "dependence_figure_data": output_dir / "figures" / "data" / "exp3_appendix_dependence_and_selection_structure_data.csv",
        "arrival_figure_data": output_dir / "figures" / "data" / "exp3_appendix_arrival_carrier_diagnostic_data.csv",
        "artifact_manifest": output_dir / "manifest" / "artifact_manifest.csv",
    }


def _check_input_and_time(
    rows: list[dict[str, object]],
    output_dir: Path,
    manifest: dict[str, Any],
    config: dict[str, Any],
    split: dict[str, Any],
) -> None:
    add_check(rows, "timezone_rule", split.get("timezone_rule") == config.get("timezone_rule"), str(split.get("timezone_rule")), "scientific")
    add_check(rows, "interval_convention", split.get("interval_convention") == "left_closed_right_open", str(split.get("interval_convention")), "scientific")
    strict = int(split["history_end_time_exclusive"]) <= int(split["evaluation_start_time"])
    add_check(rows, "strict_temporal_split", strict, f"history_end={split['history_end_time_exclusive']}; evaluation_start={split['evaluation_start_time']}", "scientific")
    history_fraction = float(split.get("history_prestart_fraction", 0.0))
    evaluation_fraction = float(split.get("evaluation_preboundary_fraction", 0.0))
    quarantine_ok = (
        history_fraction <= float(config["max_prestart_history_fraction"])
        and evaluation_fraction <= float(config["max_preboundary_evaluation_fraction"])
    )
    add_check(rows, "boundary_quarantine_within_frozen_limits", quarantine_ok, f"history={history_fraction:.6%}; evaluation={evaluation_fraction:.6%}", "scientific")
    quarantine_count = int(split.get("history_events_excluded_before_start", 0)) + int(split.get("evaluation_events_excluded_before_boundary", 0))
    expected_status = "PASS_WITH_BOUNDARY_QUARANTINE" if quarantine_count else "PASS"
    add_check(rows, "boundary_quarantine_reported", manifest.get("input_boundary_status") == expected_status and int(manifest.get("boundary_quarantine_event_count", -1)) == quarantine_count, f"status={expected_status}; count={quarantine_count}", "engineering")
    boundary_ok, boundary_detail = boundary_quarantine_summary_matches(output_dir)
    add_check(rows, "boundary_quarantine_summary_reconstruction", boundary_ok, boundary_detail, "engineering")

    for split_id, end_key in (("history", "history_end_time_exclusive"), ("evaluation", "evaluation_end_time_exclusive")):
        try:
            frame = read_frame(output_dir / "processed" / f"exp3_{split_id}_events_with_targets.parquet")
            passed, detail = target_contract_matches(frame, int(split[end_key]))
        except FileNotFoundError:
            passed, detail = False, "targeted event artifact missing"
        add_check(rows, f"{split_id}_target_window_contract", passed, detail, "scientific")
    reuse_ok, reuse_detail = target_reuse_summary_matches(output_dir)
    add_check(rows, "target_reuse_summary_reconstruction", reuse_ok, reuse_detail, "engineering")
    dependence_ok, dependence_detail = dependence_structure_matches(output_dir)
    add_check(rows, "dependence_structure_disclosed", dependence_ok, dependence_detail, "scientific")


def _check_design_and_model(
    rows: list[dict[str, object]],
    output_dir: Path,
    config: dict[str, Any],
    design: dict[str, Any],
    model: dict[str, Any],
) -> None:
    actions = pd.read_csv(output_dir / "design" / "exp3_action_vocabulary.csv")
    candidate = actions[actions["is_candidate_action"].astype(str).str.lower().isin({"true", "1"})]
    add_check(rows, "candidate_action_count", len(candidate) == len(design["candidate_actions"]), f"candidate_count={len(candidate)}", "scientific")
    add_check(rows, "residual_excluded", not bool(design.get("residual_action_is_candidate")), "residual bucket is excluded from primary ranking", "scientific")
    add_check(rows, "group_fold_salts_separated", design.get("group_hash_salt") != design.get("reference_fold_hash_salt"), "group and fold assignments use distinct salts", "scientific")
    add_check(rows, "design_selection_history_only", design.get("selection_uses_evaluation_data") is False, "G, support threshold, and near-tie threshold are history-frozen", "scientific")
    expected_features = {
        "lag_proxy_mean",
        "log1p_lag_proxy_count",
        "lag_proxy_missing",
    }
    features = set(model.get("feature_names", []))
    no_ewma = not any("ewma" in feature.lower() for feature in features)
    add_check(rows, "ridge_feature_contract", expected_features.issubset(features) and no_ewma and model.get("ewma_features_used") is False, f"features={sorted(features)}", "scientific")
    add_check(rows, "ridge_alpha_frozen", np.isclose(float(model["ridge_alpha"]), float(config["ridge_alpha"])), f"alpha={model['ridge_alpha']}", "scientific")
    add_check(rows, "ridge_history_only", model.get("training_split") == "history_only" and model.get("evaluation_model_selection_used") is False, "Ridge fit and model selection are history-only", "scientific")


def _check_metrics_and_routes(rows: list[dict[str, object]], output_dir: Path) -> str:
    primary = pd.read_csv(output_dir / "tables" / "exp3_primary_route_results.csv")
    expected_routes = {"arrival_carrier", "history_mean_control", "ridge_proxy"}
    add_check(rows, "primary_route_boundary", set(primary["route_id"].astype(str)) == expected_routes, f"routes={sorted(primary['route_id'].astype(str))}", "scientific")
    route_meta_ok = (
        (~primary["uses_future_outcome"].astype(bool)).all()
        and (~primary["uses_source_identity"].astype(bool)).all()
        and primary["is_deployable"].astype(bool).all()
    )
    add_check(rows, "route_metadata_boundary", bool(route_meta_ok), "operational routes use neither future outcomes nor source identity", "scientific")
    sensitivity_contract = (
        set(primary["resampling_range_method"].astype(str)) == {DEFAULT_CONFIG.resampling_range_method}
        and set(primary["uncertainty_role"].astype(str)) == {DEFAULT_CONFIG.resampling_output_role}
        and (~primary["formal_ci_validated"].astype(bool)).all()
    )
    add_check(rows, "primary_uncertainty_interface", sensitivity_contract, "full-sample point + percentile user-resampling sensitivity; formal_ci=false", "scientific")

    support_cells = pd.read_csv(output_dir / "derived" / "exp3_evaluation_support_cells.csv")
    support = pd.read_csv(output_dir / "tables" / "exp3_support_coverage.csv").iloc[0]
    pair_expected = float(support_cells["pair_coverage"].mean())
    action_expected = float(support_cells["action_coverage"].mean())
    unit_expected = float(support_cells["is_valid_audit_unit"].astype(bool).mean())
    support_ok = (
        np.isclose(float(support["pair_coverage"]), pair_expected)
        and np.isclose(float(support["action_coverage"]), action_expected)
        and np.isclose(float(support["audit_unit_coverage"]), unit_expected)
    )
    add_check(rows, "evaluation_support_reconstruction", support_ok, f"action={action_expected:.4f}; pair={pair_expected:.4f}; units={unit_expected:.4f}", "scientific")
    support_status = str(support["scientific_support_status"])
    add_check(rows, "support_not_blocked", support_status != "STOP_AND_REVIEW", f"support_status={support_status}", "scientific")
    route_ok, route_detail = route_selection_diagnostics_match(output_dir)
    add_check(rows, "route_selection_diagnostics", route_ok, route_detail, "scientific")
    return support_status


def _check_bootstrap(rows: list[dict[str, object]], output_dir: Path, bootstrap: dict[str, Any]) -> None:
    add_check(rows, "bootstrap_valid_fraction", float(bootstrap["valid_bootstrap_fraction"]) >= float(bootstrap["valid_bootstrap_fraction_gate"]), f"valid_fraction={bootstrap['valid_bootstrap_fraction']}", "engineering")
    reconstructs = all(bool(bootstrap[key]) for key in ("bootstrap_reconstructs_support", "bootstrap_reconstructs_reference_action", "bootstrap_reconstructs_pair_set"))
    add_check(rows, "bootstrap_reconstructs_estimand", reconstructs, "support, reference action, and pair set are rebuilt", "scientific")
    add_check(rows, "bootstrap_does_not_retrain_proxy", bootstrap.get("bootstrap_retrains_proxy_model") is False, "uncertainty is conditional on the frozen history proxy", "scientific")
    add_check(rows, "bootstrap_seed_contract", bootstrap.get("replication_seed_rule") == "SeedSequence([bootstrap_seed, replication_id])", str(bootstrap.get("replication_seed_rule")), "engineering")
    interface_ok = (
        bootstrap.get("displayed_range_method") == DEFAULT_CONFIG.resampling_range_method
        and bootstrap.get("resampling_output_role") == DEFAULT_CONFIG.resampling_output_role
        and bootstrap.get("formal_ci_validated") is False
        and bootstrap.get("uncertainty_interface_status") == "SENSITIVITY_ONLY_ACCEPTED"
    )
    add_check(rows, "resampling_sensitivity_interface", interface_ok, str(bootstrap.get("displayed_range_method")), "scientific")
    audit_ok, audit_detail = bootstrap_interval_audit_matches(output_dir)
    add_check(rows, "resampling_sensitivity_audit_reconstruction", audit_ok, audit_detail, "scientific")
    add_check(rows, "resampling_bias_is_disclosed", bootstrap.get("legacy_basic_interval_retained_for_audit") is True and bootstrap.get("resampling_centering_status") in {"PASS", "PASS_WITH_WARNING"}, f"centering_status={bootstrap.get('resampling_centering_status')}; warnings={bootstrap.get('bootstrap_bias_warning_count')}", "scientific")


def _check_full_preflight(rows: list[dict[str, object]], output_dir: Path, manifest: dict[str, Any]) -> None:
    preflight = load_json(output_dir / "diagnostics" / "exp3_full_design_support_preflight.json")
    status = str(preflight["status"])
    evaluable = not status.startswith("NOT_EVALUATED")
    if evaluable:
        selection_ok = preflight.get("selection_uses_evaluation_data") is False
        bounds_ok = all(0.0 <= float(preflight[key]) <= 1.0 for key in ("evaluation_action_coverage", "evaluation_pair_coverage", "evaluation_audit_unit_coverage"))
        add_check(rows, "full_preflight_history_only_selection", selection_ok, f"selected_G={preflight.get('selected_user_group_count')}", "scientific")
        add_check(rows, "full_preflight_metric_bounds", bounds_ok, status, "engineering")
    else:
        add_check(rows, "full_preflight_fixture_declaration", bool(manifest.get("synthetic_fixture")), status, "engineering")
    action_coverage = pd.read_csv(output_dir / "tables" / "exp3_action_space_coverage.csv")
    coverage_ok = action_coverage["selected_action_exposure_mass_coverage"].between(0, 1).all()
    add_check(rows, "action_space_scope_reported", bool(coverage_ok) and {"active_run", "full_design_preflight"}.issubset(set(action_coverage["design_scope"])), "selected-action exposure mass is reported separately from support coverage", "scientific")
    readiness_ok = (
        "full_recommended" not in preflight
        and preflight.get("full_design_support_ready")
        == (status in {"READY", "READY_WITH_LIMITED_SUPPORT"})
    )
    add_check(rows, "support_readiness_semantics", readiness_ok, status, "engineering")


def _check_figures(rows: list[dict[str, object]], output_dir: Path) -> None:
    main_ok, main_detail = main_figure_data_matches(output_dir)
    add_check(rows, "main_figure_data_contract", main_ok, main_detail, "engineering")
    appendix_ok, appendix_detail = full_preflight_figure_data_matches(output_dir)
    add_check(rows, "full_preflight_figure_data_contract", appendix_ok, appendix_detail, "engineering")
    dependence_ok, dependence_detail = dependence_figure_data_matches(output_dir)
    add_check(rows, "dependence_figure_data_contract", dependence_ok, dependence_detail, "engineering")
    arrival_ok, arrival_detail = arrival_figure_data_matches(output_dir)
    add_check(rows, "arrival_carrier_figure_data_contract", arrival_ok, arrival_detail, "engineering")
    hash_ok, hash_detail = figure_metadata_hashes_match(output_dir)
    add_check(rows, "figure_source_hash_contract", hash_ok, hash_detail, "engineering")


def write_self_check_outputs(
    output_dir: Path,
    manifest: dict[str, Any],
    result: dict[str, Any],
    rows: list[dict[str, object]],
) -> None:
    """Synchronize final self-check status across every public status carrier."""
    (output_dir / "checks").mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(rows)
    for key in (
        "pipeline_execution_status",
        "independent_self_check_status",
        "archival_integrity_check_status",
        "final_engineering_status",
        "scientific_contract_status",
        "scientific_uncertainty_status",
        "figure_data_contracts",
        "artifact_manifest_status",
    ):
        summary[key] = result[key]
    summary.to_csv(output_dir / "checks" / "exp3_self_check.csv", index=False)
    summary.to_csv(output_dir / "checks" / "exp3_self_check_summary.csv", index=False)
    save_json(result, output_dir / "checks" / "exp3_self_check.json")
    synchronize_run_outputs(output_dir, manifest)
    build_artifact_manifest(output_dir)


def run_self_check(output_dir: Path, promote_paper_result: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    missing_processed: list[str] = []
    for split_id in ("history", "evaluation"):
        base = output_dir / "processed" / f"exp3_{split_id}_events_with_targets"
        if not base.with_suffix(".parquet").exists() and not base.with_suffix(".csv").exists():
            missing_processed.append(split_id)
    if missing_processed:
        raise RuntimeError(
            "INDEPENDENT_SELF_CHECK_BLOCKED: event-level processed data are missing for "
            f"{missing_processed}. This directory can only receive archival integrity "
            "verification; archival verification is not independent reconstruction."
        )
    artifacts = _required_artifacts(output_dir)
    missing = [f"{key}={path}" for key, path in artifacts.items() if not path.exists()]
    if missing:
        raise RuntimeError("SELF_CHECK_BLOCKED: required artifacts are missing: " + "; ".join(missing))

    manifest = load_json(artifacts["manifest"])
    config = load_json(artifacts["config"])
    design = load_json(artifacts["design"])
    split = load_json(artifacts["split_manifest"])
    model = load_json(artifacts["model_manifest"])
    bootstrap = load_json(artifacts["bootstrap"])
    rows: list[dict[str, object]] = []

    artifact_ok, artifact_detail = verify_artifact_manifest(output_dir, archival=False)
    add_check(rows, "artifact_manifest_frozen_hashes", artifact_ok, artifact_detail, "engineering")
    current_version = code_version(Path(__file__).resolve().parent)
    figure_metadata = [
        load_json(path)
        for path in sorted((output_dir / "figures" / "metadata").glob("*.json"))
    ]
    version_ok = (
        manifest.get("code_version_type") == current_version["code_version_type"]
        and manifest.get("code_version") == current_version["code_version"]
        and design.get("code_version_type") == current_version["code_version_type"]
        and design.get("code_version") == current_version["code_version"]
        and bool(figure_metadata)
        and all(meta.get("code_version_type") == current_version["code_version_type"] for meta in figure_metadata)
        and all(meta.get("code_version") == current_version["code_version"] for meta in figure_metadata)
        and current_version["code_version"] != "unknown"
    )
    add_check(rows, "code_version_consistency", version_ok, current_version["code_version"], "engineering")

    pipeline_completed = (
        manifest.get("pipeline_execution_status", manifest.get("engineering_status")) == "PASS"
        and bool(manifest.get("completed_at_utc"))
    )
    add_check(rows, "pipeline_completed", pipeline_completed, str(manifest.get("pipeline_execution_status")), "engineering")
    _check_input_and_time(rows, output_dir, manifest, config, split)
    _check_design_and_model(rows, output_dir, config, design, model)
    support_status = _check_metrics_and_routes(rows, output_dir)
    _check_bootstrap(rows, output_dir, bootstrap)
    _check_full_preflight(rows, output_dir, manifest)
    _check_figures(rows, output_dir)

    run_tier = str(manifest["run_tier"])
    if run_tier == "fast":
        add_check(rows, "fast_never_paper_result", manifest.get("paper_result") is False, "fast is never paper eligible", "paper")
        add_check(rows, "fast_scaled_support_declared", design.get("support_threshold_is_fast_scaled") is True, "fast primary support is explicitly scaled", "scientific")
        expected_input = "synthetic_fixture" if bool(manifest.get("synthetic_fixture")) else "original_kuairand_inputs"
        add_check(rows, "fast_input_declared", manifest.get("input_data_status") == expected_input, expected_input, "engineering")
    else:
        add_check(rows, "full_threshold_frozen", int(design["support_min_events_per_fold"]) == int(config["support_min_events_per_fold_full"]), f"threshold={design['support_min_events_per_fold']}", "scientific")
        add_check(rows, "full_not_synthetic", manifest.get("synthetic_fixture") is False, "full uses frozen KuaiRand inputs", "paper")
        preflight = load_json(artifacts["full_preflight"])
        add_check(rows, "full_preflight_ready", preflight.get("full_design_support_ready") is True, str(preflight.get("status")), "scientific")
    engineering_pass = all(row["status"] == "PASS" for row in rows if row["category"] == "engineering")
    scientific_pass = all(row["status"] == "PASS" for row in rows if row["category"] == "scientific") and support_status == "PASS"
    scientific_contract_status = "PASS" if scientific_pass else support_status
    uncertainty_status = scientific_uncertainty_status(bootstrap)
    independent_status = "PASS" if engineering_pass and scientific_pass else "FAIL"
    if run_tier == "full":
        scientific_status = scientific_contract_status if uncertainty_status == "SENSITIVITY_ONLY_ACCEPTED" else "FAIL"
    elif bool(manifest.get("synthetic_fixture")):
        scientific_status = "NOT_EVALUATED_FAST_FIXTURE"
    else:
        scientific_status = "NOT_EVALUATED_FAST_REAL"
    input_check_ids = {
        "timezone_rule",
        "interval_convention",
        "strict_temporal_split",
        "boundary_quarantine_within_frozen_limits",
        "boundary_quarantine_reported",
        "boundary_quarantine_summary_reconstruction",
        "history_target_window_contract",
        "evaluation_target_window_contract",
        "target_reuse_summary_reconstruction",
        "dependence_structure_disclosed",
    }
    input_audit_status = "PASS" if all(
        row["status"] == "PASS" for row in rows if row["check_id"] in input_check_ids
    ) else "FAIL"
    figure_check_ids = {
        "main_figure_data_contract",
        "full_preflight_figure_data_contract",
        "dependence_figure_data_contract",
        "arrival_carrier_figure_data_contract",
        "figure_source_hash_contract",
    }
    figure_status = "PASS" if all(
        row["status"] == "PASS" for row in rows if row["check_id"] in figure_check_ids
    ) else "FAIL"
    manifest.update(
        {
            "independent_self_check_status": independent_status,
            "scientific_status": scientific_status,
            "scientific_contract_status": scientific_contract_status,
            "scientific_uncertainty_status": uncertainty_status,
            "input_audit_status": input_audit_status,
            "figure_data_contract_status": figure_status,
            "figure_data_contracts": figure_status,
            "artifact_manifest_status": "PASS" if artifact_ok else "FAIL",
            "archival_integrity_check_status": "NOT_RUN",
            "paper_result": bool(manifest.get("paper_result", False)),
        }
    )
    manifest["final_engineering_status"] = calculate_final_engineering_status(manifest)
    manifest["engineering_status"] = manifest["final_engineering_status"]
    manifest.update(readiness_fields(manifest))
    final_engineering_status = str(manifest["final_engineering_status"])
    paper_gate = bool(manifest["paper_promotion_eligible"])
    if promote_paper_result:
        if not paper_gate:
            raise RuntimeError("Paper promotion blocked: all full readiness gates are required.")
        manifest.update({"paper_result": True, "paper_status": "PASS"})
        plot_main_figure(output_dir, run_tier, paper_result=True)
        plot_appendix_figures(output_dir, run_tier, paper_result=True)
    result = {
        "pipeline_execution_status": manifest.get("pipeline_execution_status"),
        "independent_self_check_status": independent_status,
        "archival_integrity_check_status": manifest["archival_integrity_check_status"],
        "final_engineering_status": final_engineering_status,
        "engineering_status": final_engineering_status,
        "scientific_status": scientific_status,
        "scientific_contract_status": scientific_contract_status,
        "scientific_uncertainty_status": uncertainty_status,
        "formal_ci_validated": False,
        "figure_data_contracts": figure_status,
        "artifact_manifest_status": manifest["artifact_manifest_status"],
        "full_design_support_ready": bool(manifest.get("full_design_support_ready", False)),
        "full_run_recommended": bool(manifest.get("full_run_recommended", False)),
        "paper_promotion_eligible": paper_gate,
        "paper_result": bool(manifest.get("paper_result", False)),
        "code_version_type": manifest.get("code_version_type"),
        "code_version": manifest.get("code_version"),
        "checks": rows,
    }
    write_self_check_outputs(output_dir, manifest, result, rows)
    for key in (
        "pipeline_execution_status",
        "independent_self_check_status",
        "archival_integrity_check_status",
        "final_engineering_status",
        "scientific_status",
        "scientific_contract_status",
        "scientific_uncertainty_status",
    ):
        print(f"{key}={result[key]}")
    print(f"full_design_support_ready={str(result['full_design_support_ready']).lower()}")
    print(f"full_run_recommended={str(result['full_run_recommended']).lower()}")
    print(f"paper_promotion_eligible={str(result['paper_promotion_eligible']).lower()}")
    print(f"paper_result={str(result['paper_result']).lower()}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "full"], required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--promote-paper-result", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.output_dir is not None and args.run_id is not None:
        raise SystemExit("Use only one of --output-dir and --run-id.")
    if args.output_dir is not None:
        output_dir = args.output_dir
    elif args.run_id is not None:
        from runner import resolve_run_id
        output_dir = resolve_run_id(root, args.run_id, args.mode)
    else:
        from runner import resolve_latest_completed_run
        output_dir = resolve_latest_completed_run(root, args.mode)
    run_self_check(output_dir, promote_paper_result=args.promote_paper_result)


if __name__ == "__main__":
    main()
