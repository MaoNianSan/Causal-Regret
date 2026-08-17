from __future__ import annotations

"""Primary runners for route diagnostics and paired learner consequences."""

from dataclasses import dataclass
import json
from typing import Any

import numpy as np
import pandas as pd

from config import LearnerConfig, StructuralConfig
from src.artifact_io import git_commit
from src.contracts import EXPERIMENT_ID, ScientificInvariantError
from src.delayed_exp3 import ContextualDelayedEXP3, SourceFeedbackEvent
from src.metrics import (
    action_gap_defect,
    complete_conflict_indicator,
    deterministic_best_action,
    directed_choice_disagreement,
    margin_preservation,
    optimal_mask,
    pairwise_sign_disagreement,
    ranking_reversal,
    regret_stability_slack,
    reversal_margin,
    route_conflict_margin,
    route_regret_increment,
    structural_conflict_margin,
    structural_margin,
    structural_regret_increment,
    transfer_slack,
)
from src.path_generator import SharedPathBundle
from src.route_maps import build_arrival_assigned_route_map, build_source_bound_route_map


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    run_tier: str
    paper_result: bool
    analysis_tier: str
    configuration_id: str
    code_commit: str
    config_hash: str
    input_manifest_hash: str
    calibration_manifest_hash: str
    generated_at: str


def _global_metadata(metadata: RunMetadata, bundle: SharedPathBundle) -> dict[str, Any]:
    return {
        "run_id": metadata.run_id,
        "run_tier": metadata.run_tier,
        "paper_result": bool(metadata.paper_result),
        "analysis_tier": metadata.analysis_tier,
        "experiment_id": EXPERIMENT_ID,
        "configuration_id": metadata.configuration_id,
        "seed": int(bundle.seed),
        "mechanism_id": bundle.mechanism_id,
        "code_commit": metadata.code_commit,
        "config_hash": metadata.config_hash,
        "input_manifest_hash": metadata.input_manifest_hash,
        "calibration_manifest_hash": metadata.calibration_manifest_hash,
        "generated_at": metadata.generated_at,
    }


def _eval_structural(bundle: SharedPathBundle) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = bundle.structural_path
    idx = np.flatnonzero(path.source_rounds >= 0)
    return (
        path.structural_loss_matrix[idx],
        path.public_context[idx],
        path.structural_margin[idx],
    )


def _set_as_list(mask: np.ndarray) -> list[list[int]]:
    return [np.flatnonzero(row).astype(int).tolist() for row in mask]


def run_route_map_diagnostic(
    bundle: SharedPathBundle,
    metadata: RunMetadata,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    structural_loss, _, precomputed_margin = _eval_structural(bundle)
    route_results = (
        build_arrival_assigned_route_map(bundle),
        build_source_bound_route_map(bundle),
    )
    global_meta = _global_metadata(metadata, bundle)
    all_rounds: list[pd.DataFrame] = []
    seed_rows: list[dict[str, Any]] = []

    structural_best_mask = optimal_mask(structural_loss)
    structural_best_action = deterministic_best_action(structural_loss)
    structural_best_sets = _set_as_list(structural_best_mask)
    recomputed_margin = structural_margin(structural_loss)
    if not np.allclose(precomputed_margin, recomputed_margin, atol=1e-12, rtol=0.0):
        raise ScientificInvariantError("structural margin reconstruction failed")

    for result in route_results:
        route_loss = result.route_loss_matrix
        route_best_mask = optimal_mask(route_loss)
        route_best_action = deterministic_best_action(route_loss)
        route_best_sets = _set_as_list(route_best_mask)
        actions = route_best_action.copy()  # route-greedy diagnostic
        delta = action_gap_defect(route_loss, structural_loss)
        rho = pairwise_sign_disagreement(route_loss, structural_loss)
        chi = directed_choice_disagreement(route_loss, structural_loss)
        complete_conflict = complete_conflict_indicator(route_loss, structural_loss)
        gamma = structural_conflict_margin(route_loss, structural_loss)
        eta = route_conflict_margin(route_loss, structural_loss)
        with np.errstate(invalid="ignore", divide="ignore"):
            gap_margin_ratio = np.where(
                np.isfinite(recomputed_margin) & (recomputed_margin > 0.0),
                delta / recomputed_margin,
                np.nan,
            )
        reversals = ranking_reversal(route_loss, structural_loss)
        preserved = margin_preservation(delta, recomputed_margin)
        reversal_margins = reversal_margin(route_loss, structural_loss)
        structural_inc = structural_regret_increment(actions, structural_loss)
        route_inc = route_regret_increment(actions, route_loss)
        rows = np.arange(structural_loss.shape[0])

        frame = pd.DataFrame(
            {
                **{key: [value] * structural_loss.shape[0] for key, value in global_meta.items()},
                "analysis_component": "route_map_diagnostic",
                "route_id": result.route_id,
                "diagnostic_policy_id": "route_greedy",
                "t": rows,
                "action": actions,
                "structural_best_action": structural_best_action,
                "route_best_action": route_best_action,
                "structural_best_action_set": structural_best_sets,
                "route_best_action_set": route_best_sets,
                "structural_loss_chosen": structural_loss[rows, actions],
                "structural_loss_best": np.min(structural_loss, axis=1),
                "route_loss_chosen": route_loss[rows, actions],
                "route_loss_best": np.min(route_loss, axis=1),
                "structural_regret_increment": structural_inc,
                "route_regret_increment": route_inc,
                "delta_gap": delta,
                "structural_margin": recomputed_margin,
                "pairwise_sign_disagreement": rho,
                "directed_choice_disagreement": chi,
                "complete_conflict": complete_conflict,
                "structural_conflict_margin": gamma,
                "route_conflict_margin": eta,
                "gap_margin_ratio": gap_margin_ratio,
                "ranking_reversal": reversals,
                "margin_preserved": preserved,
                "reversal_margin": reversal_margins,
                "route_map_age": result.route_map_age,
                "arrival_batch_size": result.arrival_batch_size,
                "empty_arrival_indicator": result.arrival_batch_size == 0,
                "multiarrival_indicator": result.arrival_batch_size > 1,
                "route_map_updated": result.route_map_updated,
                "source_rounds": result.source_round_lists,
                "source_weights": result.source_weight_lists,
                "path_id": bundle.bundle_id,
                "simulator_only": True,
                "learner_admissible": False,
            }
        )
        all_rounds.append(frame)

        structural_regret = float(np.sum(structural_inc))
        route_regret = float(np.sum(route_inc))
        alignment_budget = float(np.sum(delta))
        slack_rate, numerical_tolerance = transfer_slack(
            structural_regret, route_regret, alignment_budget, structural_loss.shape[0]
        )
        stability_rate, stability_tolerance = regret_stability_slack(
            structural_regret, route_regret, alignment_budget, structural_loss.shape[0]
        )
        reversal_values = reversal_margins[reversals]
        conflict_mask = complete_conflict.astype(bool)
        gamma_values = gamma[conflict_mask]
        eta_values = eta[conflict_mask]
        seed_rows.append(
            {
                **global_meta,
                "analysis_component": "route_map_diagnostic",
                "route_id": result.route_id,
                "diagnostic_policy_id": "route_greedy",
                "n_rounds": int(structural_loss.shape[0]),
                "structural_regret": structural_regret,
                "route_regret": route_regret,
                "alignment_budget": alignment_budget,
                "structural_regret_rate": structural_regret / structural_loss.shape[0],
                "route_regret_rate": route_regret / structural_loss.shape[0],
                "alignment_budget_rate": alignment_budget / structural_loss.shape[0],
                "transfer_bound_rate": (route_regret + alignment_budget) / structural_loss.shape[0],
                "transfer_slack_rate": slack_rate,
                "numerical_tolerance": numerical_tolerance,
                "transfer_invariant_pass": bool(slack_rate >= -numerical_tolerance),
                "regret_stability_slack_rate": stability_rate,
                "regret_stability_tolerance": stability_tolerance,
                "regret_stability_invariant_pass": bool(stability_rate >= -stability_tolerance),
                "pairwise_sign_disagreement_rate": float(np.mean(rho)),
                "directed_choice_disagreement_rate": float(np.mean(chi)),
                "ranking_reversal_rate": float(np.mean(reversals)),
                "complete_conflict_rate": float(np.mean(complete_conflict)),
                "complete_conflict_count": int(np.sum(conflict_mask)),
                "mean_structural_conflict_margin": (
                    float(np.mean(gamma_values)) if gamma_values.size else np.nan
                ),
                "min_structural_conflict_margin": (
                    float(np.min(gamma_values)) if gamma_values.size else np.nan
                ),
                "mean_route_conflict_margin": (
                    float(np.mean(eta_values)) if eta_values.size else np.nan
                ),
                "min_route_conflict_margin": (
                    float(np.min(eta_values)) if eta_values.size else np.nan
                ),
                "margin_preservation_rate": float(np.mean(preserved)),
                "mean_reversal_margin": float(np.mean(reversal_values)) if reversal_values.size else 0.0,
                "q10_reversal_margin": float(np.quantile(reversal_values, 0.10)) if reversal_values.size else 0.0,
                "generated_mean_delay": float(bundle.delay_path.generated_mean_delay),
                "empty_arrival_clock_rate": float(np.mean(result.arrival_batch_size == 0)),
                "multiarrival_clock_rate": float(np.mean(result.arrival_batch_size > 1)),
                "mean_route_map_age": float(np.mean(result.route_map_age)),
                "max_route_map_age": int(np.max(result.route_map_age)),
                "structural_path_hash": bundle.structural_path.path_hash,
                "delay_path_hash": bundle.delay_path.delay_path_hash,
                "bundle_hash": bundle.bundle_hash,
            }
        )
    return pd.concat(all_rounds, ignore_index=True), pd.DataFrame(seed_rows)


def _context_cell(context: float, boundaries: np.ndarray) -> int:
    return int(np.searchsorted(boundaries, float(context), side="right"))


def run_paired_learner_consequence(
    bundle: SharedPathBundle,
    metadata: RunMetadata,
    learner_config: LearnerConfig,
    context_partition: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    boundaries = np.asarray(context_partition["boundaries"], dtype=float)
    cell_oracle_actions = np.asarray(context_partition["cell_oracle_actions"], dtype=int)
    if boundaries.size + 1 != learner_config.n_context_cells:
        raise ScientificInvariantError("context partition and learner cell count differ")
    if cell_oracle_actions.size != learner_config.n_context_cells:
        raise ScientificInvariantError("context oracle action vector has invalid size")

    structural_loss, contexts, _ = _eval_structural(bundle)
    delays = bundle.delay_path.delays[bundle.delay_path.source_rounds >= 0]
    horizon = structural_loss.shape[0]
    if delays.size != horizon:
        raise ScientificInvariantError("evaluation delay path has invalid length")

    learners = {
        binding: ContextualDelayedEXP3(
            k_actions=bundle.structural_path.action_locations.size,
            context_boundaries=boundaries,
            gamma=learner_config.exploration_gamma,
            eta=learner_config.learning_rate_eta,
        )
        for binding in ("arrival_clock", "source_round")
    }
    queues: dict[str, dict[int, list[SourceFeedbackEvent]]] = {
        binding: {} for binding in learners
    }
    records: dict[str, list[dict[str, Any]]] = {binding: [] for binding in learners}
    global_meta = _global_metadata(metadata, bundle)

    for t in range(horizon):
        current_context = float(contexts[t])
        uniform_draw = float(bundle.learner_uniform_tape[t])
        branch_action: dict[str, int] = {}
        branch_probability: dict[str, float] = {}
        branch_cell: dict[str, int] = {}

        # Decision first: clock-t arrivals are not part of F_t.
        for binding, learner in learners.items():
            cell = learner.context_cell(current_context)
            action, probability = learner.choose_action(cell, uniform_draw)
            branch_cell[binding] = cell
            branch_action[binding] = action
            branch_probability[binding] = probability

        # Generate factual source events using the shared source-level delay path.
        for binding in learners:
            action = branch_action[binding]
            factual_loss = float(structural_loss[t, action])
            arrival_clock = int(t + delays[t])
            event = SourceFeedbackEvent(
                event_id=f"{bundle.bundle_id}:{binding}:{t}",
                source_round=t,
                arrival_clock=arrival_clock,
                source_context_cell=branch_cell[binding],
                source_action=action,
                source_action_probability=branch_probability[binding],
                factual_loss=factual_loss,
            )
            queues[binding].setdefault(arrival_clock, []).append(event)

        for binding, learner in learners.items():
            arrivals = sorted(queues[binding].pop(t, []), key=lambda event: event.source_round)
            updated_actions: list[int] = []
            updated_cells: list[int] = []
            update_probabilities: list[float] = []
            for event in arrivals:
                if binding == "arrival_clock":
                    update_cell = branch_cell[binding]
                    update_action = branch_action[binding]
                    update_probability = branch_probability[binding]
                else:
                    update_cell = event.source_context_cell
                    update_action = event.source_action
                    update_probability = event.source_action_probability
                learner.apply_update(
                    context_cell=update_cell,
                    action=update_action,
                    selected_probability=update_probability,
                    factual_loss=event.factual_loss,
                )
                updated_actions.append(int(update_action))
                updated_cells.append(int(update_cell))
                update_probabilities.append(float(update_probability))

            action = branch_action[binding]
            best_action = int(np.argmin(structural_loss[t]))
            structural_best_loss = float(np.min(structural_loss[t]))
            structural_regret = float(structural_loss[t, action] - structural_best_loss)
            context_oracle_action = int(cell_oracle_actions[branch_cell[binding]])
            context_regret = float(
                structural_loss[t, action] - structural_loss[t, context_oracle_action]
            )
            records[binding].append(
                {
                    **global_meta,
                    "analysis_component": "learner_consequence",
                    "learner_id": learner_config.learner_id,
                    "feedback_binding_id": binding,
                    "t": t,
                    "context": current_context,
                    "context_cell": branch_cell[binding],
                    "action": action,
                    "selected_probability": branch_probability[binding],
                    "shared_action_uniform": uniform_draw,
                    "structural_best_action": best_action,
                    "structural_loss_chosen": float(structural_loss[t, action]),
                    "structural_loss_best": structural_best_loss,
                    "structural_regret_increment": structural_regret,
                    "context_regret_increment": context_regret,
                    "factual_loss": float(structural_loss[t, action]),
                    "arrivals_processed": len(arrivals),
                    "updates_applied": len(arrivals),
                    "arrived_source_rounds": [int(event.source_round) for event in arrivals],
                    "arrived_source_actions": [int(event.source_action) for event in arrivals],
                    "arrived_source_probabilities": [float(event.source_action_probability) for event in arrivals],
                    "updated_action_indices": updated_actions,
                    "updated_context_cells": updated_cells,
                    "update_probabilities": update_probabilities,
                    "used_source_identity": binding == "source_round",
                    "read_full_loss_vector": False,
                    "path_id": bundle.bundle_id,
                    "learner_uniform_tape_id": bundle.learner_uniform_tape_id,
                    "log_weight_hash": learner.state_hash(),
                }
            )

    round_frame = pd.concat(
        [pd.DataFrame(records[binding]) for binding in ("arrival_clock", "source_round")],
        ignore_index=True,
    )
    seed_rows: list[dict[str, Any]] = []
    for binding in ("arrival_clock", "source_round"):
        frame = pd.DataFrame(records[binding])
        seed_rows.append(
            {
                **global_meta,
                "analysis_component": "learner_consequence",
                "learner_id": learner_config.learner_id,
                "feedback_binding_id": binding,
                "n_rounds": horizon,
                "structural_regret": float(frame["structural_regret_increment"].sum()),
                "structural_regret_rate": float(frame["structural_regret_increment"].mean()),
                "context_constrained_regret": float(frame["context_regret_increment"].sum()),
                "context_constrained_regret_rate": float(frame["context_regret_increment"].mean()),
                "feedback_units_processed": int(frame["updates_applied"].sum()),
                "terminal_unobserved_feedback": int(
                    sum(len(events) for clock, events in queues[binding].items() if clock >= horizon)
                ),
                "final_log_weight_hash": learners[binding].state_hash(),
                "structural_path_hash": bundle.structural_path.path_hash,
                "delay_path_hash": bundle.delay_path.delay_path_hash,
                "learner_uniform_tape_hash": bundle.learner_uniform_tape_hash,
                "bundle_hash": bundle.bundle_hash,
            }
        )
    seed_frame = pd.DataFrame(seed_rows)
    arrival_rate = float(
        seed_frame.loc[seed_frame.feedback_binding_id == "arrival_clock", "structural_regret_rate"].iloc[0]
    )
    source_rate = float(
        seed_frame.loc[seed_frame.feedback_binding_id == "source_round", "structural_regret_rate"].iloc[0]
    )
    seed_frame["paired_arrival_minus_source_regret_rate"] = arrival_rate - source_rate
    return round_frame, seed_frame
