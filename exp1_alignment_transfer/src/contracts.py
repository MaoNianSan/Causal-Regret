from __future__ import annotations

"""Central scientific and artifact contracts for Experiment 1."""

from dataclasses import dataclass

from config import DISPLAY_NAMES, EXPERIMENT_ID, MECHANISM_ORDER


STRUCTURAL_FAMILIES = (
    "smooth_bounded_ar1",
    "action_invariant_shift",
    "alternating_block_state",
)
ROUTES = ("arrival_assigned", "source_bound")
FEEDBACK_BINDINGS = ("arrival_clock", "source_round")
ANALYSIS_COMPONENTS = ("route_map_diagnostic", "learner_consequence")
RUN_TIERS = ("fast", "full", "paper")
ANALYSIS_TIERS = ("primary", "targeted", "appendix", "implementation_check")

METRICS = (
    "structural_regret_rate",
    "context_constrained_regret_rate",
    "route_regret_rate",
    "alignment_budget_rate",
    "transfer_bound_rate",
    "transfer_slack_rate",
    "ranking_reversal_rate",
    "margin_preservation_rate",
    "reversal_margin",
    "arrival_minus_source_regret_rate",
    "pairwise_sign_disagreement_rate",
    "directed_choice_disagreement_rate",
    "complete_conflict_rate",
    "mean_structural_conflict_margin",
    "min_structural_conflict_margin",
    "mean_route_conflict_margin",
    "min_route_conflict_margin",
    "regret_stability_slack_rate",
)

GLOBAL_METADATA_COLUMNS = (
    "run_id",
    "run_tier",
    "paper_result",
    "analysis_tier",
    "experiment_id",
    "configuration_id",
    "seed",
    "mechanism_id",
    "code_commit",
    "config_hash",
    "input_manifest_hash",
    "calibration_manifest_hash",
    "generated_at",
)

ROUTE_ROUND_COLUMNS = (
    *GLOBAL_METADATA_COLUMNS,
    "analysis_component",
    "route_id",
    "diagnostic_policy_id",
    "t",
    "action",
    "structural_best_action",
    "route_best_action",
    "structural_best_action_set",
    "route_best_action_set",
    "structural_loss_chosen",
    "structural_loss_best",
    "route_loss_chosen",
    "route_loss_best",
    "structural_regret_increment",
    "route_regret_increment",
    "delta_gap",
    "structural_margin",
    "pairwise_sign_disagreement",
    "directed_choice_disagreement",
    "complete_conflict",
    "structural_conflict_margin",
    "route_conflict_margin",
    "gap_margin_ratio",
    "ranking_reversal",
    "margin_preserved",
    "reversal_margin",
    "route_map_age",
    "arrival_batch_size",
    "empty_arrival_indicator",
    "multiarrival_indicator",
    "route_map_updated",
    "source_rounds",
    "source_weights",
    "path_id",
    "simulator_only",
    "learner_admissible",
)

LEARNER_ROUND_COLUMNS = (
    *GLOBAL_METADATA_COLUMNS,
    "analysis_component",
    "learner_id",
    "feedback_binding_id",
    "t",
    "context",
    "context_cell",
    "action",
    "selected_probability",
    "shared_action_uniform",
    "structural_best_action",
    "structural_loss_chosen",
    "structural_loss_best",
    "structural_regret_increment",
    "context_regret_increment",
    "factual_loss",
    "arrivals_processed",
    "updates_applied",
    "arrived_source_rounds",
    "arrived_source_actions",
    "arrived_source_probabilities",
    "updated_action_indices",
    "updated_context_cells",
    "update_probabilities",
    "used_source_identity",
    "read_full_loss_vector",
    "path_id",
    "learner_uniform_tape_id",
    "log_weight_hash",
)


class Exp1Error(RuntimeError):
    """Base exception for all hard-fail conditions."""


class ContractError(Exp1Error):
    pass


class CalibrationError(Exp1Error):
    pass


class ScientificInvariantError(Exp1Error):
    pass


class ArtifactError(Exp1Error):
    pass


@dataclass(frozen=True)
class Registry:
    experiment_id: str = EXPERIMENT_ID
    mechanism_order: tuple[str, ...] = MECHANISM_ORDER
    structural_families: tuple[str, ...] = STRUCTURAL_FAMILIES
    routes: tuple[str, ...] = ROUTES
    feedback_bindings: tuple[str, ...] = FEEDBACK_BINDINGS
    metrics: tuple[str, ...] = METRICS


REGISTRY = Registry()


def validate_id(value: str, allowed: tuple[str, ...], field_name: str) -> None:
    if value not in allowed:
        raise ContractError(f"{field_name}={value!r} is not allowed; expected one of {allowed}")


def display_name(identifier: str) -> str:
    try:
        return DISPLAY_NAMES[identifier]
    except KeyError as exc:
        raise ContractError(f"Missing display name for identifier {identifier!r}") from exc
