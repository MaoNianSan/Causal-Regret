from __future__ import annotations

import pandas as pd
import pytest

from contracts import ScientificInvariantError
from exp2_core.cohort_stages import (
    COHORT_FILTER_STAGES,
    COHORT_STAGE_SPEC,
    assign_cohort_stage_outcomes,
    build_cohort_flow,
    build_exclusion_summary,
    validate_cohort_flow_reconciliation,
)


def test_primary_cohort_contract(experiment_objects):
    cohort = experiment_objects["cohort"]
    retained = cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"]]
    assert not retained.empty
    assert retained["user_id"].notna().all()
    assert retained["candidate_campaign_count"].eq(1).all()
    assert retained["arrival_anchor_cell_count"].eq(1).all()
    assert retained["is_attribution_ambiguous"].any()
    assert len(cohort.decision_cell_universe) > 50


def test_cohort_stage_spec_drives_flow_reasons_summary_and_retained_mask():
    manifest = pd.DataFrame(
        {
            "journey_id": ["retained", "lookback", "uid", "campaign", "source", "anchor", "arrival", "multi"],
            "has_complete_lookback": [True, False, True, True, True, True, True, False],
            "has_unique_uid": [True, True, False, True, True, True, True, False],
            "has_single_campaign": [True, True, True, False, True, True, True, True],
            "has_source_support": [True, True, True, True, False, True, True, True],
            "has_unique_arrival_anchor": [True, True, True, True, True, False, True, True],
            "has_arrival_support": [True, True, True, True, True, True, False, True],
        }
    )
    resolved = assign_cohort_stage_outcomes(manifest)
    flow = build_cohort_flow(resolved, len(resolved))
    summary = build_exclusion_summary(resolved)

    assert [stage.execution_order for stage in COHORT_STAGE_SPEC] == list(
        range(len(COHORT_STAGE_SPEC))
    )
    assert flow["stage"].tolist() == [stage.stage_id for stage in COHORT_STAGE_SPEC]
    assert resolved.set_index("journey_id").loc["multi", "primary_exclusion_reason"] == "incomplete_lookback"
    assert resolved.set_index("journey_id").loc["multi", "all_exclusion_reasons"] == (
        "incomplete_lookback|invalid_or_cross_user_id"
    )
    expected_retained = manifest[
        [stage.predicate_column for stage in COHORT_FILTER_STAGES]
    ].all(axis=1)
    assert resolved["is_primary_eligible"].equals(expected_retained)
    assert summary["journey_count"].sum() == len(resolved)
    assert validate_cohort_flow_reconciliation(resolved, flow)["status"] == "PASS"


def test_temporal_filtering_is_upstream_not_a_fake_cohort_stage(experiment_objects):
    cohort = experiment_objects["cohort"]
    assert "is_temporally_valid" not in cohort.journey_manifest.columns
    stages = cohort.cohort_flow["stage"].tolist()
    assert stages[0] == "candidate_journeys_after_temporal_filters"
    assert "temporally_valid_journeys" not in stages


def test_cohort_reconciliation_rejects_count_drift(experiment_objects):
    cohort = experiment_objects["cohort"]
    broken = cohort.cohort_flow.copy()
    broken.loc[broken.index[-1], "journey_count"] -= 1
    with pytest.raises(ScientificInvariantError):
        validate_cohort_flow_reconciliation(cohort.journey_manifest, broken)
