from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal


CSV_SPECS = {
    "derived/cohort_flow.csv": ["stage"],
    "derived/exclusion_summary.csv": ["primary_exclusion_reason"],
    "derived/temporal_coverage.csv": ["quantity"],
    "derived/primary_comparisons.csv": ["comparison_group", "route_left", "route_right", "route_id"],
    "derived/ambiguity_mechanism.csv": ["record_type", "ambiguity_stratum", "route_id", "route_left", "route_right"],
    "derived/targeted_robustness.csv": ["targeted_dimension", "targeted_value", "record_type", "route_id", "route_left", "route_right"],
    "derived/route_allocations.csv": ["route_id", "campaign_id", "source_date_utc", "decision_cell_id"],
    "derived/route_assignments.csv": ["route_id", "journey_id", "decision_cell_id"],
    "derived/decision_cell_universe.csv": ["campaign_id", "source_date_utc", "decision_cell_id"],
    "derived/journey_manifest.csv": ["journey_id"],
    "derived/bootstrap_draws.csv": ["replication_id", "record_type", "route_id", "route_left", "route_right", "top_k"],
    "derived/kendall_support.csv": ["route_left", "route_right"],
    "derived/arrival_displacement.csv": ["route_id"],
    "derived/source_route_pairwise.csv": ["route_left", "route_right"],
    "figures/figure_exp2_attribution_sensitivity_source.csv": ["record_type", "comparison_group", "route_left", "route_right"],
    "figures/figure_exp2_ambiguity_mechanism_source.csv": ["record_type", "ambiguity_stratum", "route_left", "route_right", "route_id"],
    "tables/table_exp2_cohort_flow.csv": ["Cohort stage"],
    "tables/table_exp2_primary_results.csv": ["route_id"],
    "tables/table_exp2_pairwise_appendix.csv": ["route_left", "route_right"],
    "tables/table_exp2_robustness_summary.csv": ["dimension", "comparison_group"],
}

ALLOWED_COLUMN_DROPS = {
    "derived/journey_manifest.csv": {"is_temporally_valid"},
}

EXPECTED_COHORT_STAGES = [
    "candidate_journeys_after_temporal_filters",
    "complete_lookback_journeys",
    "unique_uid_journeys",
    "single_campaign_journeys",
    "source_cell_support_eligible_journeys",
    "unique_arrival_anchor_journeys",
    "arrival_anchor_support_eligible_journeys",
    "final_retained_journeys",
]

ALLOWED_EXCLUSION_REASONS = {
    "incomplete_lookback",
    "invalid_or_cross_user_id",
    "multi_campaign_or_missing_campaign",
    "no_support_eligible_source_cell",
    "nonunique_arrival_anchor",
    "arrival_anchor_outside_cell_universe",
    "retained",
}

JSON_FILES = (
    "audit/route_invariants.json",
    "audit/scientific_validation.json",
    "audit/resampling_audit.json",
    "audit/cohort_audit.json",
    "derived/cohort_scope.json",
    "run_manifest.json",
)

VOLATILE_JSON_KEYS = {
    "code_identity",
    "completed_at",
    "config_path",
    "generated_at",
    "input_location",
    "input_modified_time_ns",
    "run_id",
    "source_data_sha256",
    "started_at",
}


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_json(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_JSON_KEYS
        }
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "run_id" in output.columns:
        output["run_id"] = "<RUN_ID>"
    return output


def _scientific_hash(frame: pd.DataFrame) -> str:
    csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _canonical_sort(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    present = [key for key in keys if key in frame.columns]
    if not present:
        return frame.reset_index(drop=True)
    return frame.sort_values(present, kind="stable", na_position="last").reset_index(drop=True)


def _compare_cohort_flow(left: pd.DataFrame, right: pd.DataFrame, relative: str) -> dict[str, Any]:
    stage_column = "Cohort stage" if relative.startswith("tables/") else "stage"
    count_column = "Journey count" if relative.startswith("tables/") else "journey_count"
    columns_equal = list(left.columns) == list(right.columns)
    candidate_stages = right[stage_column].astype(str).tolist() if columns_equal else []
    counts = pd.to_numeric(right[count_column], errors="coerce") if columns_equal else pd.Series(dtype=float)
    baseline_counts = pd.to_numeric(left[count_column], errors="coerce") if columns_equal else pd.Series(dtype=float)
    monotone = bool((counts.diff().dropna() <= 0).all()) if len(counts) else False
    endpoints_equal = bool(
        len(counts)
        and len(baseline_counts)
        and int(counts.iloc[0]) == int(baseline_counts.iloc[0])
        and int(counts.iloc[-1]) == int(baseline_counts.iloc[-1])
    )
    expected_order = candidate_stages == EXPECTED_COHORT_STAGES
    status = columns_equal and monotone and endpoints_equal and expected_order
    return {
        "status": "PASS" if status else "FAIL",
        "columns_equal": columns_equal,
        "row_count_equal": len(left) == len(right),
        "allowed_semantic_change": "cohort_stage_order_and_temporal_stage_cleanup",
        "candidate_stage_order_valid": expected_order,
        "candidate_counts_monotone_nonincreasing": monotone,
        "candidate_and_final_counts_equal": endpoints_equal,
        "baseline_hash": _scientific_hash(left),
        "candidate_hash": _scientific_hash(right),
    }


def _compare_exclusion_summary(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    columns_equal = list(left.columns) == list(right.columns)
    left_counts = left.set_index("primary_exclusion_reason")["journey_count"]
    right_counts = right.set_index("primary_exclusion_reason")["journey_count"]
    reasons_valid = set(right_counts.index.astype(str)).issubset(ALLOWED_EXCLUSION_REASONS)
    totals_equal = int(left_counts.sum()) == int(right_counts.sum())
    retained_equal = int(left_counts.get("retained", 0)) == int(right_counts.get("retained", 0))
    status = columns_equal and reasons_valid and totals_equal and retained_equal
    return {
        "status": "PASS" if status else "FAIL",
        "columns_equal": columns_equal,
        "row_count_equal": len(left) == len(right),
        "allowed_semantic_change": "primary_reason_precedence_from_frozen_stage_order",
        "candidate_reasons_valid": reasons_valid,
        "candidate_total_equal": totals_equal,
        "retained_count_equal": retained_equal,
        "baseline_hash": _scientific_hash(left),
        "candidate_hash": _scientific_hash(right),
    }


def compare_csv(baseline: Path, candidate: Path, relative: str, keys: list[str]) -> dict[str, Any]:
    left = _normalize_frame(pd.read_csv(baseline / relative))
    right = _normalize_frame(pd.read_csv(candidate / relative))
    if relative in {"derived/cohort_flow.csv", "tables/table_exp2_cohort_flow.csv"}:
        return _compare_cohort_flow(left, right, relative)
    if relative == "derived/exclusion_summary.csv":
        return _compare_exclusion_summary(left, right)
    candidate_window_status_valid = True
    if relative == "derived/targeted_robustness.csv":
        left_status = left["analysis_status"].eq("NOT_RUN_IN_FAST") & left[
            "targeted_dimension"
        ].eq("candidate_window_days")
        right_status = right["analysis_status"].eq("NOT_RUN_IN_FAST") & right[
            "targeted_dimension"
        ].eq("candidate_window_days")
        candidate_window_status_valid = bool(
            right_status.sum() == 1
            and right.loc[right_status, "targeted_value"].astype(str).eq("30").all()
        )
        left.loc[left_status, "targeted_value"] = "30"
    allowed_drops = ALLOWED_COLUMN_DROPS.get(relative, set())
    expected_right_columns = [column for column in left.columns if column not in allowed_drops]
    schema_compatible = list(right.columns) == expected_right_columns
    comparable_left = left[expected_right_columns] if schema_compatible else left
    result: dict[str, Any] = {
        "columns_equal": list(left.columns) == list(right.columns),
        "schema_compatible": schema_compatible,
        "allowed_column_drops": sorted(allowed_drops),
        "row_count_equal": len(left) == len(right),
        "row_order_equal": False,
        "canonical_values_equal": False,
        "candidate_window_status_valid": candidate_window_status_valid,
        "baseline_hash": _scientific_hash(left),
        "candidate_hash": _scientific_hash(right),
    }
    if not schema_compatible or not result["row_count_equal"] or not candidate_window_status_valid:
        result["status"] = "FAIL"
        return result
    try:
        assert_frame_equal(comparable_left, right, check_dtype=False, check_exact=False, rtol=0.0, atol=1e-12)
        result["row_order_equal"] = True
    except AssertionError as exc:
        result["row_order_error"] = str(exc)[:2000]
    try:
        assert_frame_equal(
            _canonical_sort(comparable_left, keys),
            _canonical_sort(right, keys),
            check_dtype=False,
            check_exact=False,
            rtol=0.0,
            atol=1e-12,
        )
        result["canonical_values_equal"] = True
    except AssertionError as exc:
        result["canonical_error"] = str(exc)[:2000]
    result["status"] = "PASS" if result["row_order_equal"] and result["canonical_values_equal"] else "FAIL"
    return result


def compare_json(baseline: Path, candidate: Path, relative: str) -> dict[str, Any]:
    left = _normalize_json(json.loads((baseline / relative).read_text(encoding="utf-8")))
    right = _normalize_json(json.loads((candidate / relative).read_text(encoding="utf-8")))
    allowed_change: str | None = None
    allowed_change_valid = True
    if relative == "audit/cohort_audit.json":
        allowed_change = "cohort_flow_reconciliation_status"
        allowed_change_valid = right.pop("cohort_flow_reconciliation_status", None) == "PASS"
    elif relative == "audit/scientific_validation.json":
        allowed_change = "cohort_flow_exclusion_reconciliation_check"
        extra_checks = [
            item
            for item in right.get("checks", [])
            if item.get("check") == "cohort_flow_exclusion_reconciliation"
        ]
        allowed_change_valid = len(extra_checks) == 1 and extra_checks[0].get("status") == "PASS"
        right["checks"] = [
            item
            for item in right.get("checks", [])
            if item.get("check") != "cohort_flow_exclusion_reconciliation"
        ]
    equal = left == right
    status = equal and allowed_change_valid
    return {
        "status": "PASS" if status else "FAIL",
        "equal_after_allowed_changes": equal,
        "allowed_change": allowed_change,
        "allowed_change_valid": allowed_change_valid,
    }


def build_report(baseline: Path, candidate: Path) -> dict[str, Any]:
    missing = [
        relative
        for relative in [*CSV_SPECS, *JSON_FILES]
        if not (baseline / relative).exists() or not (candidate / relative).exists()
    ]
    if missing:
        return {"status": "FAIL", "missing_files": missing}
    csv_results = {
        relative: compare_csv(baseline, candidate, relative, keys)
        for relative, keys in CSV_SPECS.items()
    }
    json_results = {
        relative: compare_json(baseline, candidate, relative)
        for relative in JSON_FILES
    }
    journey_left = pd.read_csv(baseline / "derived/journey_manifest.csv")
    journey_right = pd.read_csv(candidate / "derived/journey_manifest.csv")
    retained_left = journey_left.loc[journey_left["is_primary_eligible"].astype(bool)]
    retained_right = journey_right.loc[journey_right["is_primary_eligible"].astype(bool)]
    retained_journeys_equal = set(retained_left["journey_id"].astype(str)) == set(retained_right["journey_id"].astype(str))
    retained_uids_equal = set(retained_left["user_id"].astype(str)) == set(retained_right["user_id"].astype(str))
    allocations_left = pd.read_csv(baseline / "derived/route_allocations.csv")
    allocations_right = pd.read_csv(candidate / "derived/route_allocations.csv")
    route_totals_equal = np.allclose(
        allocations_left.groupby("route_id", sort=False)["credited_conversion_mass"].sum().to_numpy(dtype=float),
        allocations_right.groupby("route_id", sort=False)["credited_conversion_mass"].sum().to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-12,
    )
    random_draw_equal = csv_results["derived/bootstrap_draws.csv"]["status"] == "PASS"
    all_pass = (
        all(item["status"] == "PASS" for item in csv_results.values())
        and all(item["status"] == "PASS" for item in json_results.values())
        and retained_journeys_equal
        and retained_uids_equal
        and route_totals_equal
        and random_draw_equal
    )
    return {
        "status": "PASS" if all_pass else "FAIL",
        "rtol": 0.0,
        "atol": 1e-12,
        "csv_results": csv_results,
        "json_results": json_results,
        "retained_journey_ids_equal": retained_journeys_equal,
        "retained_uid_sets_equal": retained_uids_equal,
        "route_credit_totals_equal": bool(route_totals_equal),
        "random_draw_equivalence_status": "PASS" if random_draw_equal else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Exp2 Fast artifacts without recomputing scientific logic.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.baseline, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
