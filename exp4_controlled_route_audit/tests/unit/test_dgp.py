from __future__ import annotations

import numpy as np

from exp4.configuration.parameters import MODULE_B, SHARED_DGP
from exp4.simulation.action_space import construct_action_centers
from exp4.simulation.trajectory import generate_structural_trajectory


def test_action_centers_and_structural_contract() -> None:
    centers = construct_action_centers(SHARED_DGP.num_actions)
    trajectory = generate_structural_trajectory(
        "unit_dgp", 0, MODULE_B.horizon, MODULE_B.warmup
    )
    assert centers.shape == (10, 3)
    assert trajectory.structural_loss_map.shape == (MODULE_B.horizon, 10)
    assert np.all((trajectory.structural_loss_map >= 0.0) & (trajectory.structural_loss_map <= 1.0))
    assert trajectory.clock_horizon == MODULE_B.horizon + SHARED_DGP.maximum_candidate_delay
    assert np.isclose(trajectory.mean_delay, SHARED_DGP.target_mean_delay)
    assert int(np.max(trajectory.arrival_clocks)) < trajectory.clock_horizon


def test_stream_reproducibility_and_source_signature_semantics() -> None:
    first = generate_structural_trajectory("unit_dgp", 7, 240, 20)
    second = generate_structural_trajectory("unit_dgp", 7, 240, 20)
    different_module = generate_structural_trajectory("unit_dgp_other", 7, 240, 20)
    assert first.trajectory_hash == second.trajectory_hash
    assert first.trajectory_hash != different_module.trajectory_hash
    assert np.array_equal(first.observation_proxy.source_proxy, first.structural_states)
    signature = first.observation_proxy.arrival_signature(0.25)
    assert signature.shape == first.structural_states.shape
    assert not np.array_equal(signature, first.clock_states[: first.decision_horizon] + 0.25)
