"""Independent scientific and engineering contract checks for Exp3."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG
from design_contract import EVALUATION_ARRAY_SCHEMA_VERSION, METRIC_BY_ID, design_contract_hash
from self_check_helpers import (
    add_check,
    arrival_figure_data_matches,
    boundary_quarantine_summary_matches,
    bootstrap_interval_audit_matches,
    dependence_figure_data_matches,
    dependence_structure_matches,
    figure_metadata_hashes_match,
    full_preflight_figure_data_matches,
    load_json,
    main_figure_data_matches,
    ridge_selection_contract_matches,
    route_selection_diagnostics_match,
    target_component_audit_matches,
    target_contract_matches,
    target_reuse_summary_matches,
    two_fold_contract_matches,
)
from utilities import read_frame


def required_artifacts(output_dir: Path) -> dict[str, Path]:
    return {
        "manifest": output_dir / "metadata/run_manifest.json",
        "config": output_dir / "metadata/run_config_snapshot.json",
        "design": output_dir / "design/exp3_design_freeze.json",
        "split_manifest": output_dir / "design/exp3_split_manifest.json",
        "model_manifest": output_dir / "metadata/exp3_model_manifest.json",
        "ridge_selection": output_dir / "metadata/exp3_ridge_selection_manifest.json",
        "ridge_cv": output_dir / "tables/exp3_ridge_history_cv.csv",
        "metric_registry": output_dir / "tables/exp3_metric_registry.csv",
        "bootstrap": output_dir / "checks/exp3_bootstrap_diagnostics.json",
        "resampling_audit": output_dir / "checks/exp3_resampling_sensitivity_audit.csv",
        "primary_results": output_dir / "tables/exp3_primary_route_results.csv",
        "paired_results": output_dir / "tables/exp3_paired_ranking_contrast.csv",
        "support": output_dir / "tables/exp3_support_coverage.csv",
        "support_cells": output_dir / "derived/exp3_evaluation_support_cells.csv",
        "route_selection": output_dir / "diagnostics/exp3_route_selection_diagnostics.csv",
        "full_preflight": output_dir / "diagnostics/exp3_full_design_support_preflight.json",
        "action_coverage": output_dir / "tables/exp3_action_space_coverage.csv",
        "target_reuse": output_dir / "tables/exp3_target_reuse_audit.csv",
        "target_component": output_dir / "tables/exp3_target_component_audit.csv",
        "data_dependence": output_dir / "tables/exp3_data_dependence_structure.csv",
        "resampling_structure": output_dir / "tables/exp3_resampling_structure_diagnostics.csv",
        "boundary_quarantine": output_dir / "tables/exp3_boundary_quarantine_audit.csv",
        "main_figure": output_dir / "figures/data/exp3_main_score_gap_ranking_data.csv",
        "dependence_figure": output_dir / "figures/data/exp3_appendix_dependence_and_selection_structure_data.csv",
        "arrival_figure": output_dir / "figures/data/exp3_appendix_arrival_carrier_diagnostic_data.csv",
        "artifact_manifest": output_dir / "manifest/artifact_manifest.csv",
    }


def check_input_and_time(
    rows: list[dict[str, object]],
    output_dir: Path,
    manifest: dict[str, Any],
    config: dict[str, Any],
    split: dict[str, Any],
) -> None:
    add_check(rows, "timezone_rule", split.get("timezone_rule") == config.get("timezone_rule"), str(split.get("timezone_rule")), "scientific")
    add_check(rows, "interval_convention", split.get("interval_convention") == "left_closed_right_open", str(split.get("interval_convention")), "scientific")
    strict = int(split["history_end_time_exclusive"]) <= int(split["evaluation_start_time"])
    add_check(rows, "strict_temporal_split", strict, "history ends before evaluation", "scientific")
    history_fraction = float(split.get("history_prestart_fraction", 0.0))
    evaluation_fraction = float(split.get("evaluation_preboundary_fraction", 0.0))
    quarantine_ok = history_fraction <= float(config["max_prestart_history_fraction"]) and evaluation_fraction <= float(config["max_preboundary_evaluation_fraction"])
    add_check(rows, "boundary_quarantine_within_frozen_limits", quarantine_ok, f"history={history_fraction:.6%}; evaluation={evaluation_fraction:.6%}", "scientific")
    count = int(split.get("history_events_excluded_before_start", 0)) + int(split.get("evaluation_events_excluded_before_boundary", 0))
    expected_status = "PASS_WITH_BOUNDARY_QUARANTINE" if count else "PASS"
    reported = manifest.get("input_boundary_status") == expected_status and int(manifest.get("boundary_quarantine_event_count", -1)) == count
    add_check(rows, "boundary_quarantine_reported", reported, f"status={expected_status}; count={count}", "engineering")
    boundary_ok, detail = boundary_quarantine_summary_matches(output_dir)
    add_check(rows, "boundary_quarantine_summary_reconstruction", boundary_ok, detail, "engineering")
    for split_id, end_key in (("history", "history_end_time_exclusive"), ("evaluation", "evaluation_end_time_exclusive")):
        try:
            frame = read_frame(output_dir / "processed" / f"exp3_{split_id}_events_with_targets.parquet")
            passed, detail = target_contract_matches(frame, int(split[end_key]))
        except FileNotFoundError:
            passed, detail = False, "targeted event artifact missing"
        add_check(rows, f"{split_id}_target_window_contract", passed, detail, "scientific")
    for check_id, function, category in (
        ("target_reuse_summary_reconstruction", target_reuse_summary_matches, "engineering"),
        ("target_component_audit_reconstruction", target_component_audit_matches, "scientific"),
        ("dependence_structure_disclosed", dependence_structure_matches, "scientific"),
    ):
        passed, detail = function(output_dir)
        add_check(rows, check_id, passed, detail, category)


def check_design_and_model(
    rows: list[dict[str, object]],
    output_dir: Path,
    design: dict[str, Any],
    model: dict[str, Any],
) -> None:
    actions = pd.read_csv(output_dir / "design/exp3_action_vocabulary.csv")
    candidate = actions[actions["is_candidate_action"].astype(str).str.lower().isin({"true", "1"})]
    add_check(rows, "candidate_action_count", len(candidate) == len(design["candidate_actions"]), f"candidate_count={len(candidate)}", "scientific")
    add_check(rows, "residual_excluded", not bool(design.get("residual_action_is_candidate")), "residual excluded", "scientific")
    add_check(rows, "group_fold_salts_separated", design.get("group_hash_salt") != design.get("reference_fold_hash_salt"), "separate salts", "scientific")
    add_check(rows, "design_selection_history_only", design.get("selection_uses_evaluation_data") is False, "design frozen on history", "scientific")
    features = set(model.get("feature_names", []))
    expected = {"lag_proxy_mean", "log1p_lag_proxy_count", "lag_proxy_missing"}
    feature_ok = expected.issubset(features) and not any("ewma" in item.lower() for item in features) and model.get("ewma_features_used") is False
    add_check(rows, "ridge_feature_contract", feature_ok, f"features={sorted(features)}", "scientific")
    selection_ok, detail = ridge_selection_contract_matches(output_dir)
    add_check(rows, "ridge_alpha_history_only_selection", selection_ok, detail, "scientific")
    add_check(rows, "ridge_history_only", model.get("selection_scope") == "history_only" and model.get("evaluation_model_selection_used") is False, "history-only selection/refit", "scientific")
    fold = design.get("two_fold_contract", {})
    contract_ok = design.get("design_contract_hash") == design_contract_hash() and design.get("evaluation_array_schema_version") == EVALUATION_ARRAY_SCHEMA_VERSION and fold.get("route_action_source") == "selection_fold" and fold.get("heldout_target_source") == "opposite_evaluation_fold"
    add_check(rows, "design_contract_hash_and_fold_metadata", contract_ok, str(fold), "scientific")


def check_metrics_and_routes(rows: list[dict[str, object]], output_dir: Path) -> str:
    primary = pd.read_csv(output_dir / "tables/exp3_primary_route_results.csv")
    expected_routes = {"arrival_carrier", "history_mean_control", "ridge_proxy"}
    add_check(rows, "primary_route_boundary", set(primary["route_id"].astype(str)) == expected_routes, str(expected_routes), "scientific")
    route_ok = (~primary["uses_future_outcome"].astype(bool)).all() and (~primary["uses_source_identity"].astype(bool)).all() and primary["uses_predecision_available_information"].astype(bool).all() and (~primary["deployment_value_estimated"].astype(bool)).all() and "is_deployable" not in primary.columns
    add_check(rows, "route_metadata_boundary", bool(route_ok), "no deployment-value claim", "scientific")
    uncertainty_ok = set(primary["resampling_range_method"].astype(str)) == {DEFAULT_CONFIG.resampling_range_method} and set(primary["uncertainty_role"].astype(str)) == {DEFAULT_CONFIG.resampling_output_role} and (~primary["formal_ci_validated"].astype(bool)).all()
    add_check(rows, "primary_uncertainty_interface", uncertainty_ok, "sensitivity-only ranges", "scientific")
    cells = pd.read_csv(output_dir / "derived/exp3_evaluation_support_cells.csv")
    support = pd.read_csv(output_dir / "tables/exp3_support_coverage.csv").iloc[0]
    expected_pair = float(cells["reference_pair_coverage"].mean())
    support_ok = np.isclose(float(support["reference_pair_coverage"]), expected_pair) and np.isclose(float(support["action_coverage"]), float(cells["action_coverage"].mean())) and np.isclose(float(support["audit_unit_coverage"]), float(cells["is_valid_audit_unit"].astype(bool).mean()))
    add_check(rows, "evaluation_support_reconstruction", support_ok, f"reference_pair={expected_pair:.4f}", "scientific")
    support_status = str(support["scientific_support_status"])
    add_check(rows, "support_not_blocked", support_status != "STOP_AND_REVIEW", support_status, "scientific")
    for check_id, function in (("route_selection_diagnostics", route_selection_diagnostics_match), ("two_fold_selection_evaluation_contract", two_fold_contract_matches)):
        passed, detail = function(output_dir)
        add_check(rows, check_id, passed, detail, "scientific")
    registry = pd.read_csv(output_dir / "tables/exp3_metric_registry.csv")
    paired_metric = "ridge_over_historical_paired_value_gain"
    route_metric_ids = {
        metric_id
        for metric_id, spec in METRIC_BY_ID.items()
        if spec.estimand_level != "support" and metric_id != paired_metric
    }
    registry_ids = set(registry["metric_id"].astype(str))
    alias = registry[registry["metric_id"] == "pair_coverage"]
    alias_ok = (
        len(alias) == 1
        and bool(alias.iloc[0]["deprecated"])
        and alias.iloc[0]["canonical_metric_id"] == "reference_pair_coverage"
    )
    canonical = (
        route_metric_ids.issubset(primary.columns)
        and set(METRIC_BY_ID).issubset(registry_ids)
        and alias_ok
    )
    add_check(rows, "canonical_metric_registry_and_schema", canonical, f"canonical={canonical}", "engineering")
    paired = pd.read_csv(output_dir / "tables/exp3_paired_ranking_contrast.csv").iloc[0]
    values = primary.set_index("route_id")["signed_cross_fitted_reference_minus_route_value_difference"]
    gain = float(values["history_mean_control"] - values["ridge_proxy"])
    paired_ok = paired["metric_id"] == "ridge_over_historical_paired_value_gain" and np.isclose(float(paired["full_sample_estimate"]), gain) and paired["positive_favors"] == "ridge_proxy"
    add_check(rows, "paired_gain_sign_convention", paired_ok, f"expected_gain={gain}", "scientific")
    return support_status


def check_bootstrap(rows: list[dict[str, object]], output_dir: Path, bootstrap: dict[str, Any]) -> None:
    add_check(rows, "bootstrap_valid_fraction", float(bootstrap["valid_bootstrap_fraction"]) >= float(bootstrap["valid_bootstrap_fraction_gate"]), str(bootstrap["valid_bootstrap_fraction"]), "engineering")
    reconstructs = all(bool(bootstrap[key]) for key in ("bootstrap_reconstructs_support", "bootstrap_reconstructs_reference_action", "bootstrap_reconstructs_pair_set"))
    add_check(rows, "bootstrap_reconstructs_estimand", reconstructs, "support/reference/pairs rebuilt", "scientific")
    frozen = bootstrap.get("bootstrap_retrains_proxy_model") is False and bootstrap.get("ridge_refit_in_resampling") is False
    add_check(rows, "bootstrap_does_not_retrain_proxy", frozen, "conditions on frozen Ridge", "scientific")
    add_check(rows, "bootstrap_seed_contract", bootstrap.get("replication_seed_rule") == "SeedSequence([bootstrap_seed, replication_id])", str(bootstrap.get("replication_seed_rule")), "engineering")
    interface_ok = bootstrap.get("displayed_range_method") == DEFAULT_CONFIG.resampling_range_method and bootstrap.get("resampling_output_role") == DEFAULT_CONFIG.resampling_output_role and bootstrap.get("formal_ci_validated") is False and bootstrap.get("uncertainty_interface_status") == "SENSITIVITY_ONLY_ACCEPTED"
    add_check(rows, "resampling_sensitivity_interface", interface_ok, str(bootstrap.get("displayed_range_method")), "scientific")
    audit_ok, detail = bootstrap_interval_audit_matches(output_dir)
    add_check(rows, "resampling_sensitivity_audit_reconstruction", audit_ok, detail, "scientific")
    disclosure = bootstrap.get("legacy_basic_interval_retained_for_audit") is True and bootstrap.get("resampling_centering_status") in {"PASS", "PASS_WITH_WARNING"}
    add_check(rows, "resampling_bias_is_disclosed", disclosure, str(bootstrap.get("resampling_centering_status")), "scientific")


def check_full_preflight(rows: list[dict[str, object]], output_dir: Path, manifest: dict[str, Any]) -> None:
    preflight = load_json(output_dir / "diagnostics/exp3_full_design_support_preflight.json")
    status = str(preflight["status"])
    if not status.startswith("NOT_EVALUATED"):
        selection_ok = preflight.get("selection_uses_evaluation_data") is False
        keys = ("evaluation_action_coverage", "evaluation_reference_pair_coverage", "evaluation_audit_unit_coverage")
        bounds_ok = all(0.0 <= float(preflight[key]) <= 1.0 for key in keys)
        add_check(rows, "full_preflight_history_only_selection", selection_ok, status, "scientific")
        add_check(rows, "full_preflight_metric_bounds", bounds_ok, status, "engineering")
    else:
        add_check(rows, "full_preflight_fixture_declaration", bool(manifest.get("synthetic_fixture")), status, "engineering")
    coverage = pd.read_csv(output_dir / "tables/exp3_action_space_coverage.csv")
    coverage_ok = coverage["selected_action_exposure_mass_coverage"].between(0, 1).all() and {"active_run", "full_design_preflight"}.issubset(set(coverage["design_scope"]))
    add_check(rows, "action_space_scope_reported", bool(coverage_ok), "exposure scope reported", "scientific")
    readiness_ok = "full_recommended" not in preflight and preflight.get("full_design_support_ready") == (status in {"READY", "READY_WITH_LIMITED_SUPPORT"})
    add_check(rows, "support_readiness_semantics", readiness_ok, status, "engineering")


def check_figures(rows: list[dict[str, object]], output_dir: Path) -> None:
    checks = (
        ("main_figure_data_contract", main_figure_data_matches),
        ("full_preflight_figure_data_contract", full_preflight_figure_data_matches),
        ("dependence_figure_data_contract", dependence_figure_data_matches),
        ("arrival_carrier_figure_data_contract", arrival_figure_data_matches),
        ("figure_source_hash_contract", figure_metadata_hashes_match),
    )
    for check_id, function in checks:
        passed, detail = function(output_dir)
        add_check(rows, check_id, passed, detail, "engineering")


_required_artifacts = required_artifacts
_check_input_and_time = check_input_and_time
_check_design_and_model = check_design_and_model
_check_metrics_and_routes = check_metrics_and_routes
_check_bootstrap = check_bootstrap
_check_full_preflight = check_full_preflight
_check_figures = check_figures
