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
"""

from typing import Any

import numpy as np

from config import DelayConfig, StructuralConfig, THEORY_SWEEP
from src.artifact_io import hash_payload
from src.delay_mechanisms import generate_geometric_delay
from src.metrics import (
    action_gap_defect,
    directed_choice_disagreement,
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
    return {
        "theory_exact_cardinal_shift_sweep": exact_checks,
        "theory_margin_threshold_sweep": margin_checks,
        "all_theory_sweeps_pass": bool(
            exact_checks["passed"] and margin_checks["passed"]
        ),
    }
