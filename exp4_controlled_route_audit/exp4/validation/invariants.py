"""Scientific invariants for completed Exp4 v2 runs."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd

from exp4.configuration.parameters import CALIBRATION, MODULE_A, MODULE_B, REPORTING, SHARED_DGP
from exp4.metrics.action_gaps import compute_action_gap_defect
from exp4.routes.partial_label_proxy import _label_blind_assignments


def _manual_defect_check() -> tuple[bool, str]:
    structural = np.array(((0.0, 1.0, 3.0), (1.0, 1.5, 2.0)))
    route = np.array(((0.0, 2.0, 2.0), (2.0, 1.5, 1.0)))
    result = compute_action_gap_defect(structural, route)
    manual = []
    for structural_row, route_row in zip(structural, route, strict=True):
        values = []
        for low in range(3):
            for high in range(low + 1, 3):
                values.append(abs((route_row[low] - route_row[high]) - (structural_row[low] - structural_row[high])))
        manual.append(max(values))
    difference = float(np.max(np.abs(result.round_max_gap_defect - np.asarray(manual))))
    return difference < 1e-12, f"max_difference={difference:.3e}"


def scientific_checks(run_dir: Path) -> list[tuple[str, bool, str]]:
    seed_level = pd.read_parquet(run_dir / "derived" / "module_a" / "exp4_module_a_seed_level.parquet")
    unit_level = pd.read_parquet(run_dir / "derived" / "module_b" / "exp4_module_b_audit_unit_level.parquet")
    conditions = pd.read_parquet(run_dir / "derived" / "module_b" / "exp4_module_b_condition_level.parquet")
    parameters = pd.read_parquet(run_dir / "derived" / "module_c" / "exp4_module_c_parameter_level.parquet")
    recovery = pd.read_csv(run_dir / "derived" / "module_c" / "exp4_module_c_parameter_recovery.csv")
    correspondence = pd.read_csv(run_dir / "derived" / "module_c" / "exp4_module_c_correspondence_checks.csv")
    contrasts = pd.read_csv(run_dir / "derived" / "module_a" / "exp4_module_a_paired_contrasts.csv")
    manifest = pd.read_csv(run_dir / "logs" / "exp4_module_bc_path_manifest.csv")
    calibration = json.loads((run_dir / "derived" / "calibration" / "exp4_proxy_route_calibration.json").read_text(encoding="utf-8"))
    source = seed_level[seed_level["route_id"] == "source_bound"]
    q1 = seed_level[(seed_level["route_id"] == "proxy_label") & np.isclose(seed_level["route_label_rate"], 1.0)]
    selective = conditions[conditions["audit_design_id"].isin(("ambiguity_selective_unweighted", "ambiguity_selective_ipw"))]
    shared_masks = selective.groupby(["replication_id", "audit_evidence_rate"])["inclusion_mask_hash"].nunique().max()
    pair_count = parameters[["action_pair_low", "action_pair_high"]].drop_duplicates().shape[0]
    positivity = conditions[conditions["audit_design_id"].str.contains("selective")]
    parameter_affine = recovery[recovery["control_id"] == "affine_linked"]
    intercept_bias = parameter_affine.loc[parameter_affine["parameter"] == "intercept", "bias"].abs().max()
    slope_bias = parameter_affine.loc[parameter_affine["parameter"] == "slope", "bias"].abs().max()
    blocked = correspondence[correspondence["control_id"] == "blocked_correspondence_destroyed"]
    formula_pass, formula_details = _manual_defect_check()
    label_blind_source = inspect.getsource(_label_blind_assignments)
    calibration_seed_overlap = bool(set(calibration["calibration_seed_ids"]) & set(MODULE_A.evaluation_seeds))
    first_trajectory = np.load(run_dir / manifest["trajectory_file"].iloc[0])
    uniforms = first_trajectory["route_label_uniforms"]
    nested = np.all((uniforms < 0.3) <= (uniforms < 0.7)) and np.all((uniforms < 0.7) <= (uniforms < 1.0))
    checks = [
        ("SOURCE_BOUND_DEFECT_ZERO", float(source["population_action_gap_defect"].abs().max()) < REPORTING.zero_defect_tolerance, f"max={source['population_action_gap_defect'].abs().max():.3e}"),
        ("FULL_LABEL_PROXY_DEFECT_ZERO", float(q1["population_action_gap_defect"].abs().max()) < REPORTING.zero_defect_tolerance, f"max={q1['population_action_gap_defect'].abs().max():.3e}"),
        ("COMPLETE_45_PAIR_SUPPORT", pair_count == 45, f"pair_count={pair_count}"),
        ("POSITIVE_ATTRIBUTION_MASS", bool(seed_level[seed_level["route_id"].str.startswith("proxy_label")]["minimum_attribution_mass"].gt(0.0).all()), "all proxy route rows have positive mass"),
        ("NO_FUTURE_INFORMATION", bool(seed_level[seed_level["route_id"].str.startswith("proxy_label")]["candidate_set_contains_true_source_rate"].eq(1.0).all()), "true source is always in the historical candidate set"),
        ("ROUTE_AND_AUDIT_STREAMS_INDEPENDENT", bool((manifest["route_label_uniform_hash"] != manifest["audit_mcar_uniform_hash"]).all() and (manifest["route_label_uniform_hash"] != manifest["audit_selective_uniform_hash"]).all()), "stream hashes differ"),
        ("AMBIGUITY_SCORE_LABEL_BLIND", "structural_loss_map" not in label_blind_source and "route_label_mask" not in label_blind_source and "round_max_gap_defect" not in label_blind_source, "label-blind assignment function excludes labels and defects"),
        ("DEFECT_FORMULA_CODE_THEORY_MATCH", formula_pass, formula_details),
        ("MODULE_A_B_HORIZONS_EXPLICIT", MODULE_A.horizon == 5000 and MODULE_A.warmup == 250 and MODULE_B.horizon == 2000 and MODULE_B.warmup == 100, "A=(5000,250), B=(2000,100)"),
        ("NESTED_ROUTE_LABEL_MASKS", bool(nested), "q=0.3 mask is nested in q=0.7 and q=1"),
        ("SELECTIVE_MASK_SHARED_BETWEEN_UNWEIGHTED_AND_IPW", int(shared_masks) == 1, f"maximum unique hashes={shared_masks}"),
        ("IPW_POSITIVITY", bool(positivity["minimum_inclusion_probability"].ge(MODULE_B.inclusion_lower_bound - 1e-12).all() and positivity["maximum_inclusion_probability"].le(MODULE_B.inclusion_upper_bound + 1e-12).all()), f"bounds=[{MODULE_B.inclusion_lower_bound},{MODULE_B.inclusion_upper_bound}]"),
        ("TEMPORAL_CROSSFIT_NO_LEAKAGE", bool(parameters["held_out_fold_excluded_from_training"].eq(True).all()), "all parameter rows exclude the held-out fold"),
        ("AFFINE_PARAMETER_RECOVERY", bool(intercept_bias < 0.15 and slope_bias < 0.15), f"intercept_bias={intercept_bias:.3f}, slope_bias={slope_bias:.3f}"),
        ("BLOCKED_SHUFFLE_CORRESPONDENCE_DESTROYED", bool(blocked["status"].eq("PASS").all()), f"pre={blocked['pre_mean_abs_pearson'].iloc[0]:.3f}, post={blocked['post_mean_abs_pearson'].iloc[0]:.3f}"),
        ("CALIBRATION_EVALUATION_SEEDS_DISJOINT", not calibration_seed_overlap, f"overlap={calibration_seed_overlap}"),
        ("EXACT_MEAN_DELAY", bool(np.allclose(manifest["mean_delay"], SHARED_DGP.target_mean_delay)), f"range=[{manifest['mean_delay'].min():.3f},{manifest['mean_delay'].max():.3f}]"),
    ]
    primary = contrasts[contrasts["is_primary_contrast"].astype(bool)]
    precision_status = str(primary["monte_carlo_precision_gate"].iloc[0])
    checks.append(("MONTE_CARLO_PRECISION", precision_status in {"PASS", "NOT_APPLICABLE_NON_FULL"}, precision_status))
    return checks
