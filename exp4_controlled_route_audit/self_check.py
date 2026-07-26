"""Engineering and scientific invariant checks for completed Exp4 runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import config
from io_utils import sha256_file, write_json
from route_maps import compute_action_gaps


def _check(name: str, passed: bool, details: str) -> dict[str, str]:
    return {
        "check_name": name,
        "status": "PASS" if passed else "FAIL",
        "details": details,
    }



def _resolve_manifest_path(run_dir: Path, stored_path: object) -> Path:
    """Resolve current relative paths and relocated legacy absolute paths."""
    path = Path(str(stored_path))
    if not path.is_absolute():
        return run_dir / path
    if path.exists():
        return path
    if path.parent.name == "trajectories":
        return run_dir / "raw" / "trajectories" / path.name
    if path.parent.name == "route_maps":
        return run_dir / "raw" / "route_maps" / path.name
    return path


def _reconstruct_calibrated_population_target(run_dir: Path) -> tuple[bool, str]:
    calibrated = pd.read_csv(run_dir / "derived" / "exp4_calibrated_estimates.csv")
    parameters = pd.read_parquet(
        run_dir / "derived" / "exp4_calibration_fold_parameters.parquet"
    )
    target = calibrated[
        (calibrated["replication_id"] == 0)
        & (calibrated["route_id"] == "proxy_label")
        & np.isclose(calibrated["audit_evidence_rate"], 0.3)
        & (calibrated["audit_design_id"] == "mcar_unweighted")
    ]
    if target.empty or not bool(target["is_calibration_estimable"].iloc[0]):
        return False, "Primary reconstruction row is absent or not estimable."
    maps = np.load(run_dir / "raw" / "route_maps" / "replication_0000.npz")
    structural = maps["structural_loss_map"]
    route = maps["proxy_label_route_map"]
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    warmup = int(run_config["mode_settings"]["module_b_warmup_rounds"])
    structural_gap = compute_action_gaps(structural[warmup:])
    route_gap = compute_action_gaps(route[warmup:])
    fold_ids = np.empty(len(structural_gap), dtype=int)
    for fold_id, indices in enumerate(
        np.array_split(np.arange(len(structural_gap)), config.PARAMETERS.audit_temporal_folds)
    ):
        fold_ids[indices] = fold_id
    filtered = parameters[
        (parameters["replication_id"] == 0)
        & (parameters["route_id"] == "proxy_label")
        & np.isclose(parameters["audit_evidence_rate"], 0.3)
        & (parameters["audit_design_id"] == "mcar_unweighted")
    ].copy()
    action_pair_low, action_pair_high = np.triu_indices(config.PARAMETERS.num_actions, k=1)
    calibrated_gap = np.full_like(route_gap, np.nan)
    for fold_id in range(config.PARAMETERS.audit_temporal_folds):
        fold_parameters = filtered[filtered["fold_id"] == fold_id].sort_values(
            ["action_pair_low", "action_pair_high"]
        )
        if len(fold_parameters) != len(action_pair_low):
            return False, f"Fold {fold_id} has {len(fold_parameters)} parameters."
        held_out = fold_ids == fold_id
        intercept = fold_parameters["calibration_intercept"].to_numpy(dtype=float)
        slope = fold_parameters["calibration_slope"].to_numpy(dtype=float)
        calibrated_gap[held_out] = intercept + slope * route_gap[held_out]
    reconstructed = float(np.mean(np.max(np.abs(calibrated_gap - structural_gap), axis=1)))
    stored = float(
        target[
            "population_calibrated_action_gap_defect_conditional_on_fitted_map"
        ].iloc[0]
    )
    difference = abs(reconstructed - stored)
    return difference < 1e-10, f"absolute difference={difference:.3e}"


def run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    derived = run_dir / "derived"
    run_config = json.loads(
        (run_dir / "logs" / "run_config.json").read_text(encoding="utf-8")
    )
    seed_level = pd.read_parquet(derived / "exp4_route_boundary_seed_level.parquet")
    pair_metrics = pd.read_parquet(
        derived / "exp4_route_boundary_pairwise_metrics.parquet"
    )
    audit_units = pd.read_parquet(derived / "exp4_audit_unit_level.parquet")
    raw = pd.read_csv(derived / "exp4_raw_estimates.csv")
    calibrated = pd.read_csv(derived / "exp4_calibrated_estimates.csv")
    population = pd.read_csv(derived / "exp4_population_targets.csv")
    learner = pd.read_csv(derived / "exp4_learner_consequence_appendix.csv")
    path_manifest = pd.read_csv(run_dir / "logs" / "exp4_path_manifest.csv")

    engineering_checks: list[dict[str, str]] = []
    scientific_checks: list[dict[str, str]] = []

    required_paths = [derived / name for name in config.REQUIRED_DERIVED_FILES]
    engineering_checks.append(
        _check(
            "required_derived_files_complete",
            all(path.exists() for path in required_paths),
            f"missing={[path.name for path in required_paths if not path.exists()]}",
        )
    )
    engineering_checks.append(
        _check(
            "result_schema_is_current",
            run_config["result_schema"] == config.RESULT_SCHEMA
            and set(seed_level["result_schema"]) == {config.RESULT_SCHEMA},
            f"run schema={run_config['result_schema']}",
        )
    )
    engineering_checks.append(
        _check(
            "full_or_fast_remains_nonpaper",
            run_config["paper_result"] is False
            and bool(seed_level["paper_result"].eq(False).all()),
            f"run_tier={run_config['run_tier']}, paper_result={run_config['paper_result']}",
        )
    )
    expected_figures = config.PRIMARY_FIGURE_STEMS + config.APPENDIX_FIGURE_STEMS
    figure_complete = all(
        (run_dir / "figures" / "pdf" / f"{stem}.pdf").exists()
        and (run_dir / "figures" / "png" / f"{stem}.png").exists()
        and (run_dir / "figures" / "data" / f"{stem}_data.csv").exists()
        and (run_dir / "figures" / "metadata" / f"{stem}_metadata.json").exists()
        for stem in expected_figures
    )
    engineering_checks.append(
        _check("figure_bundles_complete", figure_complete, f"expected={expected_figures}")
    )
    manifest_hashes_valid = True
    for _, row in path_manifest.iterrows():
        trajectory_path = _resolve_manifest_path(run_dir, row["trajectory_file"])
        if not trajectory_path.exists():
            manifest_hashes_valid = False
            break
    engineering_checks.append(
        _check(
            "trajectory_manifest_paths_exist",
            manifest_hashes_valid,
            f"manifest rows={len(path_manifest)}",
        )
    )

    stored_paths_are_relative = bool(
        path_manifest["trajectory_file"].map(lambda value: not Path(str(value)).is_absolute()).all()
        and path_manifest["route_map_file"].dropna().map(
            lambda value: not Path(str(value)).is_absolute()
        ).all()
    )
    engineering_checks.append(
        _check(
            "path_manifest_is_portable",
            stored_paths_are_relative,
            "Trajectory and route-map paths must be relative to the run directory.",
        )
    )

    first_trajectory_path = _resolve_manifest_path(
        run_dir, path_manifest["trajectory_file"].iloc[0]
    )
    first_trajectory = np.load(first_trajectory_path)
    structural = first_trajectory["structural_loss_map"]
    realized = first_trajectory["realized_potential_feedback"]
    scientific_checks.append(
        _check(
            "structural_and_realized_feedback_are_separate",
            structural.shape == realized.shape and not np.array_equal(structural, realized),
            f"shape={structural.shape}, identical={np.array_equal(structural, realized)}",
        )
    )
    clock_horizon = int(first_trajectory["clock_horizon"][0])
    decision_horizon = int(first_trajectory["decision_horizon"][0])
    delays = first_trajectory["delays"]
    scientific_checks.append(
        _check(
            "extended_clock_covers_all_arrivals",
            int(np.max(np.arange(decision_horizon) + delays)) < clock_horizon,
            f"max_arrival={int(np.max(np.arange(decision_horizon)+delays))}, clock_horizon={clock_horizon}",
        )
    )
    source_rows = seed_level[seed_level["route_id"] == "source_bound"]
    scientific_checks.append(
        _check(
            "source_bound_zero_defect",
            float(source_rows["population_raw_action_gap_defect"].abs().max())
            < config.PARAMETERS.zero_defect_tolerance,
            f"max={source_rows['population_raw_action_gap_defect'].abs().max():.3e}",
        )
    )
    q1_rows = seed_level[
        (seed_level["route_id"] == "proxy_label")
        & np.isclose(seed_level["route_label_rate"], 1.0)
    ]
    scientific_checks.append(
        _check(
            "full_label_proxy_route_zero_defect",
            float(q1_rows["population_raw_action_gap_defect"].abs().max())
            < config.PARAMETERS.zero_defect_tolerance,
            f"max={q1_rows['population_raw_action_gap_defect'].abs().max():.3e}",
        )
    )
    scientific_checks.append(
        _check(
            "proxy_attribution_mass_positive",
            bool(
                seed_level.loc[
                    seed_level["route_id"] == "proxy_label",
                    "minimum_attribution_mass",
                ].gt(0.0).all()
            ),
            "All stored minimum attribution masses are positive.",
        )
    )
    observed_pair_count = pair_metrics[
        ["action_pair_low", "action_pair_high"]
    ].drop_duplicates().shape[0]
    scientific_checks.append(
        _check(
            "pair_count_is_45",
            observed_pair_count == 45,
            f"observed_pair_count={observed_pair_count}",
        )
    )
    scientific_checks.append(
        _check(
            "pair_coverage_complete",
            bool(raw["pair_coverage_rate"].eq(1.0).all()),
            f"minimum={raw['pair_coverage_rate'].min():.3f}",
        )
    )
    biased = raw[raw["inclusion_mechanism"] == "ambiguity_biased"]
    positivity = (
        biased["minimum_inclusion_probability"].ge(
            config.PARAMETERS.inclusion_probability_lower_bound - 1e-12
        ).all()
        and biased["maximum_inclusion_probability"].le(
            config.PARAMETERS.inclusion_probability_upper_bound + 1e-12
        ).all()
    )
    scientific_checks.append(
        _check(
            "biased_inclusion_positivity",
            bool(positivity),
            f"range=[{biased['minimum_inclusion_probability'].min():.3f}, {biased['maximum_inclusion_probability'].max():.3f}]",
        )
    )
    rate_error = (
        biased["mean_inclusion_probability"] - biased["audit_evidence_rate"]
    ).abs().max()
    scientific_checks.append(
        _check(
            "biased_inclusion_rate_solver",
            float(rate_error) < config.PARAMETERS.inclusion_rate_tolerance,
            f"max_error={rate_error:.3e}",
        )
    )
    stream_independence = bool(
        (path_manifest["route_label_uniform_hash"] != path_manifest["audit_mcar_uniform_hash"]).all()
        and (path_manifest["route_label_uniform_hash"] != path_manifest["audit_biased_uniform_hash"]).all()
    )
    scientific_checks.append(
        _check(
            "route_and_audit_stream_hashes_differ",
            stream_independence,
            "Compared path-manifest hashes.",
        )
    )
    correlation_frame = raw[
        (raw["route_id"] == "proxy_label")
        & (raw["audit_evidence_rate"] < 1.0)
    ].drop_duplicates(["replication_id", "audit_evidence_rate", "audit_design_id"])
    mean_correlation = float(
        correlation_frame["route_audit_mask_correlation"].mean(skipna=True)
    )
    scientific_checks.append(
        _check(
            "route_and_audit_mask_empirical_correlation",
            abs(mean_correlation)
            < config.PARAMETERS.route_audit_mask_correlation_tolerance,
            f"mean_correlation={mean_correlation:.4f}",
        )
    )
    scientific_checks.append(
        _check(
            "calibration_not_estimable_has_no_numeric_fallback",
            bool(
                calibrated.loc[
                    ~calibrated["is_calibration_estimable"].astype(bool),
                    "sample_calibrated_action_gap_defect",
                ].isna().all()
            ),
            "Non-estimable rows retain NA calibrated outputs.",
        )
    )
    source_cal = calibrated[calibrated["route_id"] == "source_bound"]
    scientific_checks.append(
        _check(
            "zero_raw_defect_recoverability_is_na",
            bool(source_cal["estimated_recoverability"].isna().all()),
            f"non_na={source_cal['estimated_recoverability'].notna().sum()}",
        )
    )
    reconstructed_raw = (
        audit_units.groupby(["replication_id", "route_id"])[
            "raw_unit_action_gap_defect"
        ]
        .mean()
        .reset_index(name="reconstructed_population_raw")
    )
    comparison = population.merge(
        reconstructed_raw, on=["replication_id", "route_id"], validate="one_to_one"
    )
    raw_reconstruction_error = float(
        (
            comparison["population_raw_action_gap_defect"]
            - comparison["reconstructed_population_raw"]
        )
        .abs()
        .max()
    )
    scientific_checks.append(
        _check(
            "raw_population_target_reconstructable",
            raw_reconstruction_error < 1e-12,
            f"max_error={raw_reconstruction_error:.3e}",
        )
    )
    calibrated_ok, calibrated_details = _reconstruct_calibrated_population_target(run_dir)
    scientific_checks.append(
        _check(
            "conditional_calibrated_target_reconstructable",
            calibrated_ok,
            calibrated_details,
        )
    )
    q1_learner = learner[
        (learner["route_id"] == "proxy_label")
        & np.isclose(learner["route_label_rate"], 1.0)
    ][["seed", "action_trace_sha256"]].rename(
        columns={"action_trace_sha256": "proxy_hash"}
    )
    source_learner = learner[learner["route_id"] == "source_bound"][
        ["seed", "action_trace_sha256"]
    ].rename(columns={"action_trace_sha256": "source_hash"})
    trace_compare = q1_learner.merge(source_learner, on="seed", validate="one_to_one")
    scientific_checks.append(
        _check(
            "full_label_scalar_learner_matches_source_bound",
            bool(trace_compare["proxy_hash"].eq(trace_compare["source_hash"]).all()),
            f"matched={int(trace_compare['proxy_hash'].eq(trace_compare['source_hash']).sum())}/{len(trace_compare)}",
        )
    )

    engineering_status = "PASS" if all(row["status"] == "PASS" for row in engineering_checks) else "FAIL"
    scientific_status = "PASS" if all(row["status"] == "PASS" for row in scientific_checks) else "FAIL"
    engineering_payload = {
        "check_type": "engineering",
        "status": engineering_status,
        "checks": engineering_checks,
    }
    scientific_payload = {
        "check_type": "scientific",
        "status": scientific_status,
        "checks": scientific_checks,
    }
    write_json(engineering_payload, run_dir / "checks" / "exp4_self_check.json")
    write_json(scientific_payload, run_dir / "checks" / "exp4_scientific_check.json")
    return engineering_payload, scientific_payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    arguments = parser.parse_args()
    engineering, scientific = run(arguments.run_dir)
    print(json.dumps({"engineering": engineering["status"], "scientific": scientific["status"]}, indent=2))
    if engineering["status"] != "PASS" or scientific["status"] != "PASS":
        raise SystemExit(1)
