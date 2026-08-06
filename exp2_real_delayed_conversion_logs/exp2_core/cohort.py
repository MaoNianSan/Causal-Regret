from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from contracts import DataContractError, ScientificInvariantError

from .cohort_stages import (
    assign_cohort_stage_outcomes,
    build_cohort_flow,
    validate_cohort_flow_reconciliation,
)


@dataclass(frozen=True)
class CohortBuildResult:
    journey_manifest: pd.DataFrame
    eligible_candidates: pd.DataFrame
    decision_cell_universe: pd.DataFrame
    cohort_summary: pd.DataFrame
    audit: dict[str, Any]
    cohort_flow: pd.DataFrame | None = None


def _first_non_null(series: pd.Series) -> object:
    values = series.dropna()
    return values.iloc[0] if not values.empty else pd.NA


def _ambiguity_stratum(candidate_cell_count: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [candidate_cell_count.eq(1), candidate_cell_count.eq(2)],
            ["candidate_cells_1", "candidate_cells_2"],
            default="candidate_cells_3plus",
        ),
        index=candidate_cell_count.index,
        dtype="string",
    )


def build_primary_cohort(
    candidates: pd.DataFrame,
    impression_counts: pd.DataFrame,
    config: dict[str, Any],
) -> CohortBuildResult:
    analysis_window_days = float(
        config["cohort"].get(
            "analysis_window_days", config["cohort"].get("primary_candidate_window_days", 7.0)
        )
    )
    minimum_impressions = int(config["decision_cell"]["minimum_impressions"])
    minimum_eligible_cells = int(config["decision_cell"]["minimum_eligible_cells"])

    cells = impression_counts.copy()
    cells["is_support_eligible"] = cells["eligible_impression_count"].ge(
        minimum_impressions
    )
    eligible_cells = cells.loc[cells["is_support_eligible"]].copy()
    if len(eligible_cells) < minimum_eligible_cells:
        raise DataContractError(
            "Insufficient support-eligible decision cells: "
            f"observed={len(eligible_cells)}, required={minimum_eligible_cells}."
        )
    eligible_cell_ids = set(eligible_cells["decision_cell_id"].astype(str))

    frame = candidates.loc[
        pd.to_numeric(candidates["source_lag_days"], errors="coerce").le(analysis_window_days)
    ].copy()
    if frame.empty:
        raise DataContractError(
            f"No candidate events remain within the {analysis_window_days:g}-day window."
        )
    observed_start = pd.to_datetime(
        frame["observed_exposure_start_utc"], utc=True, errors="coerce"
    ).dropna()
    if not observed_start.empty:
        frame["has_complete_lookback"] = (
            pd.to_datetime(frame["conversion_timestamp_utc"], utc=True)
            - pd.to_timedelta(analysis_window_days, unit="D")
        ).ge(observed_start.iloc[0])
    frame["is_source_cell_support_eligible"] = frame["decision_cell_id"].astype(str).isin(
        eligible_cell_ids
    )
    frame["is_arrival_cell_support_eligible"] = frame["arrival_anchor_cell_id"].astype(
        str
    ).isin(eligible_cell_ids)

    grouped_all = frame.groupby("journey_id", sort=False, observed=True)
    manifest = pd.DataFrame(
        {
            "journey_id": grouped_all.size().index.astype("string"),
            "candidate_event_count_raw": grouped_all.size().to_numpy(dtype=np.int64),
            "user_id": grouped_all["user_id"].agg(_first_non_null).astype("string").to_numpy(),
            "conversion_id": grouped_all["conversion_id"]
            .agg(_first_non_null)
            .astype("string")
            .to_numpy(),
            "conversion_timestamp_utc": grouped_all["conversion_timestamp_utc"]
            .agg(_first_non_null)
            .to_numpy(),
            "nonmissing_user_count": grouped_all["user_id"].nunique(dropna=True).to_numpy(),
            "candidate_campaign_count_raw": grouped_all["campaign_id"]
            .nunique(dropna=True)
            .to_numpy(),
            "has_complete_lookback": grouped_all["has_complete_lookback"]
            .all()
            .to_numpy(),
            "has_support_eligible_source_cell": grouped_all[
                "is_source_cell_support_eligible"
            ]
            .any()
            .to_numpy(),
            "has_support_eligible_arrival_cell": grouped_all[
                "is_arrival_cell_support_eligible"
            ]
            .all()
            .to_numpy(),
        }
    )

    support_candidates = frame.loc[frame["is_source_cell_support_eligible"]].copy()
    support_grouped = support_candidates.groupby("journey_id", sort=False, observed=True)
    support_summary = pd.DataFrame(
        {
            "journey_id": support_grouped.size().index.astype("string"),
            "candidate_event_count": support_grouped.size().to_numpy(dtype=np.int64),
            "candidate_cell_count": support_grouped["decision_cell_id"]
            .nunique(dropna=True)
            .to_numpy(dtype=np.int64),
            "candidate_campaign_count": support_grouped["campaign_id"]
            .nunique(dropna=True)
            .to_numpy(dtype=np.int64),
            "arrival_anchor_cell_count": support_grouped["arrival_anchor_cell_id"]
            .nunique(dropna=True)
            .to_numpy(dtype=np.int64),
            "arrival_anchor_cell_id": support_grouped["arrival_anchor_cell_id"]
            .agg(_first_non_null)
            .astype("string")
            .to_numpy(),
        }
    )
    manifest = manifest.merge(support_summary, on="journey_id", how="left", validate="one_to_one")
    for column in (
        "candidate_event_count",
        "candidate_cell_count",
        "candidate_campaign_count",
        "arrival_anchor_cell_count",
    ):
        manifest[column] = manifest[column].fillna(0).astype(np.int64)

    manifest["has_unique_uid"] = manifest["nonmissing_user_count"].eq(1)
    manifest["has_single_campaign"] = manifest["candidate_campaign_count"].eq(1)
    manifest["has_source_support"] = manifest["has_support_eligible_source_cell"]
    manifest["has_unique_arrival_anchor"] = manifest["arrival_anchor_cell_count"].eq(1)
    manifest["has_arrival_support"] = manifest["has_support_eligible_arrival_cell"]
    manifest["is_attribution_ambiguous"] = manifest["candidate_cell_count"].ge(2)
    manifest["is_attribution_degenerate"] = manifest["candidate_cell_count"].eq(1)
    manifest["ambiguity_stratum"] = _ambiguity_stratum(manifest["candidate_cell_count"])

    manifest = assign_cohort_stage_outcomes(manifest)

    primary_journey_ids = set(
        manifest.loc[manifest["is_primary_eligible"], "journey_id"].astype(str)
    )
    eligible_candidates = support_candidates.loc[
        support_candidates["journey_id"].astype(str).isin(primary_journey_ids)
    ].copy()
    if eligible_candidates.empty:
        raise DataContractError("No journeys remain in the primary common cohort.")

    retained_manifest = manifest.loc[manifest["is_primary_eligible"]].copy()
    if retained_manifest["user_id"].isna().any():
        raise ScientificInvariantError("Retained journeys contain missing user IDs.")
    if retained_manifest["candidate_campaign_count"].ne(1).any():
        raise ScientificInvariantError("Multi-campaign journey entered the primary cohort.")
    if retained_manifest["arrival_anchor_cell_count"].ne(1).any():
        raise ScientificInvariantError("A retained journey has a nonunique arrival anchor.")

    journey_counts = (
        eligible_candidates[["journey_id", "decision_cell_id"]]
        .drop_duplicates()
        .groupby("decision_cell_id", sort=False, observed=True)
        .size()
        .rename("eligible_journey_count")
        .reset_index()
    )
    eligible_cells = eligible_cells.merge(
        journey_counts, on="decision_cell_id", how="left", validate="one_to_one"
    )
    eligible_cells["eligible_journey_count"] = (
        eligible_cells["eligible_journey_count"].fillna(0).astype(np.int64)
    )
    eligible_cells = eligible_cells.sort_values(
        ["campaign_id", "source_date_utc", "decision_cell_id"], kind="stable"
    ).reset_index(drop=True)

    retained_count = int(retained_manifest.shape[0])
    retained_user_count = int(retained_manifest["user_id"].nunique())
    ambiguous_count = int(retained_manifest["is_attribution_ambiguous"].sum())
    strata_counts = retained_manifest["ambiguity_stratum"].value_counts()

    summary_values: dict[str, object] = {
        "retained_journey_count": retained_count,
        "retained_user_count": retained_user_count,
        "eligible_campaign_count": int(eligible_cells["campaign_id"].nunique()),
        "eligible_decision_cell_count": int(len(eligible_cells)),
        "candidate_cells_1_count": int(strata_counts.get("candidate_cells_1", 0)),
        "candidate_cells_2_count": int(strata_counts.get("candidate_cells_2", 0)),
        "candidate_cells_3plus_count": int(strata_counts.get("candidate_cells_3plus", 0)),
        "ambiguous_journey_count": ambiguous_count,
        "ambiguous_journey_rate": ambiguous_count / retained_count,
        "candidate_cell_count_median": float(
            retained_manifest["candidate_cell_count"].median()
        ),
        "candidate_cell_count_p90": float(
            retained_manifest["candidate_cell_count"].quantile(0.90)
        ),
        "minimum_impressions_per_cell": minimum_impressions,
    }
    for reason, count in manifest["primary_exclusion_reason"].value_counts().items():
        if reason != "retained":
            summary_values[f"excluded_{reason}_count"] = int(count)

    cohort_summary = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in summary_values.items()]
    )
    audit = {
        "all_journey_count": int(len(manifest)),
        "retained_journey_count": retained_count,
        "retained_user_count": retained_user_count,
        "ambiguous_journey_count": ambiguous_count,
        "ambiguous_journey_rate": ambiguous_count / retained_count,
        "eligible_cell_count": int(len(eligible_cells)),
        "eligible_campaign_count": int(eligible_cells["campaign_id"].nunique()),
        "exclusion_counts": {
            str(key): int(value)
            for key, value in manifest["primary_exclusion_reason"].value_counts().items()
        },
        "analysis_window_days": analysis_window_days,
    }
    flow = build_cohort_flow(manifest, len(grouped_all))
    reconciliation = validate_cohort_flow_reconciliation(manifest, flow)
    audit["cohort_flow_reconciliation_status"] = reconciliation["status"]
    return CohortBuildResult(
        journey_manifest=manifest.sort_values("journey_id", kind="stable").reset_index(drop=True),
        eligible_candidates=eligible_candidates.sort_values(
            ["journey_id", "event_timestamp_utc", "decision_cell_id", "source_event_id"],
            kind="stable",
        ).reset_index(drop=True),
        decision_cell_universe=eligible_cells,
        cohort_summary=cohort_summary,
        audit=audit,
        cohort_flow=flow,
    )
