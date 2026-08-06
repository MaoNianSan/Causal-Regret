from __future__ import annotations

import numpy as np

from metrics import allocation_tv, kendall_tau_b, stable_top_k, top_k_overlap


def test_metric_ranges_and_distinct_estimands(experiment_objects):
    metrics = experiment_objects["metrics"]
    pairwise = metrics.source_route_pairwise
    assert pairwise["allocation_tv"].between(0.0, 1.0).all()
    assert pairwise["mean_journey_assignment_tv"].between(0.0, 1.0).all()
    assert pairwise["top_k_overlap"].between(0.0, 1.0).all()
    assert pairwise["kendall_tau_b"].between(-1.0, 1.0).all()
    # The synthetic fixture is designed so cell-allocation TV and mean journey TV
    # are not merely two names for the same statistic.
    assert not np.allclose(
        pairwise["allocation_tv"].to_numpy(),
        pairwise["mean_journey_assignment_tv"].to_numpy(),
    )


def test_allocation_vectors_sum_to_one(experiment_objects):
    allocations = experiment_objects["metrics"].route_allocations
    totals = allocations.groupby("route_id")["allocation_share"].sum()
    assert np.allclose(totals.to_numpy(), 1.0, atol=1e-12, rtol=0.0)


def test_frozen_support_leaves_point_estimates_unchanged(experiment_objects):
    metrics = experiment_objects["metrics"]
    allocations = metrics.route_allocations
    arrival = metrics.arrival_displacement.set_index("route_id")
    pairwise = metrics.source_route_pairwise.set_index(["route_left", "route_right"])
    for state in metrics.kendall_metric_states:
        left = allocations.loc[allocations["route_id"].eq(state.route_left)]
        right = allocations.loc[allocations["route_id"].eq(state.route_right)]
        dynamic_tau, dynamic_support = kendall_tau_b(left, right)
        frozen_tau, frozen_support = kendall_tau_b(
            left, right, support_cell_ids=state.support_cell_ids
        )
        assert dynamic_tau == frozen_tau
        assert dynamic_support == frozen_support
        if state.route_left == "arrival_time_accounting_anchor":
            assert frozen_tau == arrival.loc[state.route_right, "kendall_tau_b_vs_arrival"]
        else:
            assert frozen_tau == pairwise.loc[
                (state.route_left, state.route_right), "kendall_tau_b"
            ]


def test_allocation_tv_and_top_k_are_independent_of_kendall_support(experiment_objects):
    metrics = experiment_objects["metrics"]
    allocations = metrics.route_allocations
    pairwise = metrics.source_route_pairwise.set_index(["route_left", "route_right"])
    top_k = int(experiment_objects["config"]["ranking"]["primary_top_k"])
    for state in metrics.kendall_metric_states:
        if state.route_left == "arrival_time_accounting_anchor":
            continue
        left = allocations.loc[allocations["route_id"].eq(state.route_left)].sort_values(
            "decision_cell_id"
        )
        right = allocations.loc[allocations["route_id"].eq(state.route_right)].sort_values(
            "decision_cell_id"
        )
        row = pairwise.loc[(state.route_left, state.route_right)]
        assert allocation_tv(
            left["allocation_share"].to_numpy(), right["allocation_share"].to_numpy()
        ) == row["allocation_tv"]
        assert top_k_overlap(stable_top_k(left, top_k), stable_top_k(right, top_k), top_k) == row[
            "top_k_overlap"
        ]
