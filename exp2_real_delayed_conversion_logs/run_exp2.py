from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from attribution_engine import build_assignments, route_specification_table
from src.common import ensure_output_dirs, load_config, make_output_manifest, normalise_conversion_identifier, normalise_uid_identifier, out_dir, save_run_metadata, write_csv


def _validate_uid_contract(conversions: pd.DataFrame, candidates: pd.DataFrame, cohort_name: str) -> None:
    conversion_frame = conversions[["conversion_id", "uid"]].copy()
    conversion_frame["conversion_id"] = normalise_conversion_identifier(conversion_frame["conversion_id"])
    conversion_frame["uid"] = normalise_uid_identifier(conversion_frame["uid"])
    bad = conversion_frame["conversion_id"].isna() | conversion_frame["uid"].isna()
    if bad.any():
        raise RuntimeError(f"{cohort_name}: {int(bad.sum())} conversion rows have a missing conversion_id or UID.")
    uid_counts = conversion_frame.groupby("conversion_id", sort=False)["uid"].nunique(dropna=True)
    if uid_counts.ne(1).any():
        raise RuntimeError(f"{cohort_name}: conversion IDs with non-unique UIDs: {uid_counts[uid_counts.ne(1)].index[:5].tolist()}.")
    expected = conversion_frame.drop_duplicates("conversion_id").set_index("conversion_id")["uid"].astype(str)
    frame = candidates[candidates["conversion_id"].astype(str).isin(set(expected.index.astype(str)))].copy()
    frame["conversion_id"] = normalise_conversion_identifier(frame["conversion_id"])
    frame["uid"] = normalise_uid_identifier(frame["uid"])
    if frame["uid"].isna().any():
        raise RuntimeError(f"{cohort_name}: candidate rows with missing UID reached route assignment.")
    mismatch = frame["uid"].astype(str).ne(frame["conversion_id"].astype(str).map(expected))
    if mismatch.any():
        raise RuntimeError(f"{cohort_name}: candidate UID mismatch; examples={frame.loc[mismatch, ['conversion_id','uid']].head(5).to_dict(orient='records')}")


def _candidate_summary(conversions: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for cohort_id, mask in [
        (str(cfg["subsets"]["main_cohort_id"]), conversions["main_cohort_eligible"].eq(1)),
        (str(cfg["subsets"]["source_linked_audit_cohort_id"]), conversions["source_linked_audit_eligible"].eq(1)),
    ]:
        frame = conversions.loc[mask].copy()
        if frame.empty:
            raise RuntimeError(f"Cohort is empty: {cohort_id}")
        rows.append(
            {
                "cohort_id": cohort_id,
                "n_conversion_events": int(frame["conversion_id"].nunique()),
                "n_users": int(normalise_uid_identifier(frame["uid"]).nunique(dropna=True)),
                "candidate_source_event_count_median": float(frame["n_candidate_source_rows"].median()),
                "candidate_source_event_count_p90": float(frame["n_candidate_source_rows"].quantile(0.90)),
                "candidate_decision_cell_count_median": float(frame["n_candidate_decision_cells"].median()),
                "candidate_decision_cell_count_p90": float(frame["n_candidate_decision_cells"].quantile(0.90)),
                "candidate_campaign_count_median": float(frame["n_candidate_campaigns"].median()),
                "ambiguous_decision_cell_rate": float(frame["n_candidate_decision_cells"].gt(1).mean()),
                "ambiguous_campaign_rate": float(frame["n_candidate_campaigns"].gt(1).mean()),
                "arrival_bin_anchor_available_rate": float(pd.to_numeric(frame["arrival_time_action_id"], errors="coerce").notna().mean()),
                "unique_labelled_rate": float(frame["unique_labelled_conversion_candidates_flag"].eq(1).mean()),
            }
        )
    return pd.DataFrame(rows)


def _route_assignment_summary(assignments: pd.DataFrame) -> pd.DataFrame:
    return assignments.groupby(
        ["cohort_id", "route", "method_display_name", "information_interface", "reference_role", "diagnostic_only", "deployable"], as_index=False
    ).agg(
        n_assignment_rows=("conversion_id", "size"),
        n_conversion_events=("conversion_id", "nunique"),
        assigned_conversion_mass=("weight", "sum"),
        mean_assignment_weight=("weight", "mean"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source-time decision-cell attribution assignments for Experiment 2.")
    parser.add_argument("--config", default="config_exp2.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    processed, summaries = out_dir(cfg, "processed"), out_dir(cfg, "summaries")
    required = [
        processed / "exp2_candidate_sources.csv",
        processed / "exp2_conversion_arrivals.csv",
        processed / "exp2_action_exposure_cost.csv",
    ]
    if not all(path.exists() and path.stat().st_size > 0 for path in required):
        raise FileNotFoundError("Run construct_timeline.py before run_exp2.py.")
    candidates = pd.read_csv(required[0])
    conversions = pd.read_csv(required[1])
    action_exposure = pd.read_csv(required[2])
    main_id = str(cfg["subsets"]["main_cohort_id"])
    audit_id = str(cfg["subsets"]["source_linked_audit_cohort_id"])
    main_conversions = conversions[conversions["main_cohort_eligible"].eq(1)].copy()
    audit_conversions = conversions[conversions["source_linked_audit_eligible"].eq(1)].copy()
    if main_conversions.empty or audit_conversions.empty:
        raise RuntimeError("Main or source-linked audit cohort is empty after eligibility filtering.")
    _validate_uid_contract(main_conversions, candidates, "main cohort")
    _validate_uid_contract(audit_conversions, candidates, "source-linked audit cohort")

    main_routes = list(map(str, cfg["attribution_routes"]["main"]))
    appendix_routes = list(map(str, cfg["attribution_routes"]["appendix"]))
    main_result = build_assignments(candidates, main_conversions, action_exposure, cfg, main_id, float(cfg["candidate_set"]["window_days_main"]), main_routes + appendix_routes)
    audit_result = build_assignments(candidates, audit_conversions, action_exposure, cfg, audit_id, float(cfg["candidate_set"]["window_days_main"]), main_routes + appendix_routes + [str(cfg["attribution_routes"]["audit_reference"])])
    assignments = pd.concat([main_result.assignments, audit_result.assignments], ignore_index=True)
    write_csv(assignments, processed / "exp2_route_assignments.csv")
    write_csv(route_specification_table(), processed / "exp2_attribution_route_specification.csv")
    if not main_result.em_diagnostic.empty:
        write_csv(main_result.em_diagnostic.assign(cohort_id=main_id), processed / "exp2_em_action_diagnostic.csv")

    write_csv(_candidate_summary(conversions, cfg), summaries / "exp2_candidate_set_summary.csv")
    write_csv(_route_assignment_summary(assignments), summaries / "exp2_route_assignment_summary.csv")
    save_run_metadata(
        cfg,
        "route_assignment_success",
        {
            "n_main_conversion_events": int(main_conversions["conversion_id"].nunique()),
            "n_audit_conversion_events": int(audit_conversions["conversion_id"].nunique()),
            "n_route_assignment_rows": int(len(assignments)),
            "action_unit": cfg["action"]["action_unit"],
            "main_routes": main_routes,
        },
    )
    make_output_manifest(cfg)
    print("[run_exp2] done", flush=True)


if __name__ == "__main__":
    main()
