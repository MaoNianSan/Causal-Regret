"""Execution units for Module A, appendix learners, and Module B."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

import config
from audit_engine import (
    audit_route,
    construct_audit_unit_records,
    construct_population_target_records,
    evaluate_calibration_controls,
)
from policies import ArrivalTimeUCB, HistorySurrogateUCB, ProxyLabelUCB, SourceBoundUCB
from route_maps import (
    construct_arrival_time_route,
    construct_history_surrogate_route,
    construct_label_blind_attribution_diagnostics,
    construct_proxy_label_route,
    construct_source_bound_route,
    evaluate_pairwise_metrics,
    evaluate_route_map,
)
from simulator import (
    StructuralTrajectory,
    generate_structural_trajectory,
    save_structural_trajectory,
    trajectory_manifest_record,
)


def _configuration_id(
    module_id: str,
    route_id: str,
    route_label_rate: float | None = None,
    attribution_proxy_noise_sd: float | None = None,
) -> str:
    parts = [module_id, route_id]
    if route_label_rate is not None:
        parts.append(f"label_rate_{int(round(route_label_rate * 100)):03d}")
    if attribution_proxy_noise_sd is not None:
        parts.append(f"proxy_noise_{int(round(attribution_proxy_noise_sd * 100)):03d}")
    return "__".join(parts)


def _action_trace_hash(actions: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(actions).tobytes()).hexdigest()


def run_scalar_feedback_learner(
    trajectory: StructuralTrajectory,
    route_id: str,
    route_label_rate: float,
    attribution_proxy_noise_sd: float,
) -> dict[str, Any]:
    context_ids = trajectory.context_ids()
    num_actions = config.PARAMETERS.num_actions
    if route_id == "arrival_time":
        learner: Any = ArrivalTimeUCB(num_actions, num_actions)
    elif route_id == "history_surrogate":
        learner = HistorySurrogateUCB(num_actions, num_actions)
    elif route_id == "proxy_label":
        learner = ProxyLabelUCB(
            num_actions,
            num_actions,
            trajectory.attribution_proxy(attribution_proxy_noise_sd),
        )
    elif route_id == "source_bound":
        learner = SourceBoundUCB(num_actions, num_actions)
    else:
        raise KeyError(f"Unknown learner route_id: {route_id}")

    action_history = np.full(trajectory.decision_horizon, -1, dtype=np.int64)
    context_history = context_ids[: trajectory.decision_horizon].copy()
    structural_regret = np.zeros(trajectory.decision_horizon, dtype=np.float64)
    route_label_mask = trajectory.route_label_mask(route_label_rate)
    structural_minimum = np.min(trajectory.structural_loss_map, axis=1)

    for decision_round in range(trajectory.decision_horizon):
        current_context = int(context_history[decision_round])
        action = int(learner.choose_action(decision_round, current_context))
        action_history[decision_round] = action
        structural_regret[decision_round] = (
            trajectory.structural_loss_map[decision_round, action]
            - structural_minimum[decision_round]
        )
        arriving_sources = trajectory.arrivals_by_clock[decision_round]
        anonymous_losses: list[float] = []
        labelled_events: list[tuple[int, float]] = []
        for source_round in arriving_sources:
            source_action = int(action_history[source_round])
            factual_loss = float(
                trajectory.realized_potential_feedback[source_round, source_action]
            )
            if route_id == "source_bound" or (
                route_id == "proxy_label" and bool(route_label_mask[source_round])
            ):
                labelled_events.append((int(source_round), factual_loss))
            else:
                anonymous_losses.append(factual_loss)
        if route_id == "arrival_time":
            learner.observe(action, current_context, anonymous_losses)
        elif route_id == "history_surrogate":
            learner.observe(action, current_context, anonymous_losses)
        elif route_id == "source_bound":
            learner.observe(labelled_events, action_history, context_history)
        elif route_id == "proxy_label":
            learner.observe(
                decision_round,
                labelled_events,
                anonymous_losses,
                action_history,
                context_history,
                trajectory.decision_horizon,
            )

    return {
        "route_id": route_id,
        "route_label_rate": float(route_label_rate),
        "attribution_proxy_noise_sd": float(attribution_proxy_noise_sd),
        "structural_regret_per_round": float(
            np.mean(structural_regret[trajectory.evaluation_slice])
        ),
        "action_trace_sha256": _action_trace_hash(action_history),
        "uses_full_structural_map_for_update": False,
        "uses_realized_scalar_feedback": True,
    }


def run_module_a_seed(
    seed: int,
    decision_horizon: int,
    warmup_rounds: int,
    run_dir: Path,
) -> dict[str, Any]:
    trajectory = generate_structural_trajectory(seed, decision_horizon, warmup_rounds)
    trajectory_path = run_dir / "raw" / "trajectories" / f"module_a_seed_{seed:03d}.npz"
    save_structural_trajectory(trajectory, trajectory_path)
    manifest_record = trajectory_manifest_record(trajectory, trajectory_path, run_dir)

    arrival_result = construct_arrival_time_route(trajectory)
    history_result = construct_history_surrogate_route(trajectory)
    source_result = construct_source_bound_route(trajectory)
    primary_sigma = config.PARAMETERS.attribution_proxy_noise_sd_primary_audit
    primary_rate = config.PARAMETERS.route_label_rate_primary_audit

    seed_records: list[dict[str, Any]] = []
    pair_records: list[dict[str, Any]] = []
    base_results = [arrival_result, history_result, source_result]
    for route_result in base_results:
        summary, _ = evaluate_route_map(trajectory, route_result)
        configuration_id = _configuration_id(
            config.MODULE_ROUTE_BOUNDARY,
            route_result.route_id,
            primary_rate,
            primary_sigma,
        )
        seed_records.append(
            {
                "seed": int(seed),
                "route_id": route_result.route_id,
                "route_label_rate": primary_rate,
                "attribution_proxy_noise_sd": primary_sigma,
                **summary,
                "route_map_hash": route_result.route_map_hash,
                "structural_map_hash": trajectory.path_hashes[
                    "structural_loss_map_hash"
                ],
                "path_id": trajectory.path_id,
                "configuration_id": configuration_id,
                "analysis_tier": "appendix",
            }
        )
        pair_metrics = evaluate_pairwise_metrics(trajectory, route_result)
        action_pair_low, action_pair_high = np.triu_indices(
            config.PARAMETERS.num_actions, k=1
        )
        for pair_index in range(len(action_pair_low)):
            pair_records.append(
                {
                    "seed": int(seed),
                    "route_id": route_result.route_id,
                    "route_label_rate": primary_rate,
                    "attribution_proxy_noise_sd": primary_sigma,
                    "action_pair_low": int(action_pair_low[pair_index]),
                    "action_pair_high": int(action_pair_high[pair_index]),
                    "mean_absolute_action_gap_error": float(
                        pair_metrics["mean_absolute_action_gap_error"][pair_index]
                    ),
                    "action_gap_rmse": float(
                        pair_metrics["action_gap_rmse"][pair_index]
                    ),
                    "sign_agreement_rate": float(
                        pair_metrics["sign_agreement_rate"][pair_index]
                    ),
                    "configuration_id": configuration_id,
                    "analysis_tier": "appendix",
                }
            )

    for attribution_proxy_noise_sd in config.MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS:
        label_blind = construct_label_blind_attribution_diagnostics(
            trajectory, attribution_proxy_noise_sd
        )
        for route_label_rate in config.MODULE_A_ROUTE_LABEL_RATES:
            proxy_result = construct_proxy_label_route(
                trajectory,
                route_label_rate=route_label_rate,
                attribution_proxy_noise_sd=attribution_proxy_noise_sd,
                label_blind_diagnostics=label_blind,
            )
            summary, _ = evaluate_route_map(trajectory, proxy_result)
            configuration_id = _configuration_id(
                config.MODULE_ROUTE_BOUNDARY,
                "proxy_label",
                route_label_rate,
                attribution_proxy_noise_sd,
            )
            seed_records.append(
                {
                    "seed": int(seed),
                    "route_id": "proxy_label",
                    "route_label_rate": float(route_label_rate),
                    "attribution_proxy_noise_sd": float(
                        attribution_proxy_noise_sd
                    ),
                    **summary,
                    "route_map_hash": proxy_result.route_map_hash,
                    "structural_map_hash": trajectory.path_hashes[
                        "structural_loss_map_hash"
                    ],
                    "path_id": trajectory.path_id,
                    "configuration_id": configuration_id,
                    "analysis_tier": "primary",
                }
            )
            pair_metrics = evaluate_pairwise_metrics(trajectory, proxy_result)
            action_pair_low, action_pair_high = np.triu_indices(
                config.PARAMETERS.num_actions, k=1
            )
            for pair_index in range(len(action_pair_low)):
                pair_records.append(
                    {
                        "seed": int(seed),
                        "route_id": "proxy_label",
                        "route_label_rate": float(route_label_rate),
                        "attribution_proxy_noise_sd": float(
                            attribution_proxy_noise_sd
                        ),
                        "action_pair_low": int(action_pair_low[pair_index]),
                        "action_pair_high": int(action_pair_high[pair_index]),
                        "mean_absolute_action_gap_error": float(
                            pair_metrics["mean_absolute_action_gap_error"][pair_index]
                        ),
                        "action_gap_rmse": float(
                            pair_metrics["action_gap_rmse"][pair_index]
                        ),
                        "sign_agreement_rate": float(
                            pair_metrics["sign_agreement_rate"][pair_index]
                        ),
                        "configuration_id": configuration_id,
                        "analysis_tier": "primary",
                    }
                )

    learner_records: list[dict[str, Any]] = []
    for route_id in ["arrival_time", "history_surrogate", "source_bound"]:
        result = run_scalar_feedback_learner(
            trajectory,
            route_id=route_id,
            route_label_rate=primary_rate,
            attribution_proxy_noise_sd=primary_sigma,
        )
        learner_records.append(
            {
                "seed": int(seed),
                **result,
                "path_id": trajectory.path_id,
                "configuration_id": _configuration_id(
                    config.MODULE_LEARNER_APPENDIX,
                    route_id,
                    primary_rate,
                    primary_sigma,
                ),
            }
        )
    for route_label_rate in config.MODULE_A_ROUTE_LABEL_RATES:
        result = run_scalar_feedback_learner(
            trajectory,
            route_id="proxy_label",
            route_label_rate=route_label_rate,
            attribution_proxy_noise_sd=primary_sigma,
        )
        learner_records.append(
            {
                "seed": int(seed),
                **result,
                "path_id": trajectory.path_id,
                "configuration_id": _configuration_id(
                    config.MODULE_LEARNER_APPENDIX,
                    "proxy_label",
                    route_label_rate,
                    primary_sigma,
                ),
            }
        )
    return {
        "seed_records": seed_records,
        "pair_records": pair_records,
        "learner_records": learner_records,
        "trajectory_manifest_record": manifest_record,
    }


def save_module_b_route_maps(
    trajectory: StructuralTrajectory,
    route_results: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proxy_diagnostics = route_results["proxy_label"].attribution_diagnostics
    if proxy_diagnostics is None:
        raise RuntimeError("Proxy-label diagnostics are required for Module B storage.")
    np.savez_compressed(
        output_path,
        structural_loss_map=trajectory.structural_loss_map.astype(np.float64),
        arrival_time_route_map=route_results["arrival_time"].route_loss_map.astype(
            np.float64
        ),
        history_surrogate_route_map=route_results[
            "history_surrogate"
        ].route_loss_map.astype(np.float64),
        proxy_label_route_map=route_results["proxy_label"].route_loss_map.astype(
            np.float64
        ),
        source_bound_route_map=route_results["source_bound"].route_loss_map.astype(
            np.float64
        ),
        route_label_mask=trajectory.route_label_mask(
            config.PARAMETERS.route_label_rate_primary_audit
        ),
        audit_uniform_mcar=trajectory.audit_uniform_mcar,
        audit_uniform_biased=trajectory.audit_uniform_biased,
        base_ambiguity_score=proxy_diagnostics.base_ambiguity_score,
        candidate_contributor_count=proxy_diagnostics.candidate_contributor_count,
        maximum_assignment_mass=proxy_diagnostics.maximum_assignment_mass,
        path_id=np.array([trajectory.path_id]),
    )


def run_module_b_replication(
    replication_id: int,
    decision_horizon: int,
    warmup_rounds: int,
    run_dir: Path,
) -> dict[str, Any]:
    trajectory = generate_structural_trajectory(
        replication_id + 10_000_000,
        decision_horizon,
        warmup_rounds,
    )
    trajectory_path = (
        run_dir
        / "raw"
        / "trajectories"
        / f"module_b_replication_{replication_id:04d}.npz"
    )
    save_structural_trajectory(trajectory, trajectory_path)
    manifest_record = trajectory_manifest_record(trajectory, trajectory_path, run_dir)
    label_blind = construct_label_blind_attribution_diagnostics(
        trajectory,
        config.PARAMETERS.attribution_proxy_noise_sd_primary_audit,
    )
    route_results = {
        "arrival_time": construct_arrival_time_route(trajectory),
        "history_surrogate": construct_history_surrogate_route(trajectory),
        "proxy_label": construct_proxy_label_route(
            trajectory,
            route_label_rate=config.PARAMETERS.route_label_rate_primary_audit,
            attribution_proxy_noise_sd=config.PARAMETERS.attribution_proxy_noise_sd_primary_audit,
            label_blind_diagnostics=label_blind,
        ),
        "source_bound": construct_source_bound_route(trajectory),
    }
    route_map_path = (
        run_dir
        / "raw"
        / "route_maps"
        / f"replication_{replication_id:04d}.npz"
    )
    save_module_b_route_maps(trajectory, route_results, route_map_path)
    proxy_diagnostics = route_results["proxy_label"].attribution_diagnostics
    if proxy_diagnostics is None:
        raise RuntimeError("Missing proxy attribution diagnostics in Module B.")
    evaluation = trajectory.evaluation_slice
    ambiguity_score = proxy_diagnostics.base_ambiguity_score[evaluation]
    contributor_count = proxy_diagnostics.candidate_contributor_count[evaluation]
    maximum_assignment_mass = proxy_diagnostics.maximum_assignment_mass[evaluation]
    audit_unit_records = construct_audit_unit_records(
        trajectory,
        route_results,
        ambiguity_score,
        contributor_count,
        maximum_assignment_mass,
        replication_id,
    )
    population_target_records = construct_population_target_records(
        trajectory, route_results, replication_id
    )
    raw_records: list[dict[str, Any]] = []
    calibrated_records: list[dict[str, Any]] = []
    calibration_parameter_records: list[dict[str, Any]] = []
    for route_id in config.ROUTE_ORDER:
        raw, calibrated, parameters = audit_route(
            trajectory,
            route_results[route_id],
            ambiguity_score,
            replication_id,
        )
        raw_records.extend(raw)
        calibrated_records.extend(calibrated)
        calibration_parameter_records.extend(parameters)
    control_records, control_parameter_records = evaluate_calibration_controls(
        trajectory, route_results["proxy_label"], replication_id
    )
    calibration_parameter_records.extend(control_parameter_records)
    manifest_record.update(
        {
            "replication_id": int(replication_id),
            "route_map_file": route_map_path.relative_to(run_dir).as_posix(),
            "route_map_hashes": {
                route_id: route_results[route_id].route_map_hash
                for route_id in config.ROUTE_ORDER
            },
        }
    )
    return {
        "audit_unit_records": audit_unit_records,
        "raw_records": raw_records,
        "calibrated_records": calibrated_records,
        "calibration_parameter_records": calibration_parameter_records,
        "population_target_records": population_target_records,
        "control_records": control_records,
        "trajectory_manifest_record": manifest_record,
    }
