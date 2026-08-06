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


def compare_csv(baseline: Path, candidate: Path, relative: str, keys: list[str]) -> dict[str, Any]:
    left = _normalize_frame(pd.read_csv(baseline / relative))
    right = _normalize_frame(pd.read_csv(candidate / relative))
    result: dict[str, Any] = {
        "columns_equal": list(left.columns) == list(right.columns),
        "row_count_equal": len(left) == len(right),
        "row_order_equal": False,
        "canonical_values_equal": False,
        "baseline_hash": _scientific_hash(left),
        "candidate_hash": _scientific_hash(right),
    }
    if not result["columns_equal"] or not result["row_count_equal"]:
        result["status"] = "FAIL"
        return result
    try:
        assert_frame_equal(left, right, check_dtype=False, check_exact=False, rtol=0.0, atol=1e-12)
        result["row_order_equal"] = True
    except AssertionError as exc:
        result["row_order_error"] = str(exc)[:2000]
    try:
        assert_frame_equal(
            _canonical_sort(left, keys),
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
    equal = left == right
    return {"status": "PASS" if equal else "FAIL", "equal": equal}


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
