from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.common import load_config, make_output_manifest, out_dir, write_csv


ARRIVAL_TV = "credit_allocation_tv_distance_vs_arrival_anchor"
ARRIVAL_OVERLAP = "top_k_decision_cell_overlap_vs_arrival_anchor"
ESTIMAND_BOUNDARY = (
    "observational logged credit-allocation and source-time decision-cell ranking sensitivity; "
    "not policy value, causal effect, ROI, or deployment evaluation"
)
SOURCE_ROUTE_SET = {"first_click", "last_click", "linear_attribution", "time_decay_soft"}

FIGURES = [
    "fig_exp2_attribution_sensitivity",
    "fig_app_exp2_source_route_pairwise_overlap",
]
TABLES = [
    "tbl_app_exp2_dataset_summary",
    "tbl_app_exp2_candidate_set_summary",
    "tbl_app_exp2_attribution_routes",
    "tbl_exp2_route_sensitivity",
    "tbl_app_exp2_source_linked_audit",
    "tbl_app_exp2_top_k_sensitivity",
    "tbl_app_exp2_candidate_window_sensitivity",
    "tbl_app_exp2_em_assignment_diagnostic",
    "tbl_app_exp2_cost_adjusted_credit_score",
]


@dataclass(frozen=True)
class Check:
    check_id: str
    status: str
    expected: str
    observed: str


def _read_csv(path: Path) -> tuple[bool, pd.DataFrame | None, str]:
    try:
        if not path.exists() or path.stat().st_size == 0:
            return False, None, f"missing or empty: {path}"
        return True, pd.read_csv(path), f"rows={sum(1 for _ in path.open(encoding='utf-8')) - 1}"
    except Exception as exc:
        return False, None, f"read error: {exc}"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _add(rows: list[Check], check_id: str, passed: bool, expected: str, observed: object) -> None:
    rows.append(Check(check_id, "PASS" if passed else "FAIL", expected, str(observed)))


def _core_hash_rows(root: Path) -> pd.DataFrame:
    core_dirs = [root / "processed", root / "summaries", root / "checks"]
    validation_report_names = {
        "exp2_self_check_results.csv",
        "exp2_self_check_report.md",
        "code_check_report.csv",
        "code_check_report.md",
    }
    rows = []
    for directory in core_dirs:
        if not directory.exists():
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            if path.name.startswith("figure_table_repair_") or path.name in validation_report_names:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append({"relative_path": str(path.relative_to(root.parent)).replace("\\", "/").removeprefix("./"), "sha256": digest})
    return pd.DataFrame(rows, columns=["relative_path", "sha256"])


def _normalize_hash_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "relative_path" in normalized.columns:
        normalized["relative_path"] = (
            normalized["relative_path"]
            .astype(str)
            .str.replace("\\", "/", regex=False)
            .str.removeprefix("./")
        )
    return normalized


def _write_figure_table_repair_regression(root: Path) -> dict:
    checks = root / "checks"
    before_path = checks / "figure_table_repair_core_hashes_before.csv"
    after_path = checks / "figure_table_repair_core_hashes_after.csv"
    regression_path = checks / "figure_table_repair_regression.json"
    after = _core_hash_rows(root)
    write_csv(after, after_path)
    if before_path.exists() and before_path.stat().st_size > 0:
        before = _normalize_hash_frame(pd.read_csv(before_path))
    else:
        before = pd.DataFrame(columns=["relative_path", "sha256"])
    after = _normalize_hash_frame(after)
    before_paths = set(before["relative_path"].astype(str)) if "relative_path" in before.columns else set()
    after_paths = set(after["relative_path"].astype(str)) if "relative_path" in after.columns else set()
    merged = before.merge(after, on="relative_path", how="outer", suffixes=("_before", "_after"), indicator=True)
    changed = merged[
        (merged["_merge"] != "both")
        | (merged["sha256_before"].astype(str) != merged["sha256_after"].astype(str))
    ]
    regression = {
        "same_file_set": before_paths == after_paths,
        "same_sha256_for_every_core_file": changed.empty,
        "figure_table_repair_regression_passed": before_paths == after_paths and changed.empty,
        "n_core_files_before": int(len(before)),
        "n_core_files_after": int(len(after)),
        "changed_or_missing_files": changed["relative_path"].astype(str).tolist(),
    }
    regression_path.write_text(json.dumps(regression, indent=2, ensure_ascii=False), encoding="utf-8")
    return regression


def _mark_figure_bundles_failed(root: Path, reason: str) -> None:
    meta_dir = root / "figures" / "metadata"
    data_dir = root / "figures" / "data"
    if not meta_dir.exists():
        return
    for meta_path in meta_dir.glob("*_metadata.json"):
        meta = _read_json(meta_path)
        figure_id = str(meta.get("figure_id", meta_path.name.removesuffix("_metadata.json")))
        if not figure_id:
            continue
        meta["paper_result"] = False
        meta["figure_status"] = "scientific_gate_failed"
        meta["scientific_gate_failure_reason"] = reason
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        data_path = data_dir / f"{figure_id}_data.csv"
        if data_path.exists() and data_path.stat().st_size > 0:
            try:
                data = pd.read_csv(data_path)
                data["paper_result"] = False
                data["figure_status"] = "scientific_gate_failed"
                write_csv(data, data_path)
            except Exception:
                pass


def _completed_through_tables(status: dict, mode: str) -> bool:
    if status.get("status") == "success" and status.get("mode") == mode:
        return True
    if status.get("mode") != mode or status.get("failed_step") != "render_regressions":
        return False
    required_steps = {"precheck", "timeline", "route_assignment", "statistics", "figures", "tables"}
    observed = {
        str(step.get("step"))
        for step in status.get("steps", [])
        if int(step.get("return_code", -1)) == 0
    }
    return required_steps.issubset(observed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic self-check for Experiment 2 source-time attribution sensitivity.")
    parser.add_argument("--config", default="config_exp2.yaml")
    parser.add_argument("--mode", choices=["fast", "full"], required=True)
    parser.add_argument("--allow-running", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    root = out_dir(cfg, "root")
    rows: list[Check] = []
    figure_table_regression = _write_figure_table_repair_regression(root)
    expected_bootstrap = int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"])
    gates = cfg["scientific_gates"]
    main_routes = list(map(str, cfg["attribution_routes"]["main"]))
    figure_routes = list(map(str, cfg["reporting"]["main_figure_routes"]))
    core_source_routes = list(map(str, cfg["reporting"]["core_source_routes"]))
    pairwise_routes = list(map(str, cfg["reporting"]["pairwise_overlap_routes"]))

    _add(rows, "experiment_id", cfg["experiment"]["experiment_id"] == "exp2_logged_attribution_sensitivity", "exp2_logged_attribution_sensitivity", cfg["experiment"]["experiment_id"])
    _add(rows, "source_time_action_unit", cfg["action"]["action_unit"] == "campaign_source_day_cell", "campaign_source_day_cell", cfg["action"]["action_unit"])
    _add(rows, "action_definition_is_campaign_source_day", cfg["action"]["action_unit"] == "campaign_source_day_cell" and cfg["action"]["source_time_bin"] == "calendar_day", "action_id = campaign x source_day", cfg["action"])
    _add(rows, "main_top_k", int(cfg["action"]["main_top_k"]) == 10, "main_top_k=10", cfg["action"]["main_top_k"])
    _add(rows, "main_cost_lambda_zero", float(cfg["utility"]["main_cost_lambda"]) == 0.0, "primary credit summaries use cost_lambda=0", cfg["utility"]["main_cost_lambda"])
    _add(rows, "em_appendix_only", "soft_attribution_em" in main_routes and "soft_attribution_em" not in figure_routes, "EM computed for diagnostic but omitted from main figure", figure_routes)

    status = _read_json(out_dir(cfg, "metadata") / "run_status.json")
    paper_expected = args.mode == "full" and status.get("status") == "success" and not args.allow_running
    allowed = {"success", "running"} if args.allow_running else {"success"}
    status_ok = (status.get("status") in allowed and status.get("mode") == args.mode) or _completed_through_tables(status, args.mode)
    _add(rows, "run_status", status_ok, f"mode={args.mode}, status in {sorted(allowed)} or completed through tables with render_regressions-only failure", status)

    uid_ok, uid_summary, uid_detail = _read_csv(out_dir(cfg, "processed") / "exp2_conversion_uid_integrity_summary.csv")
    if uid_ok and uid_summary is not None:
        values = pd.to_numeric(uid_summary.set_index("metric")["value"], errors="coerce")
        passed = float(values.get("conversion_ids_valid_one_uid", 0)) > 0 and float(values.get("candidate_rows_retained_after_uid_integrity_filter", 0)) > 0
        _add(rows, "uid_integrity_audit", passed, "valid one-UID conversion journeys retained", uid_detail)
    else:
        _add(rows, "uid_integrity_audit", False, "UID integrity audit", uid_detail)

    map_ok, action_map, map_detail = _read_csv(out_dir(cfg, "processed") / "exp2_action_cell_mapping.csv")
    if map_ok and action_map is not None:
        n_actions = int(action_map["action_id"].nunique())
        max_k = max(map(int, cfg["action"]["sensitivity_top_k"]))
        _add(rows, "action_cell_universe", n_actions >= int(cfg["action"]["minimum_eligible_decision_cells"]), f">={cfg['action']['minimum_eligible_decision_cells']} eligible cells", n_actions)
        top_k_ok = n_actions > max_k if bool(gates["max_top_k_must_be_strictly_below_action_universe"]) else True
        _add(rows, "top_k_non_degenerate", top_k_ok, f"action universe > max top_k={max_k}", n_actions)
        _add(rows, "action_cell_universe_exceeds_max_top_k", top_k_ok, f"action universe > max top_k={max_k}", n_actions)
    else:
        n_actions = 0
        _add(rows, "action_cell_universe", False, "eligible action-cell mapping", map_detail)
        _add(rows, "top_k_non_degenerate", False, "action universe > maximum top-k", map_detail)

    conv_ok, conv, conv_detail = _read_csv(out_dir(cfg, "processed") / "exp2_conversion_arrivals.csv")
    if conv_ok and conv is not None:
        main = conv[conv["main_cohort_eligible"].eq(1)].copy()
        uid_contract = not main.empty and main["conversion_id"].notna().all() and main["uid"].notna().all() and main["conversion_id"].nunique() == len(main) and main["uid_integrity_status"].eq("valid_one_uid").all()
        _add(rows, "main_cohort_uid_contract", uid_contract, "one valid UID per main conversion", conv_detail)
    else:
        _add(rows, "main_cohort_uid_contract", False, "main conversion table", conv_detail)

    candidate_ok, candidate, candidate_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_candidate_set_summary.csv")
    if candidate_ok and candidate is not None:
        main_candidate = candidate[candidate["cohort_id"].eq(str(cfg["subsets"]["main_cohort_id"]))]
        ambiguous = float(main_candidate["ambiguous_decision_cell_rate"].iloc[0]) if len(main_candidate) == 1 else np.nan
        _add(rows, "candidate_cohorts_present", set(candidate["cohort_id"].astype(str)) == {str(cfg["subsets"]["main_cohort_id"]), str(cfg["subsets"]["source_linked_audit_cohort_id"])}, "main and audit cohorts", candidate["cohort_id"].tolist())
        ambiguity_ok = np.isfinite(ambiguous) and ambiguous >= float(gates["min_decision_cell_ambiguity_rate"])
        _add(rows, "main_cohort_has_nontrivial_multicell_journeys", ambiguity_ok, "main cohort has multi decision-cell journeys", ambiguous)
        _add(rows, "decision_cell_ambiguity_rate_above_threshold", ambiguity_ok, f">={gates['min_decision_cell_ambiguity_rate']}", ambiguous)
    else:
        _add(rows, "candidate_cohorts_present", False, "candidate summary", candidate_detail)
        _add(rows, "main_cohort_has_nontrivial_multicell_journeys", False, "nontrivial decision-cell ambiguity", candidate_detail)
        _add(rows, "decision_cell_ambiguity_rate_above_threshold", False, "nontrivial decision-cell ambiguity", candidate_detail)

    assign_ok, assignments, assign_detail = _read_csv(out_dir(cfg, "processed") / "exp2_route_assignments.csv")
    if assign_ok and assignments is not None:
        main_id = str(cfg["subsets"]["main_cohort_id"])
        present = set(assignments.loc[assignments["cohort_id"].eq(main_id), "route"].astype(str))
        _add(rows, "main_routes_present", set(main_routes).issubset(present), str(sorted(main_routes)), str(sorted(present)))
        _add(rows, "source_reference_audit_only", not ((assignments["cohort_id"].eq(main_id)) & assignments["route"].eq("source_linked_reference")).any(), "no source-linked reference on main cohort", int(((assignments["cohort_id"].eq(main_id)) & assignments["route"].eq("source_linked_reference")).sum()))
        sums = assignments.groupby(["cohort_id", "route", "conversion_id"], as_index=False)["weight"].sum()
        _add(rows, "route_weights_normalized", np.allclose(sums["weight"].to_numpy(dtype=float), 1.0, rtol=0, atol=1e-8), "route weights sum to one per conversion", float(np.max(np.abs(sums["weight"] - 1.0))))
        anchor = assignments[assignments["route"].eq("arrival_bin_anchor")]
        _add(rows, "arrival_anchor_diagnostic_status", anchor["diagnostic_only"].astype(bool).all() and (~anchor["deployable"].astype(bool)).all(), "constructed arrival anchor must be diagnostic/nondeployable", anchor[["diagnostic_only", "deployable"]].drop_duplicates().to_dict(orient="records"))
        route_names = assignments.groupby("route")["method_display_name"].first().to_dict()
        expected_names = {
            "first_click": "First click or touch",
            "last_click": "Last click or touch",
            "linear_attribution": "Linear attribution",
            "time_decay_soft": "Time-decay attribution",
            "soft_attribution_em": "EM soft attribution",
        }
        _add(rows, "route_display_names_match_fallback_semantics", all(route_names.get(k) == v for k, v in expected_names.items()), str(expected_names), route_names)
    else:
        for name in ["main_routes_present", "source_reference_audit_only", "route_weights_normalized", "arrival_anchor_diagnostic_status"]:
            _add(rows, name, False, "valid route assignments", assign_detail)
        _add(rows, "route_display_names_match_fallback_semantics", False, "fallback-aware display names", assign_detail)

    summary_ok, summary, summary_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_route_sensitivity_summary.csv")
    if summary_ok and summary is not None:
        expected = set(main_routes)
        _add(rows, "main_summary_routes", set(summary["route"].astype(str)) == expected, str(sorted(expected)), str(sorted(set(summary["route"].astype(str)))))
        metric_fields = [
            "top_k_credited_mass_per_1000_events",
            ARRIVAL_TV,
            ARRIVAL_OVERLAP,
        ]
        ci_fields = [item for field in metric_fields for item in (f"{field}_ci_lower", f"{field}_ci_upper")]
        finite = all(field in summary.columns and np.isfinite(pd.to_numeric(summary[field], errors="coerce")).all() for field in ci_fields)
        ordered = all((summary[f"{field}_ci_lower"] <= summary[f"{field}_ci_upper"]).all() for field in metric_fields if f"{field}_ci_lower" in summary.columns)
        _add(rows, "main_summary_ci", bool(finite and ordered), "finite ordered UID-bootstrap intervals for credited mass, allocation TV, and overlap", summary_detail)
        _add(rows, "main_summary_bootstrap_n", set(pd.to_numeric(summary["n_bootstrap"], errors="coerce").astype(int)) == {expected_bootstrap}, str(expected_bootstrap), summary["n_bootstrap"].tolist())
        arrival = summary[summary["route"].eq("arrival_bin_anchor")]
        _add(rows, "arrival_anchor_point", len(arrival) == 1 and abs(float(arrival[ARRIVAL_TV].iloc[0])) < 1e-10 and abs(float(arrival[ARRIVAL_OVERLAP].iloc[0]) - 1.0) < 1e-10, "arrival anchor=(TV=0, top-10 overlap=1)", arrival.to_dict(orient="records"))
        _add(rows, "main_figure_uses_tv_not_credited_mass_displacement", ARRIVAL_TV in summary.columns and "credited_mass_displacement" not in summary.columns, "new allocation-TV field and no credited_mass_displacement", list(summary.columns))
        _add(rows, "no_primary_utility_language", not any("utility" in str(col).lower() for col in summary.columns), "primary summary columns avoid utility naming", list(summary.columns))
    else:
        for name in ["main_summary_routes", "main_summary_ci", "main_summary_bootstrap_n", "arrival_anchor_point", "main_figure_uses_tv_not_credited_mass_displacement", "no_primary_utility_language"]:
            _add(rows, name, False, "main sensitivity summary", summary_detail)

    boot_ok, boot, boot_detail = _read_csv(out_dir(cfg, "raw") / "exp2_uid_bootstrap_replicates.csv")
    _add(rows, "uid_bootstrap_count", bool(boot_ok and boot is not None and int(boot["bootstrap_replicate"].nunique()) == expected_bootstrap), str(expected_bootstrap), boot_detail)

    div_ok, divergence, div_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_main_route_divergence_audit.csv")
    if div_ok and divergence is not None:
        required = len(main_routes) * (len(main_routes) - 1) // 2
        core = divergence[divergence["route_left"].isin(core_source_routes) & divergence["route_right"].isin(core_source_routes)]
        core_tv = pd.to_numeric(core["mean_total_variation_distance"], errors="coerce")
        nonzero = int(core_tv.gt(1e-12).sum())
        threshold_pair_count = int(core_tv.gt(float(gates["min_core_pairwise_tv"])).sum())
        _add(rows, "main_route_divergence_audit", len(divergence) == required and np.isfinite(pd.to_numeric(divergence["mean_total_variation_distance"], errors="coerce")).all(), f"{required} finite pairs", div_detail)
        _add(rows, "core_source_route_pairwise_tv_nonzero", nonzero >= 1, "at least one nonzero-TV pair among core source routes", {"core_routes": core_source_routes, "nonzero_pairs": nonzero})
        _add(rows, "at_least_one_core_pair_tv_above_threshold", threshold_pair_count >= 1, f">={gates['min_core_pairwise_tv']}", {"core_routes": core_source_routes, "above_threshold_pairs": threshold_pair_count})
    else:
        _add(rows, "main_route_divergence_audit", False, "finite route-divergence audit", div_detail)
        _add(rows, "core_source_route_pairwise_tv_nonzero", False, "nonduplicate core source routes", div_detail)
        _add(rows, "at_least_one_core_pair_tv_above_threshold", False, "nonduplicate core source routes", div_detail)

    em_ok, em, em_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_em_assignment_diagnostic.csv")
    if em_ok and em is not None and not em.empty:
        share = float(pd.to_numeric(em["nontrivial_assignment"], errors="coerce").mean())
        _add(rows, "em_positive_entropy_share_above_threshold", share >= float(gates["min_em_positive_entropy_share"]), f">={gates['min_em_positive_entropy_share']}", share)
    else:
        _add(rows, "em_positive_entropy_share_above_threshold", False, "EM diagnostic with nontrivial mass", em_detail)

    pair_fig_ok, pair_fig, pair_fig_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_source_route_pairwise_overlap.csv")
    if pair_fig_ok and pair_fig is not None:
        expected_rows = len(core_source_routes) ** 2
        valid_routes = set(pair_fig["route_left"].astype(str)) == set(core_source_routes) and set(pair_fig["route_right"].astype(str)) == set(core_source_routes)
        diagonal = pair_fig[pair_fig["route_left"].astype(str).eq(pair_fig["route_right"].astype(str))]
        diag_ok = np.allclose(diagonal["pairwise_credit_allocation_tv_distance"], 0.0) and np.allclose(diagonal["pairwise_top_k_overlap"], 1.0)
        _add(rows, "pairwise_overlap_data_exists", len(pair_fig) == expected_rows and valid_routes and diag_ok, "core-route square TV/overlap matrix with correct diagonal", pair_fig_detail)
        _add(
            rows,
            "pairwise_heatmap_excludes_arrival_anchor",
            set(pair_fig["route_left"].astype(str)) == SOURCE_ROUTE_SET
            and set(pair_fig["route_right"].astype(str)) == SOURCE_ROUTE_SET,
            "pairwise heatmap source data contains only first/last/linear/time-decay source routes",
            {
                "route_left": sorted(set(pair_fig["route_left"].astype(str))),
                "route_right": sorted(set(pair_fig["route_right"].astype(str))),
            },
        )
    else:
        _add(rows, "pairwise_overlap_data_exists", False, "pairwise source-route overlap data", pair_fig_detail)
        _add(rows, "pairwise_heatmap_excludes_arrival_anchor", False, "source-route-only pairwise heatmap source data", pair_fig_detail)

    pair_ok, pairwise, pair_detail = _read_csv(out_dir(cfg, "summaries") / "exp2_pairwise_top_k_overlap.csv")
    if pair_ok and pairwise is not None:
        expected_rows = len(cfg["action"]["sensitivity_top_k"]) * len(pairwise_routes) ** 2
        valid_sets = set(pairwise["route_left"].astype(str)).issubset(set(pairwise_routes)) and set(pairwise["route_right"].astype(str)).issubset(set(pairwise_routes))
        values = pd.to_numeric(pairwise["pairwise_top_k_overlap"], errors="coerce")
        _add(rows, "pairwise_top_k_overlap_contract", len(pairwise) == expected_rows and valid_sets and values.between(0, 1).all(), f"{expected_rows} finite overlap cells on configured route set", pair_detail)
    else:
        _add(rows, "pairwise_top_k_overlap_contract", False, "pairwise top-k overlap summary", pair_detail)

    win_ok, window, win_detail = _read_csv(out_dir(cfg, "processed") / "exp2_candidate_window_uid_integrity.csv")
    if win_ok and window is not None:
        expected_windows = set(map(float, cfg["candidate_set"]["window_days_sensitivity"]))
        passed = set(pd.to_numeric(window["candidate_window_days"], errors="coerce")) == expected_windows and (pd.to_numeric(window["missing_reference"], errors="coerce") == 0).all() and (pd.to_numeric(window["uid_mismatch"], errors="coerce") == 0).all()
        _add(rows, "window_specific_uid_contract", passed, "each window has zero missing_reference and uid_mismatch", win_detail)
    else:
        _add(rows, "window_specific_uid_contract", False, "window UID audit", win_detail)

    for figure_id in FIGURES:
        paths = {
            "pdf": root / "figures" / "pdf" / f"{figure_id}.pdf",
            "png": root / "figures" / "png" / f"{figure_id}.png",
            "data": root / "figures" / "data" / f"{figure_id}_data.csv",
            "metadata": root / "figures" / "metadata" / f"{figure_id}_metadata.json",
        }
        data_ok, data, data_detail = _read_csv(paths["data"])
        meta = _read_json(paths["metadata"])
        required_columns = {
            "figure_id", "panel_id", "experiment_id", "setting_id", "method_id", "method_display_name", "information_interface", "reference_role", "diagnostic_only", "deployable", "metric_id", "x_id", "x_value", "y_value", "ci_lower", "ci_upper", "run_mode", "paper_result"
        }
        complete = all(path.exists() and path.stat().st_size > 0 for path in paths.values())
        semantic = meta.get("figure_status") == "generated" and meta.get("run_mode") == args.mode and bool(meta.get("paper_result")) == paper_expected
        metadata_contract = (
            meta.get("estimand_boundary") == ESTIMAND_BOUNDARY
            and meta.get("uncertainty_unit") == "uid"
            and meta.get("input_data_status") == "complete"
            and bool(meta.get("metric_formula_id"))
        )
        _add(rows, f"figure_bundle_{figure_id}", bool(complete and semantic and data_ok and data is not None and required_columns.issubset(data.columns)), f"complete bundle, paper_result={paper_expected}", data_detail)
        if figure_id == "fig_app_exp2_source_route_pairwise_overlap":
            _add(rows, "pairwise_overlap_figure_exists", complete, "pairwise appendix figure bundle exists", data_detail)
            _add(rows, "pairwise_overlap_metadata_exists", bool(metadata_contract), "pairwise metadata has estimand boundary and uid uncertainty", meta)
            source_only = bool(
                data_ok
                and data is not None
                and set(data["method_id"].astype(str)) == SOURCE_ROUTE_SET
                and set(data["comparison_method_id"].astype(str)) == SOURCE_ROUTE_SET
                and meta.get("figure_role") == "appendix_source_route_mechanism_diagnostic"
            )
            _add(rows, "pairwise_heatmap_figure_excludes_arrival_anchor", source_only, "figure data/metadata exclude arrival anchor and EM", meta if data is None else sorted(set(data["method_id"].astype(str))))
        if figure_id == "fig_exp2_attribution_sensitivity":
            _add(rows, "arrival_anchor_displayed_as_diagnostic", bool(data_ok and data is not None and "Arrival-bin anchor (diagnostic)" in set(data["method_display_name"].astype(str))), "arrival anchor display name is diagnostic", [] if data is None else sorted(set(data["method_display_name"].astype(str))))
            if data_ok and data is not None:
                panel_b = data[data["panel_id"].eq("panel_b")].copy()
                horizontal_ok = (
                    len(panel_b) == len(figure_routes)
                    and set(panel_b["x_id"].astype(str)) == {ARRIVAL_TV}
                    and set(panel_b["metric_id"].astype(str)) == {ARRIVAL_TV}
                    and set(panel_b["method_id"].astype(str)) == set(figure_routes)
                    and "method_display_name" in panel_b.columns
                )
            else:
                panel_b = pd.DataFrame()
                horizontal_ok = False
            _add(rows, "main_figure_uses_horizontal_point_range", horizontal_ok, "panel B encodes allocation TV on x and methods on y", [] if data is None else panel_b[["method_id", "x_id", "metric_id"]].to_dict(orient="records"))
            panel_titles = meta.get("panel_titles", {})
            title_ok = (
                panel_titles == {
                    "panel_a": "(a) Delay composition",
                    "panel_b": "(b) Allocation and ranking displacement",
                }
                and float(meta.get("panel_title_font_size", 999.0)) <= 9.0
                and "subplots_adjust" in str(meta.get("panel_title_overlap_check", ""))
            )
            _add(rows, "main_figure_panel_titles_do_not_overlap", title_ok, "short panel titles, <=9pt font, reserved top space", {"panel_titles": panel_titles, "font_size": meta.get("panel_title_font_size"), "layout": meta.get("panel_title_overlap_check")})
            annotations = meta.get("panel_b_annotation_positions", [])
            annotation_ok = bool(annotations) and all(
                float(item.get("x_annotation", 0.0)) <= float(item.get("x_axis_max", 0.0)) - float(item.get("right_margin", 0.0))
                and float(item.get("x_annotation", 0.0)) >= float(item.get("x_ci_upper", 0.0))
                for item in annotations
            )
            _add(rows, "main_figure_annotations_within_axes", annotation_ok, "Top-10 annotations use bounded x positions inside axes", annotations)
            expected_caption = (
                "Panel A reports the delay composition within the eligible decision-cell cohort under the 30-day "
                "candidate window, not the full Criteo-log delay distribution. Panel B reports logged "
                "credit-allocation TV distance and Top-10 decision-cell overlap relative to the constructed "
                "arrival-bin anchor."
            )
            _add(rows, "main_figure_caption_template_updated", meta.get("caption_template") == expected_caption, "caption records full cohort and anchor interpretation", meta.get("caption_template", ""))
            offsets = meta.get("panel_b_annotation_positions", {})
            if data_ok and data is not None:
                min_distance = min(
                    (
                        abs(float(a["x_annotation"]) - float(b["x_annotation"])) + abs(index - other_index)
                        for index, a in enumerate(offsets)
                        for other_index, b in enumerate(offsets)
                        if other_index > index
                    ),
                    default=1.0,
                )
                callout_ok = bool(offsets) and min_distance >= 1.0
            else:
                min_distance = float("nan")
                callout_ok = False
            _add(rows, "main_figure_callouts_do_not_overlap", callout_ok, "configured callout positions create separated label positions", {"positions": offsets, "min_distance": min_distance})

    if summary_ok and summary is not None:
        main_data_ok, main_data, main_data_detail = _read_csv(root / "figures" / "data" / "fig_exp2_attribution_sensitivity_data.csv")
        if main_data_ok and main_data is not None:
            panel_b = main_data[main_data["panel_id"].eq("panel_b")]
            route_ok = set(panel_b["method_id"].astype(str)) == set(figure_routes)
            metric_ok = set(panel_b["x_id"].astype(str)) == {ARRIVAL_TV}
            _add(rows, "main_figure_metric_contract", route_ok and metric_ok, "main figure uses allocation TV x top-10 overlap for configured non-EM routes", {"routes": sorted(set(panel_b["method_id"].astype(str))), "x_id": sorted(set(panel_b["x_id"].astype(str)))})
        else:
            _add(rows, "main_figure_metric_contract", False, "main figure panel B data", main_data_detail)

    for table_id in TABLES:
        csv_path = out_dir(cfg, "tables") / f"{table_id}.csv"
        tex_path = out_dir(cfg, "tables") / f"{table_id}.tex"
        ok, _, detail = _read_csv(csv_path)
        md_path = out_dir(cfg, "tables") / f"{table_id}.md"
        _add(rows, f"table_{table_id}", bool(ok and tex_path.exists() and tex_path.stat().st_size > 0 and md_path.exists() and md_path.stat().st_size > 0), "nonempty CSV + MD + TeX", detail)

    formal_table_ids = [
        "tbl_app_exp2_source_linked_audit",
        "tbl_app_exp2_top_k_sensitivity",
        "tbl_app_exp2_candidate_window_sensitivity",
        "tbl_app_exp2_em_assignment_diagnostic",
    ]
    triplet_ok = all(
        all((out_dir(cfg, "tables") / f"{table_id}.{suffix}").exists() and (out_dir(cfg, "tables") / f"{table_id}.{suffix}").stat().st_size > 0 for suffix in ("csv", "md", "tex"))
        for table_id in formal_table_ids
    )
    _add(rows, "csv_md_tex_table_triplets_exist", triplet_ok, "formal appendix tables have CSV, Markdown, and TeX", formal_table_ids)

    source_table_ok, source_table, source_table_detail = _read_csv(out_dir(cfg, "tables") / "tbl_app_exp2_source_linked_audit.csv")
    if source_table_ok and source_table is not None:
        required_source_cols = {
            "candidate_decision_cell_count_p90",
            "attribution_nondiscriminative",
            "interpretation_note",
        }
        p90 = pd.to_numeric(source_table.get("candidate_decision_cell_count_p90"), errors="coerce")
        flag = source_table.get("attribution_nondiscriminative")
        note = source_table.get("interpretation_note")
        flag_bool = flag.astype(str).str.casefold().isin({"true", "1"}) if flag is not None else pd.Series([], dtype=bool)
        source_flag_ok = (
            required_source_cols.issubset(source_table.columns)
            and p90.notna().all()
            and ((p90 <= 1.0) == flag_bool).all()
            and note.astype(str).str.len().gt(20).all()
        )
        _add(rows, "source_linked_audit_has_nondiscriminative_flag", source_flag_ok, "source-linked audit table includes p90, nondiscriminative flag, and note", source_table_detail)
    else:
        _add(rows, "source_linked_audit_has_nondiscriminative_flag", False, "source-linked audit table", source_table_detail)

    table_only_ids = [
        "source_linked_audit",
        "top_k_sensitivity",
        "candidate_window_sensitivity",
        "em_assignment_diagnostic",
    ]
    for token in table_only_ids:
        table_exists = any((out_dir(cfg, "tables") / f"tbl_app_exp2_{token}.{suffix}").exists() for suffix in ("csv", "md", "tex"))
        figure_exists = any((root / "figures" / sub / f"fig_app_exp2_{token}.{suffix}").exists() for sub, suffix in (("pdf", "pdf"), ("png", "png")))
        _add(rows, f"{token}_is_table_only", table_exists and not figure_exists, "appendix diagnostic table exists and no formal figure exists", {"table_exists": table_exists, "figure_exists": figure_exists})
        if token == "em_assignment_diagnostic":
            _add(rows, "em_diagnostic_is_table_only", table_exists and not figure_exists, "EM diagnostic table exists and no formal figure exists", {"table_exists": table_exists, "figure_exists": figure_exists})

    obsolete_figure_tokens = [
        "fig_exp2_main_replay",
        "fig_exp2_delay_coupling_control",
        "fig_exp2_label_availability",
        "fig_app_exp2_source_linked_audit",
        "fig_app_exp2_top_k_sensitivity",
        "fig_app_exp2_candidate_window_sensitivity",
        "fig_app_exp2_em_assignment_diagnostic",
    ]
    stale = [path.name for path in root.rglob("*") if path.is_file() and any(token in path.name for token in obsolete_figure_tokens)]
    _add(rows, "no_deprecated_or_redundant_figures", not stale, "no replay or redundant appendix figures", stale)
    latex_docs = []
    for path in [Path("docs") / "latex_interface_experiments.md", Path("README.md"), Path("output_manifest.md")]:
        if path.exists():
            latex_docs.append(path.read_text(encoding="utf-8"))
    formal_text = "\n".join(latex_docs)
    _add(rows, "no_old_figure_ids_in_formal_latex_interface", not any(token in formal_text for token in obsolete_figure_tokens), "formal interface excludes old appendix figure ids", obsolete_figure_tokens)

    doc_paths = [
        Path("docs") / "metric_specification.md",
        Path("docs") / "output_contract.md",
        Path("docs") / "latex_interface_experiments.md",
        Path("docs") / "experiment_refactor_completion_report.md",
    ]
    required_doc_text = (
        "Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity."
    )
    docs_ok = True
    doc_observed = {}
    for path in doc_paths:
        exists = path.exists()
        text = path.read_text(encoding="utf-8") if exists else ""
        doc_observed[str(path)] = {"exists": exists, "has_required_text": required_doc_text in text}
        docs_ok = docs_ok and exists and required_doc_text in text
    _add(rows, "docs_present_and_updated", docs_ok, "required docs exist and state Exp2 interpretation boundary", doc_observed)

    regression_ok = (
        figure_table_regression.get("same_file_set") is True
        and figure_table_regression.get("same_sha256_for_every_core_file") is True
        and figure_table_regression.get("figure_table_repair_regression_passed") is True
    )
    _add(rows, "figure_table_repair_regression", regression_ok, "protected core outputs have identical before/after SHA256", figure_table_regression)

    result = pd.DataFrame([row.__dict__ for row in rows])
    write_csv(result, out_dir(cfg, "checks") / "exp2_self_check_results.csv")
    report = ["# Experiment 2 semantic self-check", "", f"Mode: {args.mode}", f"Failures: {(result['status'] == 'FAIL').sum()}", ""]
    report.extend(f"- [{row.status}] {row.check_id}: {row.observed}" for row in result.itertuples())
    (out_dir(cfg, "checks") / "exp2_self_check_report.md").write_text("\n".join(report), encoding="utf-8")
    make_output_manifest(cfg)
    failures = result[result["status"].eq("FAIL")]
    if not failures.empty:
        _mark_figure_bundles_failed(root, f"{len(failures)} semantic self-check failure(s)")
    print(f"[self_check] mode={args.mode}; checks={len(result)}; failures={len(failures)}", flush=True)
    raise SystemExit(0 if failures.empty else 1)


if __name__ == "__main__":
    main()
