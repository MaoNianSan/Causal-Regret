"""Deprecated compatibility exports for `exp4.simulation`."""

from exp4.simulation.action_space import construct_action_centers
from exp4.simulation.structural_loss import compute_structural_loss_map
from exp4.simulation.trajectory import (
    StructuralTrajectory,
    generate_structural_trajectory,
    hash_array,
    hash_json,
    save_trajectory,
)

__all__ = [
    "StructuralTrajectory",
    "construct_action_centers",
    "compute_structural_loss_map",
    "generate_structural_trajectory",
    "hash_array",
    "hash_json",
    "save_trajectory",
]
