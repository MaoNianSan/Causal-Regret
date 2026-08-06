from __future__ import annotations

import pandas as pd

from contracts import SCHEMA_VERSION

from ..cohort import CohortBuildResult, build_primary_cohort
from ..cohort_stages import build_exclusion_summary
from ..raw_data import PreparedRawData, write_frame, write_json
from .context import RunContext, write_csv


def run_cohort_stage(context: RunContext, prepared: PreparedRawData) -> CohortBuildResult:
    cohort = build_primary_cohort(prepared.candidates, prepared.impression_counts, context.config)
    write_csv(cohort.cohort_summary, context.paths.derived / "cohort_summary.csv")
    write_frame(cohort.journey_manifest, context.paths.derived / "journey_manifest", table_format=context.table_format)
    write_frame(
        cohort.decision_cell_universe,
        context.paths.derived / "decision_cell_universe",
        table_format=context.table_format,
    )
    write_csv(
        build_exclusion_summary(cohort.journey_manifest),
        context.paths.derived / "exclusion_summary.csv",
    )
    if cohort.cohort_flow is not None:
        write_csv(cohort.cohort_flow, context.paths.derived / "cohort_flow.csv")
    temporal = pd.DataFrame(
        [
            {"quantity": "observed_exposure_start_utc", "value": prepared.observed_start_utc.isoformat()},
            {"quantity": "observed_exposure_end_utc", "value": prepared.observed_end_utc.isoformat()},
            {"quantity": "candidate_conversion_start_utc", "value": str(prepared.candidates["conversion_timestamp_utc"].min())},
            {"quantity": "candidate_conversion_end_utc", "value": str(prepared.candidates["conversion_timestamp_utc"].max())},
            {"quantity": "retained_conversion_start_utc", "value": str(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "conversion_timestamp_utc"].min())},
            {"quantity": "retained_conversion_end_utc", "value": str(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "conversion_timestamp_utc"].max())},
        ]
    )
    write_csv(temporal, context.paths.derived / "temporal_coverage.csv")
    write_csv(
        prepared.candidates.assign(conversion_date_utc=prepared.candidates["conversion_timestamp_utc"].dt.floor("D"))
        .groupby("conversion_date_utc", dropna=False).size().rename("candidate_count").reset_index(),
        context.paths.derived / "conversion_date_distribution.csv",
    )
    write_csv(
        prepared.candidates.groupby("source_date_utc", dropna=False).size().rename("candidate_count").reset_index(),
        context.paths.derived / "source_date_distribution.csv",
    )
    write_json(cohort.audit, context.paths.audit / "cohort_audit.json")
    write_json(
        {
            "schema_version": SCHEMA_VERSION,
            "analysis_window_days": cohort.audit.get("analysis_window_days", 7),
            "primary_candidate_window_days": context.config["cohort"]["primary_candidate_window_days"],
            "robustness_candidate_window_days": context.config["cohort"].get("robustness_candidate_window_days", []),
            "require_complete_lookback": bool(context.config["cohort"]["require_complete_lookback"]),
            "require_single_campaign_per_journey": bool(context.config["cohort"]["require_single_campaign_per_journey"]),
            "retained_journey_count": int(cohort.journey_manifest["is_primary_eligible"].sum()),
            "retained_uid_count": int(cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "user_id"].nunique()),
            "eligible_cell_count": int(len(cohort.decision_cell_universe)),
        },
        context.paths.derived / "cohort_scope.json",
    )
    retained_count = int(cohort.journey_manifest["is_primary_eligible"].sum())
    retained_users = int(
        cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"], "user_id"].nunique()
    )
    print(f"      Retained journeys: {retained_count:,}")
    print(f"      Retained UIDs: {retained_users:,}")
    print(f"      Eligible cells: {len(cohort.decision_cell_universe):,}")
    print("      Status: PASS")
    return cohort
