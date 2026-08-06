from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from contracts import ScientificInvariantError


@dataclass(frozen=True)
class CohortStageSpec:
    stage_id: str
    display_name: str
    predicate_column: str | None
    exclusion_reason: str | None
    execution_order: int


COHORT_STAGE_SPEC = (
    CohortStageSpec(
        stage_id="candidate_journeys_after_temporal_filters",
        display_name="Candidate journeys after upstream temporal filters",
        predicate_column=None,
        exclusion_reason=None,
        execution_order=0,
    ),
    CohortStageSpec(
        stage_id="complete_lookback_journeys",
        display_name="Complete-lookback journeys",
        predicate_column="has_complete_lookback",
        exclusion_reason="incomplete_lookback",
        execution_order=1,
    ),
    CohortStageSpec(
        stage_id="unique_uid_journeys",
        display_name="Unique-UID journeys",
        predicate_column="has_unique_uid",
        exclusion_reason="invalid_or_cross_user_id",
        execution_order=2,
    ),
    CohortStageSpec(
        stage_id="single_campaign_journeys",
        display_name="Single-campaign journeys",
        predicate_column="has_single_campaign",
        exclusion_reason="multi_campaign_or_missing_campaign",
        execution_order=3,
    ),
    CohortStageSpec(
        stage_id="source_cell_support_eligible_journeys",
        display_name="Source-cell-support-eligible journeys",
        predicate_column="has_source_support",
        exclusion_reason="no_support_eligible_source_cell",
        execution_order=4,
    ),
    CohortStageSpec(
        stage_id="unique_arrival_anchor_journeys",
        display_name="Unique-arrival-anchor journeys",
        predicate_column="has_unique_arrival_anchor",
        exclusion_reason="nonunique_arrival_anchor",
        execution_order=5,
    ),
    CohortStageSpec(
        stage_id="arrival_anchor_support_eligible_journeys",
        display_name="Arrival-anchor-support-eligible journeys",
        predicate_column="has_arrival_support",
        exclusion_reason="arrival_anchor_outside_cell_universe",
        execution_order=6,
    ),
    CohortStageSpec(
        stage_id="final_retained_journeys",
        display_name="Final retained journeys",
        predicate_column=None,
        exclusion_reason=None,
        execution_order=7,
    ),
)

COHORT_FILTER_STAGES = tuple(
    stage for stage in COHORT_STAGE_SPEC if stage.predicate_column is not None
)


def _predicate(manifest: pd.DataFrame, stage: CohortStageSpec) -> pd.Series:
    if stage.predicate_column is None:
        return pd.Series(True, index=manifest.index, dtype=bool)
    return manifest[stage.predicate_column].fillna(False).astype(bool)


def assign_cohort_stage_outcomes(manifest: pd.DataFrame) -> pd.DataFrame:
    output = manifest.copy()
    failure_masks = [~_predicate(output, stage) for stage in COHORT_FILTER_STAGES]
    reasons = [str(stage.exclusion_reason) for stage in COHORT_FILTER_STAGES]
    output["primary_exclusion_reason"] = np.select(
        failure_masks, reasons, default="retained"
    )
    output["all_exclusion_reasons"] = [
        "|".join(
            reason
            for failed, reason in zip(row_failures, reasons)
            if bool(failed)
        )
        or "retained"
        for row_failures in zip(*(mask.to_numpy() for mask in failure_masks))
    ]
    retained = pd.Series(True, index=output.index, dtype=bool)
    for stage in COHORT_FILTER_STAGES:
        retained &= _predicate(output, stage)
    # The legacy adapter is not written by a separate precedence implementation.
    output["exclusion_reason"] = output["primary_exclusion_reason"]
    output["is_primary_eligible"] = retained
    return output


def build_cohort_flow(
    manifest: pd.DataFrame, candidate_journey_count: int
) -> pd.DataFrame:
    previous = float(candidate_journey_count)
    cumulative = pd.Series(True, index=manifest.index, dtype=bool)
    rows: list[dict[str, object]] = []
    for stage in COHORT_STAGE_SPEC:
        if stage.predicate_column is not None:
            cumulative &= _predicate(manifest, stage)
        count = int(cumulative.sum())
        rows.append(
            {
                "stage": stage.stage_id,
                "journey_count": count,
                "retention_from_previous_stage": (
                    count / previous if previous else np.nan
                ),
                "retention_from_candidate_journeys": (
                    count / candidate_journey_count
                    if candidate_journey_count
                    else np.nan
                ),
            }
        )
        previous = float(count)
    return pd.DataFrame(rows)


def build_exclusion_summary(manifest: pd.DataFrame) -> pd.DataFrame:
    counts = manifest["primary_exclusion_reason"].value_counts(dropna=False)
    rows = [
        {
            "primary_exclusion_reason": stage.exclusion_reason,
            "journey_count": int(counts.get(stage.exclusion_reason, 0)),
        }
        for stage in COHORT_FILTER_STAGES
        if int(counts.get(stage.exclusion_reason, 0)) > 0
    ]
    rows.append(
        {
            "primary_exclusion_reason": "retained",
            "journey_count": int(counts.get("retained", 0)),
        }
    )
    return pd.DataFrame(rows)


def validate_cohort_flow_reconciliation(
    manifest: pd.DataFrame, cohort_flow: pd.DataFrame
) -> dict[str, object]:
    expected_stages = [stage.stage_id for stage in COHORT_STAGE_SPEC]
    if cohort_flow["stage"].astype(str).tolist() != expected_stages:
        raise ScientificInvariantError("Cohort flow does not use the frozen stage order.")
    counts = cohort_flow["journey_count"].astype(int).tolist()
    if any(current > previous for previous, current in zip(counts, counts[1:])):
        raise ScientificInvariantError("Cohort retained counts are not monotone nonincreasing.")
    if not counts or counts[0] != len(manifest):
        raise ScientificInvariantError("Cohort flow candidate count does not match the manifest.")

    expected_retained = pd.Series(True, index=manifest.index, dtype=bool)
    for stage in COHORT_FILTER_STAGES:
        expected_retained &= _predicate(manifest, stage)
    observed_retained = manifest["is_primary_eligible"].fillna(False).astype(bool)
    if not expected_retained.equals(observed_retained):
        raise ScientificInvariantError("Final retained mask does not match the cohort stage specification.")
    if counts[-1] != int(observed_retained.sum()):
        raise ScientificInvariantError("Final cohort-flow count does not match the retained mask.")

    flow_counts = dict(zip(cohort_flow["stage"].astype(str), counts))
    previous_count = counts[0]
    for stage in COHORT_FILTER_STAGES:
        current_count = flow_counts[stage.stage_id]
        reason_count = int(
            manifest["primary_exclusion_reason"].eq(stage.exclusion_reason).sum()
        )
        if previous_count - current_count != reason_count:
            raise ScientificInvariantError(
                f"Cohort attrition does not reconcile for stage {stage.stage_id}."
            )
        previous_count = current_count

    excluded_count = int((~observed_retained).sum())
    primary_reason_count = int(
        manifest["primary_exclusion_reason"].isin(
            [stage.exclusion_reason for stage in COHORT_FILTER_STAGES]
        ).sum()
    )
    if primary_reason_count != excluded_count:
        raise ScientificInvariantError(
            "Primary exclusion reasons do not partition excluded journeys."
        )
    summary_total = int(build_exclusion_summary(manifest)["journey_count"].sum())
    if summary_total != len(manifest):
        raise ScientificInvariantError("Exclusion summary does not reconcile to candidate journeys.")
    return {
        "check": "cohort_flow_exclusion_reconciliation",
        "status": "PASS",
        "candidate_journey_count": int(len(manifest)),
        "retained_journey_count": int(observed_retained.sum()),
        "excluded_journey_count": excluded_count,
        "stage_count": len(COHORT_STAGE_SPEC),
    }
