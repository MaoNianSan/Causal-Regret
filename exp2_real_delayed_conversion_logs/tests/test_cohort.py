from __future__ import annotations


def test_primary_cohort_contract(experiment_objects):
    cohort = experiment_objects["cohort"]
    retained = cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"]]
    assert not retained.empty
    assert retained["user_id"].notna().all()
    assert retained["candidate_campaign_count"].eq(1).all()
    assert retained["arrival_anchor_cell_count"].eq(1).all()
    assert retained["is_attribution_ambiguous"].any()
    assert len(cohort.decision_cell_universe) > 50
