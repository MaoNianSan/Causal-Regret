from __future__ import annotations

"""Theorem-targeted controlled sweeps for Experiment 1 (config v1.2).

These sweeps are diagnostics of the final theoretical contract, isolated from
the delay-mechanism registry, the learner, and the primary six mechanisms.
They are integrated through ``targeted.py`` and verified by ``self_check.py``.

1. Exact-cardinal shift amplitude sweep:
   c_scale in {0, 0.05, 0.10, 0.20} with the same delayed arrival-assignment
   construction. For every scale the decision-relevant diagnostics must be
   zero (delta = rho = chi = 0), while the raw actionwise level error may
   grow. No clipping is permitted.

2. Margin/distortion threshold sweep:
   operates only on rounds with exactly one structural optimum and finite
   positive structural margin. Perturbs the unique best and the deterministic
   nearest competitor with +d/2 / -d/2 (d = r * mu). For r <= 2 the
   perturbation stays between the original best and competitor levels and
   requires NO clipping. Hard invariants: r < 1 -> chi = 0; r = 1 -> chi = 1/2;
   r > 1 -> chi = 1. rho is reported but no artificial closed-form value is
   imposed on it.

3. Matched shared-vs-action-dependent cancellation sweep:
   adds the SAME per-round level component to every action (shared profiles
   ``static_shared`` = 1 and ``state_varying_shared`` = 1 + S_t) and, in a
   matched grid, the best/nearest-competitor residual of the margin sweep.
   The diagnostic separates an action-invariant component, which may change
   loss levels while leaving action gaps, rankings, choices and the same-round
   regret map unchanged, from an action-dependent residual, which is the
   component that can change those decision objects. It is route-map-only,
   never calls the learner, and never enters ``MECHANISM_ORDER``.

   Gate C4 is checked in the native scale of the exact identity
   ``delta = alpha_dep * mu`` with tolerance
   ``ratio_tol * mu + 32 * eps * max(1, |L_row|, |L_route_row|)``, while the
   normalized ratio ``delta / mu`` is gated only on ratio-conditioned rounds
   (``mu >= roundoff_floor / ratio_tol``) and kept as a diagnostic elsewhere.
   The ratio tolerance (``1e-9``) and the round-off safety factor (``32``) are
   frozen constants declared before the run.
"""

import ast
import inspect
import textwrap
from typing import Any

import numpy as np

from config import MECHANISM_ORDER, DelayConfig, StructuralConfig, THEORY_SWEEP
from src.artifact_io import hash_payload
from src.contracts import ScientificInvariantError
from src.delay_mechanisms import generate_geometric_delay
from src.metrics import (
    action_gap_defect,
    complete_conflict_indicator,
    directed_choice_disagreement,
    optimal_mask,
    pairwise_sign_disagreement,
    structural_margin,
)
from src.path_generator import SharedPathBundle
from src.route_maps import build_arrival_assigned_route_map
from src.structural_process import (
    StructuralPath,
    generate_exact_valid_shift_path,
    generate_smooth_bounded_ar1_path,
)

SWEEP_TOLERANCE = 1e-10


def _sweep_bundle(path: StructuralPath, delay) -> SharedPathBundle:
    """Simulator-only bundle for sweep route diagnostics.

    Mirrors the calibration-only bundle pattern: the learner tape is unused by
    the route-map construction, so a zero tape of the correct length suffices.
    """
    tape = np.zeros(int(np.sum(path.source_rounds >= 0)), dtype=float)
    payload_hash = hash_payload(
        {"path": path.path_hash, "delay": delay.delay_path_hash}
    )
    return SharedPathBundle(
        seed=path.seed,
        mechanism_id="theory_sweep",
        structural_path=path,
        delay_path=delay,
        learner_uniform_tape=tape,
        learner_uniform_tape_id="theory_sweep_only",
        learner_uniform_tape_hash="theory_sweep_only",
        bundle_id=f"theory_sweep:{payload_hash[:16]}",
        bundle_hash=payload_hash,
    )


def _evaluation_slice(path: StructuralPath) -> slice:
    return slice(
        int(np.flatnonzero(path.source_rounds >= 0)[0]),
        int(np.flatnonzero(path.source_rounds >= 0)[-1]) + 1,
    )


def exact_shift_sweep_rows(
    structural_config: StructuralConfig,
    seeds: tuple[int, ...],
    geometric_probability: float,
    delay_config: DelayConfig,
    scales: tuple[float, ...] = THEORY_SWEEP.exact_shift_scales,
    g_scale: float = 0.6,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Exact-cardinal shift amplitude sweep.

    Returns per (seed, c_scale) records plus invariant checks. For every scale
    the decision-relevant diagnostics delta/rho/chi must be zero while the raw
    actionwise level error may grow. No clipping is used anywhere.
    """
    rows: list[dict[str, Any]] = []
    all_delta: list[float] = []
    all_rho: list[float] = []
    all_chi: list[float] = []
    for seed in seeds:
        base = generate_smooth_bounded_ar1_path(structural_config, int(seed))
        delay = generate_geometric_delay(
            base, float(geometric_probability), delay_config.d_max
        )
        for c_scale in scales:
            shifted = generate_exact_valid_shift_path(
                base, c_scale=float(c_scale), g_scale=float(g_scale)
            )
            bundle = _sweep_bundle(shifted, delay)
            route = build_arrival_assigned_route_map(bundle)
            evaluation = _evaluation_slice(shifted)
            structural_loss = shifted.structural_loss_matrix[evaluation]
            route_loss = route.route_loss_matrix
            delta = action_gap_defect(route_loss, structural_loss)
            rho = pairwise_sign_disagreement(route_loss, structural_loss)
            chi = directed_choice_disagreement(route_loss, structural_loss)
            level_error = float(np.mean(np.abs(route_loss - structural_loss)))
            rows.append(
                {
                    "seed": int(seed),
                    "c_scale": float(c_scale),
                    "g_scale": float(g_scale),
                    "n_rounds": int(structural_loss.shape[0]),
                    "max_delta": float(np.max(delta)),
                    "max_rho": float(np.max(rho)),
                    "max_chi": float(np.max(chi)),
                    "mean_absolute_actionwise_level_error": level_error,
                    "loss_clipping_count": 0,
                }
            )
            all_delta.append(float(np.max(delta)))
            all_rho.append(float(np.max(rho)))
            all_chi.append(float(np.max(chi)))
    checks = {
        "sweep_id": "exact_cardinal_shift_amplitude",
        "scales": list(scales),
        "n_cells": len(rows),
        "delta_all_zero": bool(max(all_delta or [0.0]) <= SWEEP_TOLERANCE),
        "rho_all_zero": bool(max(all_rho or [0.0]) <= SWEEP_TOLERANCE),
        "chi_all_zero": bool(max(all_chi or [0.0]) <= SWEEP_TOLERANCE),
        "no_clipping": True,
        "passed": bool(
            rows
            and max(all_delta or [0.0]) <= SWEEP_TOLERANCE
            and max(all_rho or [0.0]) <= SWEEP_TOLERANCE
            and max(all_chi or [0.0]) <= SWEEP_TOLERANCE
        ),
    }
    return rows, checks


def _eligible_rounds(
    structural_loss: np.ndarray, tolerance: float = 1e-12
) -> np.ndarray:
    minima = np.min(structural_loss, axis=1)
    optimal = structural_loss <= minima[:, None] + tolerance
    unique = np.sum(optimal, axis=1) == 1
    margins = structural_margin(structural_loss)
    finite_positive = np.isfinite(margins) & (margins > 0.0)
    return unique & finite_positive


def _nearest_competitor(row: np.ndarray, best: int) -> int:
    regret = row - row[best]
    nonzero = np.flatnonzero(np.abs(regret) > 1e-12)
    minimum_regret = float(np.min(regret[nonzero]))
    candidates = np.flatnonzero(
        np.isclose(regret, minimum_regret, atol=1e-12, rtol=0.0)
    )
    # Deterministic action-index tie break: smallest index.
    return int(np.min(candidates))


def margin_threshold_sweep_rows(
    structural_config: StructuralConfig,
    seeds: tuple[int, ...],
    ratios: tuple[float, ...] = THEORY_SWEEP.margin_distortion_ratios,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Margin/distortion threshold sweep on the normal smooth structural path.

    For each eligible round (unique optimum, finite positive margin) and each
    prescribed ratio r, perturbs the unique best (+r*mu/2) and the deterministic
    nearest competitor (-r*mu/2). Hard invariants: r<1 -> chi=0, r=1 -> chi=1/2,
    r>1 -> chi=1. Realized delta/mu must equal r. No clipping is permitted
    (for r <= 2 the perturbed losses stay inside the original best/competitor
    range, which is within [0, 1]).
    """
    rows: list[dict[str, Any]] = []
    ratio_errors: list[float] = []
    clipping_violations = 0
    for seed in seeds:
        base = generate_smooth_bounded_ar1_path(structural_config, int(seed))
        evaluation = _evaluation_slice(base)
        structural_loss = base.structural_loss_matrix[evaluation].copy()
        eligible = _eligible_rounds(structural_loss)
        eligible_positions = np.flatnonzero(eligible)
        for ratio in ratios:
            delta_ratio_values: list[float] = []
            chi_values: list[float] = []
            rho_values: list[float] = []
            for t in eligible_positions:
                row = structural_loss[t]
                best = int(np.argmin(row))
                competitor = _nearest_competitor(row, best)
                mu = float(row[competitor] - row[best])
                d = float(ratio) * mu
                error = np.zeros(row.size, dtype=float)
                error[best] = +d / 2.0
                error[competitor] = -d / 2.0
                route_row = row + error
                # No clipping permitted: for r <= 2 the perturbed losses must
                # stay within the original best/competitor range, hence inside
                # [0, 1]. Hard fail otherwise.
                if (
                    float(np.min(route_row)) < -1e-12
                    or float(np.max(route_row)) > 1.0 + 1e-12
                ):
                    clipping_violations += 1
                oscillation = float(np.max(error) - np.min(error))
                if not np.isclose(oscillation, d, atol=1e-12, rtol=0.0):
                    clipping_violations += 1
                route_loss = route_row[None, :]
                structural_one = row[None, :]
                delta = float(action_gap_defect(route_loss, structural_one)[0])
                chi = float(directed_choice_disagreement(route_loss, structural_one)[0])
                rho = float(pairwise_sign_disagreement(route_loss, structural_one)[0])
                delta_ratio_values.append(delta / mu if mu > 0 else np.nan)
                chi_values.append(chi)
                rho_values.append(rho)
            rows.append(
                {
                    "seed": int(seed),
                    "ratio": float(ratio),
                    "eligible_rounds": int(np.sum(eligible)),
                    "mean_delta_over_mu": (
                        float(np.mean(delta_ratio_values))
                        if delta_ratio_values
                        else np.nan
                    ),
                    "max_delta_over_mu_deviation": (
                        float(
                            np.max(
                                np.abs(np.asarray(delta_ratio_values) - float(ratio))
                            )
                        )
                        if delta_ratio_values
                        else np.nan
                    ),
                    "mean_chi": float(np.mean(chi_values)) if chi_values else np.nan,
                    "mean_rho": float(np.mean(rho_values)) if rho_values else np.nan,
                    "expected_chi": (
                        0.0
                        if float(ratio) < 1.0
                        else (0.5 if float(ratio) == 1.0 else 1.0)
                    ),
                }
            )
    threshold_ok = all(
        np.isclose(row["mean_chi"], row["expected_chi"], atol=1e-12)
        for row in rows
        if np.isfinite(row["mean_chi"])
    )
    ratio_ok = all(
        (
            np.isnan(row["max_delta_over_mu_deviation"])
            or row["max_delta_over_mu_deviation"] <= 1e-9
        )
        for row in rows
    )
    support = sum(
        int(row["eligible_rounds"]) for row in rows if row["ratio"] == ratios[0]
    )
    checks = {
        "sweep_id": "margin_distortion_threshold",
        "ratios": list(ratios),
        "n_cells": len(rows),
        "eligible_round_support_total": support,
        "realized_delta_over_mu_matches_ratio": ratio_ok,
        "threshold_behavior_correct": threshold_ok,
        "no_clipping": clipping_violations == 0,
        "clipping_violations": clipping_violations,
        "passed": bool(
            rows
            and support > 0
            and ratio_ok
            and threshold_ok
            and clipping_violations == 0
        ),
    }
    return rows, checks


CANCELLATION_SWEEP_ID = "cancellation_shared_vs_action_dependent"
CANCELLATION_REFERENCE_PROFILE = "static_shared"
CANCELLATION_REFERENCE_SHARED_SCALE = 0.00
# Normalized tolerance of the realized delta/mu ratio; unchanged from the
# existing margin-sweep numerical tolerance. It is used only on rounds where the
# ratio is numerically conditioned, while the hard gate is the native identity.
CANCELLATION_DELTA_RATIO_TOLERANCE = 1e-9
# Fixed floating-point safety factor for the short sequence of
# subtraction/max/oscillation operations behind the native C4 tolerance. It is
# declared here and in docs/EXPERIMENT_IO_CONTRACT.md before any rerun and must
# not be changed after inspecting results.
CANCELLATION_ROUNDOFF_SAFETY_FACTOR = 32.0

_CANCELLATION_FORBIDDEN_CALLS = {
    "clip": "clipping",
    "clamp": "clipping",
    "run_paired_learner_consequence": "learner",
    "run_route_map_diagnostic": "learner",
    "build_arrival_assigned_route_map": "learner",
    "build_source_bound_route_map": "learner",
    "atomic_write_csv": "write",
    "atomic_write_json": "write",
    "to_csv": "write",
    "to_parquet": "write",
    "write_text": "write",
    "write_bytes": "write",
    "mkdir": "write",
    "unlink": "write",
}


def _shared_component(profile: str, structural_state: np.ndarray) -> np.ndarray:
    """Frozen action-invariant shared profile c_t.

    ``static_shared`` is c_t = 1; ``state_varying_shared`` is c_t = 1 + S_t on
    the already generated structural state, so c_t stays in [0, 2] up to
    floating-point limits. Nothing is normalised by any evaluation statistic.
    """
    state = np.asarray(structural_state, dtype=float)
    if profile == "static_shared":
        return np.ones(state.shape, dtype=float)
    if profile == "state_varying_shared":
        return 1.0 + state
    raise ValueError(f"unknown cancellation shared profile {profile!r}")


def _actionwise_regret_map(loss: np.ndarray) -> np.ndarray:
    """All-action per-round regret map Q(M)[t, a] = M[t, a] - min_b M[t, b]."""
    values = np.asarray(loss, dtype=float)
    return values - np.min(values, axis=1, keepdims=True)


def cancellation_native_gate(
    delta: np.ndarray,
    mu: np.ndarray,
    ratio: float,
    structural_loss: np.ndarray,
    route_loss: np.ndarray,
    ratio_tol: float = CANCELLATION_DELTA_RATIO_TOLERANCE,
) -> dict[str, Any]:
    """Per-round C4 evaluation in the native scale of ``delta = alpha_dep * mu``.

    The ratio ``delta / mu`` is only a normalized representation of the native
    identity and becomes ill-conditioned when ``mu`` is tiny, where one machine
    ulp of ``delta`` is magnified into a large ratio error. The hard gate is
    therefore the native equality with tolerance

        native_tolerance = ratio_tol * mu + roundoff_floor
        roundoff_floor   = 32 * eps * max(1, max|L_row|, max|L_route_row|)

    and the normalized ratio gate is applied only to ratio-conditioned rounds
    (``mu >= roundoff_floor / ratio_tol``). On non-conditioned rounds the ratio is
    retained as a diagnostic with ``ratio_gate_applicable = False`` and never
    fails C4 by normalization alone. ``ratio_tol`` and the safety factor are
    frozen constants; no branch special-cases ``alpha_dep = 0``.
    """
    machine_eps = float(np.finfo(float).eps)
    local_scale = np.maximum.reduce(
        [
            np.ones_like(mu, dtype=float),
            np.max(np.abs(structural_loss), axis=1),
            np.max(np.abs(route_loss), axis=1),
        ]
    )
    roundoff_floor = CANCELLATION_ROUNDOFF_SAFETY_FACTOR * machine_eps * local_scale
    expected_delta = ratio * mu
    abs_error = np.abs(np.asarray(delta, dtype=float) - expected_delta)
    native_tolerance = ratio_tol * mu + roundoff_floor
    condition_threshold = (
        roundoff_floor / ratio_tol
        if ratio_tol > 0.0
        else np.full_like(mu, np.inf, dtype=float)
    )
    conditioned = mu >= condition_threshold
    ratio_error = np.abs(np.asarray(delta, dtype=float) / mu - ratio)
    ratio_allowance = np.where(conditioned, ratio_tol + roundoff_floor / mu, np.inf)
    return {
        "machine_eps": machine_eps,
        "roundoff_safety_factor": float(CANCELLATION_ROUNDOFF_SAFETY_FACTOR),
        "local_scale": local_scale,
        "roundoff_floor": roundoff_floor,
        "expected_delta": expected_delta,
        "abs_error": abs_error,
        "native_tolerance": native_tolerance,
        "native_pass": bool(np.all(abs_error <= native_tolerance)),
        "condition_threshold": condition_threshold,
        "ratio_conditioned": conditioned,
        "ratio_gate_applicable": conditioned,
        "ratio_error": ratio_error,
        "ratio_allowance": ratio_allowance,
        "ratio_pass": bool(np.all(ratio_error[conditioned] <= ratio_allowance[conditioned])),
    }


def _cancellation_structural_audit() -> dict[str, int]:
    """Static AST audit behind Gate C6 for the cancellation sweep.

    The cancellation diagnostic must stay clip-free, learner-free and free of
    any artifact write. The sweep and its helpers are parsed from this module
    and forbidden call names are counted; every count must be zero. This is a
    structural audit of the executed code path, not an assertion about it.
    """
    source = "\n".join(
        textwrap.dedent(inspect.getsource(function))
        for function in (
            cancellation_sweep_rows,
            _shared_component,
            _actionwise_regret_map,
        )
    )
    counts = {"clipping_calls": 0, "learner_calls": 0, "write_calls": 0}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Attribute):
            name = target.attr
        elif isinstance(target, ast.Name):
            name = target.id
        else:
            continue
        category = _CANCELLATION_FORBIDDEN_CALLS.get(name)
        if category is not None:
            counts[f"{category}_calls"] += 1
    return counts


def cancellation_sweep_rows(
    structural_config: StructuralConfig,
    seeds: tuple[int, ...],
    shared_scales: tuple[float, ...] = THEORY_SWEEP.cancellation_shared_scales,
    dep_ratios: tuple[float, ...] = THEORY_SWEEP.cancellation_dep_ratios,
    shared_profiles: tuple[str, ...] = THEORY_SWEEP.cancellation_shared_profiles,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Matched shared-vs-action-dependent cancellation sweep (route-map only).

    On every supported round (exactly one structural optimum and finite
    positive structural margin) the candidate route map is

        L_route[t, a] = L[t, a] + alpha_shared * c_t + u_t[a]

    with c_t the action-invariant shared profile and u_t the best/nearest-
    competitor residual of the margin sweep (d = alpha_dep * mu, +d/2 on the
    unique best and -d/2 on the deterministic nearest competitor). The shared
    term is identical for every action of the round. Nothing is clipped, no
    learner is called, and no artifact is written here.
    """
    scales = tuple(float(scale) for scale in shared_scales)
    ratios = tuple(float(ratio) for ratio in dep_ratios)
    profiles = tuple(str(profile) for profile in shared_profiles)
    if CANCELLATION_REFERENCE_PROFILE not in profiles:
        raise ValueError("cancellation sweep requires the static_shared profile")
    if CANCELLATION_REFERENCE_SHARED_SCALE not in scales:
        raise ValueError("cancellation sweep requires the alpha_shared = 0 reference cell")

    rows: list[dict[str, Any]] = []
    eligible_support_total = 0
    c1_cells = 0
    c1_max_delta = 0.0
    c1_max_mean_rho = 0.0
    c1_max_mean_chi = 0.0
    c1_max_complete_conflict_rate = 0.0
    c1_max_regret_map_linf = 0.0
    c1_mask_mismatches = 0
    c2_pairs = 0
    c2_max_deviation = 0.0
    c2_mask_mismatches = 0
    c3_pairs = 0
    c3_max_deviation = 0.0
    c3_mask_mismatches = 0
    c4_round_evaluations = 0
    c4_max_deviation = 0.0
    c4_native_pass = True
    c4_ratio_pass = True
    c4_native_max_abs_error = 0.0
    c4_native_max_tolerance_ratio = 0.0
    c4_conditioned_rounds = 0
    c4_unconditioned_rounds = 0
    c4_ratio_max_error_conditioned = 0.0
    c4_ratio_max_error_all = 0.0
    c4_condition_threshold_min = float("inf")
    c4_condition_threshold_max = 0.0
    c5_cells = 0
    c5_max_deviation = 0.0
    reference_max_deviation = 0.0
    reference_mask_mismatches = 0

    for seed in seeds:
        base = generate_smooth_bounded_ar1_path(structural_config, int(seed))
        evaluation = _evaluation_slice(base)
        structural_loss = base.structural_loss_matrix[evaluation].copy()
        structural_state = base.structural_state[evaluation].copy()
        eligible = _eligible_rounds(structural_loss)
        positions = np.flatnonzero(eligible)
        if positions.size == 0:
            raise ScientificInvariantError(
                f"cancellation sweep has no supported round for seed {int(seed)}"
            )
        supported_loss = structural_loss[positions]
        supported_state = structural_state[positions]
        n_rounds = int(supported_loss.shape[0])
        eligible_support_total += n_rounds
        round_index = np.arange(n_rounds)
        structural_best = np.argmin(supported_loss, axis=1)
        competitor = np.asarray(
            [
                _nearest_competitor(supported_loss[i], int(structural_best[i]))
                for i in range(n_rounds)
            ],
            dtype=int,
        )
        mu = (
            supported_loss[round_index, competitor]
            - supported_loss[round_index, structural_best]
        )
        if not bool(np.all(mu > 0.0)):
            raise ScientificInvariantError(
                f"cancellation sweep supported rounds must have a positive margin (seed {int(seed)})"
            )
        structural_map = _actionwise_regret_map(supported_loss)
        structural_mask = optimal_mask(supported_loss)

        for ratio in ratios:
            residual = np.zeros_like(supported_loss)
            residual[round_index, structural_best] = 0.5 * ratio * mu
            residual[round_index, competitor] = -0.5 * ratio * mu

            cells: dict[tuple[str, float], dict[str, Any]] = {}
            for profile in profiles:
                shared = _shared_component(profile, supported_state)
                for scale in scales:
                    route_loss = supported_loss + (scale * shared)[:, None] + residual
                    route_map = _actionwise_regret_map(route_loss)
                    route_mask = optimal_mask(route_loss)
                    cells[(profile, scale)] = {
                        "delta": action_gap_defect(route_loss, supported_loss),
                        "rho": pairwise_sign_disagreement(route_loss, supported_loss),
                        "chi": directed_choice_disagreement(route_loss, supported_loss),
                        "complete_conflict": complete_conflict_indicator(
                            route_loss, supported_loss
                        ),
                        "regret_map": route_map,
                        "optimal_mask": route_mask,
                        "level_error": float(
                            np.mean(np.abs(route_loss - supported_loss))
                        ),
                        "regret_map_linf_to_structural": float(
                            np.max(np.abs(route_map - structural_map))
                        ),
                        "mask_mismatch_to_structural": int(
                            np.sum(np.any(route_mask != structural_mask, axis=1))
                        ),
                        "shared_min": float(np.min(shared)),
                        "shared_max": float(np.max(shared)),
                    }

            reference = cells[
                (CANCELLATION_REFERENCE_PROFILE, CANCELLATION_REFERENCE_SHARED_SCALE)
            ]
            reference_mask = reference["optimal_mask"]

            for profile in profiles:
                scale_reference = cells[(profile, CANCELLATION_REFERENCE_SHARED_SCALE)]
                profile_reference = cells[
                    (CANCELLATION_REFERENCE_PROFILE, CANCELLATION_REFERENCE_SHARED_SCALE)
                ]
                for scale in scales:
                    cell = cells[(profile, scale)]
                    is_reference = (
                        profile == CANCELLATION_REFERENCE_PROFILE
                        and scale == CANCELLATION_REFERENCE_SHARED_SCALE
                    )
                    if is_reference:
                        delta_linf = rho_linf = chi_linf = regret_linf = 0.0
                        reference_mismatches = 0
                    else:
                        delta_linf = float(
                            np.max(np.abs(cell["delta"] - reference["delta"]))
                        )
                        rho_linf = float(
                            np.max(np.abs(cell["rho"] - reference["rho"]))
                        )
                        chi_linf = float(
                            np.max(np.abs(cell["chi"] - reference["chi"]))
                        )
                        regret_linf = float(
                            np.max(
                                np.abs(cell["regret_map"] - reference["regret_map"])
                            )
                        )
                        reference_mismatches = int(
                            np.sum(
                                np.any(
                                    cell["optimal_mask"] != reference_mask,
                                    axis=1,
                                )
                            )
                        )
                    delta_over_mu_deviation = float(
                        np.max(np.abs(cell["delta"] / mu - ratio))
                    )
                    alignment_budget = float(np.sum(cell["delta"]))
                    mean_chi = float(np.mean(cell["chi"]))
                    rows.append(
                        {
                            "cancellation_sweep_id": CANCELLATION_SWEEP_ID,
                            "seed": int(seed),
                            "shared_profile": profile,
                            "alpha_shared": float(scale),
                            "alpha_dep": float(ratio),
                            "eligible_rounds": n_rounds,
                            "mean_absolute_actionwise_level_error": cell["level_error"],
                            "mean_delta": float(np.mean(cell["delta"])),
                            "max_delta": float(np.max(cell["delta"])),
                            "alignment_budget": alignment_budget,
                            "alignment_budget_rate": alignment_budget / n_rounds,
                            "mean_rho": float(np.mean(cell["rho"])),
                            "mean_chi": mean_chi,
                            "complete_conflict_rate": float(
                                np.mean(cell["complete_conflict"])
                            ),
                            "regret_map_linf_to_structural": cell[
                                "regret_map_linf_to_structural"
                            ],
                            "optimal_mask_mismatch_count_to_structural": cell[
                                "mask_mismatch_to_structural"
                            ],
                            "delta_linf_to_shared_reference": delta_linf,
                            "rho_linf_to_shared_reference": rho_linf,
                            "chi_linf_to_shared_reference": chi_linf,
                            "regret_map_linf_to_shared_reference": regret_linf,
                            "optimal_mask_mismatch_count_to_shared_reference": (
                                reference_mismatches
                            ),
                            "max_delta_over_mu_deviation": delta_over_mu_deviation,
                            "shared_component_min": cell["shared_min"],
                            "shared_component_max": cell["shared_max"],
                            "structural_path_hash": base.path_hash,
                        }
                    )

                    # Gate C1: pure shared perturbation (no action-dependent term).
                    if ratio == 0.0:
                        c1_cells += 1
                        c1_max_delta = max(c1_max_delta, float(np.max(cell["delta"])))
                        c1_max_mean_rho = max(
                            c1_max_mean_rho, float(np.mean(cell["rho"]))
                        )
                        c1_max_mean_chi = max(c1_max_mean_chi, mean_chi)
                        c1_max_complete_conflict_rate = max(
                            c1_max_complete_conflict_rate,
                            float(np.mean(cell["complete_conflict"])),
                        )
                        c1_max_regret_map_linf = max(
                            c1_max_regret_map_linf,
                            cell["regret_map_linf_to_structural"],
                        )
                        c1_mask_mismatches += cell["mask_mismatch_to_structural"]

                    # Gate C2: shared-amplitude invariance within a profile.
                    if scale != CANCELLATION_REFERENCE_SHARED_SCALE:
                        c2_pairs += 1
                        c2_max_deviation = max(
                            c2_max_deviation,
                            float(
                                np.max(
                                    np.abs(cell["delta"] - scale_reference["delta"])
                                )
                            ),
                            float(
                                np.max(np.abs(cell["rho"] - scale_reference["rho"]))
                            ),
                            float(
                                np.max(np.abs(cell["chi"] - scale_reference["chi"]))
                            ),
                            float(
                                np.max(
                                    np.abs(
                                        cell["regret_map"]
                                        - scale_reference["regret_map"]
                                    )
                                )
                            ),
                        )
                        c2_mask_mismatches += int(
                            np.sum(
                                np.any(
                                    cell["optimal_mask"]
                                    != scale_reference["optimal_mask"],
                                    axis=1,
                                )
                            )
                        )

                    # Gate C3: static vs state-varying profile invariance.
                    if profile != CANCELLATION_REFERENCE_PROFILE:
                        c3_pairs += 1
                        c3_max_deviation = max(
                            c3_max_deviation,
                            float(
                                np.max(
                                    np.abs(cell["delta"] - profile_reference["delta"])
                                )
                            ),
                            float(
                                np.max(
                                    np.abs(cell["rho"] - profile_reference["rho"])
                                )
                            ),
                            float(
                                np.max(
                                    np.abs(cell["chi"] - profile_reference["chi"])
                                )
                            ),
                            float(
                                np.max(
                                    np.abs(
                                        cell["regret_map"]
                                        - profile_reference["regret_map"]
                                    )
                                )
                            ),
                        )
                        c3_mask_mismatches += int(
                            np.sum(
                                np.any(
                                    cell["optimal_mask"]
                                    != profile_reference["optimal_mask"],
                                    axis=1,
                                )
                            )
                        )

                    reference_max_deviation = max(
                        reference_max_deviation,
                        delta_linf,
                        rho_linf,
                        chi_linf,
                        regret_linf,
                    )
                    reference_mask_mismatches += reference_mismatches

                    # Gate C4: native identity delta = alpha_dep * mu, with the
                    # normalized ratio applied only where it is conditioned.
                    c4_gate = cancellation_native_gate(
                        cell["delta"], mu, ratio, supported_loss, route_loss
                    )
                    c4_conditioned = c4_gate["ratio_conditioned"]
                    c4_round_evaluations += n_rounds
                    c4_max_deviation = max(c4_max_deviation, delta_over_mu_deviation)
                    c4_native_pass = c4_native_pass and c4_gate["native_pass"]
                    c4_ratio_pass = c4_ratio_pass and c4_gate["ratio_pass"]
                    c4_conditioned_rounds += int(np.count_nonzero(c4_conditioned))
                    c4_unconditioned_rounds += int(np.count_nonzero(~c4_conditioned))
                    c4_native_max_abs_error = max(
                        c4_native_max_abs_error, float(np.max(c4_gate["abs_error"]))
                    )
                    c4_native_max_tolerance_ratio = max(
                        c4_native_max_tolerance_ratio,
                        float(np.max(c4_gate["abs_error"] / c4_gate["native_tolerance"])),
                    )
                    c4_ratio_max_error_all = max(
                        c4_ratio_max_error_all,
                        float(np.max(c4_gate["ratio_error"])),
                    )
                    if bool(np.any(c4_conditioned)):
                        c4_ratio_max_error_conditioned = max(
                            c4_ratio_max_error_conditioned,
                            float(
                                np.max(c4_gate["ratio_error"][c4_conditioned])
                            ),
                        )
                    c4_condition_threshold_min = min(
                        c4_condition_threshold_min,
                        float(np.min(c4_gate["condition_threshold"])),
                    )
                    c4_condition_threshold_max = max(
                        c4_condition_threshold_max,
                        float(np.max(c4_gate["condition_threshold"])),
                    )

                    # Gate C5: exact choice-threshold semantics around alpha_dep = 1.
                    expected_chi = (
                        0.0 if ratio < 1.0 else (0.5 if ratio == 1.0 else 1.0)
                    )
                    c5_cells += 1
                    c5_max_deviation = max(
                        c5_max_deviation, abs(mean_chi - expected_chi)
                    )

    audit = _cancellation_structural_audit()
    mechanism_order_intact = bool(not set(profiles) & set(MECHANISM_ORDER))
    max_numerical_deviation = float(
        max(
            c1_max_delta,
            c1_max_mean_rho,
            c1_max_mean_chi,
            c1_max_complete_conflict_rate,
            c1_max_regret_map_linf,
            c2_max_deviation,
            c3_max_deviation,
            c4_native_max_abs_error,
            c5_max_deviation,
            reference_max_deviation,
        )
    )
    c1_passed = bool(
        c1_cells > 0
        and c1_max_delta <= SWEEP_TOLERANCE
        and c1_max_mean_rho <= SWEEP_TOLERANCE
        and c1_max_mean_chi <= SWEEP_TOLERANCE
        and c1_max_complete_conflict_rate <= SWEEP_TOLERANCE
        and c1_max_regret_map_linf <= SWEEP_TOLERANCE
        and c1_mask_mismatches == 0
    )
    c2_passed = bool(
        c2_pairs > 0
        and c2_max_deviation <= SWEEP_TOLERANCE
        and c2_mask_mismatches == 0
    )
    c3_passed = bool(
        c3_pairs > 0
        and c3_max_deviation <= SWEEP_TOLERANCE
        and c3_mask_mismatches == 0
    )
    c4_passed = bool(
        c4_round_evaluations > 0 and c4_native_pass and c4_ratio_pass
    )
    if not np.isfinite(c4_condition_threshold_min):
        c4_condition_threshold_min = 0.0
    c5_passed = bool(c5_cells > 0 and c5_max_deviation <= SWEEP_TOLERANCE)
    c6_passed = bool(
        all(count == 0 for count in audit.values()) and mechanism_order_intact
    )
    checks = {
        "sweep_id": CANCELLATION_SWEEP_ID,
        "shared_scales": list(scales),
        "dep_ratios": list(ratios),
        "shared_profiles": list(profiles),
        "reference_cell": {
            "shared_profile": CANCELLATION_REFERENCE_PROFILE,
            "alpha_shared": CANCELLATION_REFERENCE_SHARED_SCALE,
        },
        "grid_cells_per_seed": len(profiles) * len(scales) * len(ratios),
        "n_seeds": len(seeds),
        "n_cells": len(rows),
        "eligible_round_support_total": eligible_support_total,
        "tolerance": SWEEP_TOLERANCE,
        "delta_ratio_tolerance": CANCELLATION_DELTA_RATIO_TOLERANCE,
        "max_numerical_deviation": max_numerical_deviation,
        "reference_agreement_max_deviation": float(reference_max_deviation),
        "reference_agreement_mask_mismatches": int(reference_mask_mismatches),
        "C1_pure_shared": {
            "passed": c1_passed,
            "cells": c1_cells,
            "max_delta": float(c1_max_delta),
            "max_mean_rho": float(c1_max_mean_rho),
            "max_mean_chi": float(c1_max_mean_chi),
            "max_complete_conflict_rate": float(c1_max_complete_conflict_rate),
            "max_regret_map_linf_to_structural": float(c1_max_regret_map_linf),
            "optimal_mask_mismatch_count_to_structural": int(c1_mask_mismatches),
        },
        "C2_shared_amplitude_invariance": {
            "passed": c2_passed,
            "cells_compared": c2_pairs,
            "max_deviation": float(c2_max_deviation),
            "optimal_mask_mismatch_count": int(c2_mask_mismatches),
        },
        "C3_profile_invariance": {
            "passed": c3_passed,
            "cells_compared": c3_pairs,
            "max_deviation": float(c3_max_deviation),
            "optimal_mask_mismatch_count": int(c3_mask_mismatches),
        },
        "C4_delta_margin_ratio": {
            "passed": c4_passed,
            "c4_native_identity_pass": bool(c4_native_pass),
            "c4_native_max_abs_error": float(c4_native_max_abs_error),
            "c4_native_max_tolerance_ratio": float(c4_native_max_tolerance_ratio),
            "c4_ratio_conditioned_pass": bool(c4_ratio_pass),
            "c4_ratio_conditioned_rounds": int(c4_conditioned_rounds),
            "c4_ratio_unconditioned_rounds": int(c4_unconditioned_rounds),
            "c4_ratio_condition_threshold_min": float(c4_condition_threshold_min),
            "c4_ratio_condition_threshold_max": float(c4_condition_threshold_max),
            "c4_ratio_max_error_conditioned": float(c4_ratio_max_error_conditioned),
            "c4_ratio_max_error_all_diagnostic": float(c4_ratio_max_error_all),
            "round_evaluations": int(c4_round_evaluations),
            "max_absolute_deviation": float(c4_max_deviation),
            "ratio_tol": CANCELLATION_DELTA_RATIO_TOLERANCE,
            "roundoff_safety_factor": float(CANCELLATION_ROUNDOFF_SAFETY_FACTOR),
            "machine_eps": float(np.finfo(float).eps),
        },
        "C5_choice_threshold": {
            "passed": c5_passed,
            "cells": c5_cells,
            "max_absolute_deviation": float(c5_max_deviation),
        },
        "C6_no_clipping_no_learner": {
            "passed": c6_passed,
            "counts": audit,
            "mechanism_order_intact": mechanism_order_intact,
            "mechanism_order": list(MECHANISM_ORDER),
            "artifact_writes": 0,
            "primary_raw_writes": 0,
            "primary_seed_metrics_writes": 0,
        },
    }
    checks["passed"] = bool(
        rows
        and eligible_support_total > 0
        and c1_passed
        and c2_passed
        and c3_passed
        and c4_passed
        and c5_passed
        and c6_passed
    )
    return rows, checks
def run_invariant_checks(
    structural_config: StructuralConfig,
    seeds: tuple[int, ...],
    geometric_probability: float,
    delay_config: DelayConfig,
) -> dict[str, Any]:
    """Independent theorem-sweep invariant checks for self_check integration."""
    _, exact_checks = exact_shift_sweep_rows(
        structural_config, seeds, geometric_probability, delay_config
    )
    _, margin_checks = margin_threshold_sweep_rows(structural_config, seeds)
    _, cancellation_checks = cancellation_sweep_rows(structural_config, seeds)
    return {
        "theory_exact_cardinal_shift_sweep": exact_checks,
        "theory_margin_threshold_sweep": margin_checks,
        "theory_cancellation_sweep": cancellation_checks,
        "all_theory_sweeps_pass": bool(
            exact_checks["passed"]
            and margin_checks["passed"]
            and cancellation_checks["passed"]
        ),
    }
