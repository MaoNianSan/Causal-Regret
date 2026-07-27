from __future__ import annotations

import numpy as np

from contracts import PRIMARY_ROUTE_ORDER


def test_primary_routes_share_cohort_and_conserve_credit(experiment_objects):
    assignments = experiment_objects["routes"].assignments
    primary = assignments.loc[assignments["route_id"].isin(PRIMARY_ROUTE_ORDER)]
    journey_sets = {
        route: frozenset(primary.loc[primary["route_id"].eq(route), "journey_id"])
        for route in PRIMARY_ROUTE_ORDER
    }
    assert len(set(journey_sets.values())) == 1
    sums = primary.groupby(["route_id", "journey_id"])["credit_weight"].sum()
    assert np.allclose(sums.to_numpy(), 1.0, atol=1e-10, rtol=0.0)


def test_time_decay_is_cell_level(experiment_objects):
    assignments = experiment_objects["routes"].assignments
    decay = assignments.loc[assignments["route_id"].eq("time_decay_credit")]
    assert not decay.duplicated(["journey_id", "decision_cell_id"]).any()
