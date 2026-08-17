"""Scientific unit tests for the final-theory Exp1 diagnostics (config v1.2).

These tests pin the final theoretical contract:

    delta_t = max_{a,b} |G_t^r(a,b) - G_t^c(a,b)|
    rho_t   = pairwise ordinal disagreement
    chi_t   = directed choice disagreement
    |R_T^c - R_T^r| <= A_T^r        (sharp regret stability)
    delta_t < mu_t^c => chi_t = 0   (strict inequality margin bridge)
"""

from __future__ import annotations

import numpy as np

from config import DELAY, FAST_STRUCTURAL, MECHANISM_ORDER, RUN, THEORY_SWEEP
from src.metrics import (
    action_gap_defect,
    action_gap_defect_bruteforce,
    complete_conflict_indicator,
    directed_choice_disagreement,
    margin_preservation,
    pairwise_sign_disagreement,
    ranking_reversal,
    regret_stability_slack,
    route_conflict_margin,
    route_regret_increment,
    structural_conflict_margin,
    structural_margin,
    structural_regret_increment,
    ternary_sign,
    transfer_slack,
)
from src.structural_process import (
    generate_exact_valid_shift_path,
    generate_smooth_bounded_ar1_path,
)
from src.theory_sweeps import exact_shift_sweep_rows, margin_threshold_sweep_rows


# ---------------------------------------------------------------------------
# 1. Fast formula == brute-force formula
# ---------------------------------------------------------------------------
def test_action_gap_defect_fast_equals_bruteforce() -> None:
    rng = np.random.default_rng(3)
    for _ in range(10):
        structural = rng.uniform(0.0, 1.0, size=(40, 8))
        route = rng.uniform(0.0, 1.0, size=(40, 8))
        assert np.allclose(
            action_gap_defect(route, structural),
            action_gap_defect_bruteforce(route, structural),
            atol=1e-12,
        )


def test_ternary_sign_semantics() -> None:
    values = np.array([0.5, 1e-14, 0.0, -1e-14, -0.5])
    assert np.array_equal(ternary_sign(values), np.array([1, 0, 0, 0, -1]))


# ---------------------------------------------------------------------------
# 2. Action-invariant shift: delta = rho = chi = 0
# ---------------------------------------------------------------------------
def test_action_invariant_shift_gives_all_zero() -> None:
    structural = np.array([[0.1, 0.3, 0.8], [0.2, 0.4, 0.7]])
    route = structural + np.array([[0.55], [-0.20]])
    assert np.allclose(action_gap_defect(route, structural), 0.0, atol=1e-15)
    assert np.allclose(pairwise_sign_disagreement(route, structural), 0.0)
    assert np.allclose(directed_choice_disagreement(route, structural), 0.0)


# ---------------------------------------------------------------------------
# 3. Validity hierarchy example: delta > 0, rho = 0, chi = 0
# ---------------------------------------------------------------------------
def test_validity_hierarchy_delta_positive_with_rho_chi_zero() -> None:
    structural = np.array([[0.0, 1.0]])
    route = np.array([[0.0, 2.0]])
    delta = action_gap_defect(route, structural)[0]
    rho = pairwise_sign_disagreement(route, structural)[0]
    chi = directed_choice_disagreement(route, structural)[0]
    assert delta > 0
    assert rho == 0
    assert chi == 0


# ---------------------------------------------------------------------------
# 4. Ordinal-with-choice-preserved: rho > 0, chi = 0
# ---------------------------------------------------------------------------
def test_ordinal_disagreement_with_choice_preserved() -> None:
    structural = np.array([[0.0, 1.0, 2.0]])
    route = np.array([[0.0, 2.0, 1.0]])
    rho = pairwise_sign_disagreement(route, structural)[0]
    chi = directed_choice_disagreement(route, structural)[0]
    assert rho > 0
    assert chi == 0


# ---------------------------------------------------------------------------
# 5. Complete reversal: rho = 1, chi = 1
# ---------------------------------------------------------------------------
def test_complete_reversal() -> None:
    structural = np.array([[0.0, 1.0]])
    route = np.array([[1.0, 0.0]])
    assert pairwise_sign_disagreement(route, structural)[0] == 1.0
    assert directed_choice_disagreement(route, structural)[0] == 1.0


# ---------------------------------------------------------------------------
# 6. Partial optimal-set disagreement: chi = 1/2
# ---------------------------------------------------------------------------
def test_partial_optimal_set_disagreement() -> None:
    structural = np.array([[0.0, 0.0, 1.0]])
    route = np.array([[0.0, 1.0, 0.0]])
    assert directed_choice_disagreement(route, structural)[0] == 0.5


# ---------------------------------------------------------------------------
# 7. ranking_reversal == (chi > 0)
# 8. complete_conflict == (chi == 1)
# ---------------------------------------------------------------------------
def test_ranking_reversal_equals_positive_chi() -> None:
    rng = np.random.default_rng(9)
    for _ in range(20):
        structural = rng.uniform(0.0, 1.0, size=(60, 6))
        route = rng.uniform(0.0, 1.0, size=(60, 6))
        chi = directed_choice_disagreement(route, structural)
        assert np.array_equal(ranking_reversal(route, structural), chi > 0.0)


def test_complete_conflict_equals_unit_chi() -> None:
    rng = np.random.default_rng(10)
    for _ in range(20):
        structural = rng.uniform(0.0, 1.0, size=(60, 6))
        route = rng.uniform(0.0, 1.0, size=(60, 6))
        chi = directed_choice_disagreement(route, structural)
        assert np.array_equal(
            complete_conflict_indicator(route, structural),
            np.isclose(chi, 1.0, atol=1e-15, rtol=0.0),
        )


# ---------------------------------------------------------------------------
# 9. Margin bridge: delta < mu => chi = 0
# ---------------------------------------------------------------------------
def test_margin_bridge_delta_below_margin_preserves_choice() -> None:
    structural = np.array([[0.0, 1.0, 2.0], [1.0, 1.5, 2.0]])
    mu = structural_margin(structural)
    assert np.all(np.isfinite(mu)) and np.all(mu > 0)
    # Small perturbations strictly below the margin.
    route = np.array([[0.2, 0.9, 2.0], [1.1, 1.6, 1.9]])
    delta = action_gap_defect(route, structural)
    assert np.all(delta < mu)
    assert np.all(directed_choice_disagreement(route, structural) == 0.0)
    assert np.all(margin_preservation(delta, mu))


# ---------------------------------------------------------------------------
# 10. Equality boundary: delta == mu is NOT guaranteed choice preservation
# ---------------------------------------------------------------------------
def test_margin_bridge_equality_boundary_is_not_preservation() -> None:
    structural = np.array([[0.0, 1.0]])
    route = np.array([[0.5, 0.5]])
    mu = structural_margin(structural)[0]  # 1.0
    delta = action_gap_defect(route, structural)[0]  # 1.0
    assert np.isclose(delta, mu)
    assert not margin_preservation(np.array([delta]), np.array([mu]))[0]
    # At equality a structurally suboptimal action becomes tied for route
    # optimum: chi is NOT guaranteed to be zero.
    chi = directed_choice_disagreement(route, structural)[0]
    assert chi == 0.5


# ---------------------------------------------------------------------------
# 11. Complete-conflict rounds: delta >= gamma + eta
# ---------------------------------------------------------------------------
def test_complete_conflict_margin_bound() -> None:
    structural = np.array([[0.0, 1.0]])
    route = np.array([[1.0, 0.0]])
    assert complete_conflict_indicator(route, structural)[0]
    gamma = structural_conflict_margin(route, structural)[0]  # 1.0
    eta = route_conflict_margin(route, structural)[0]  # 1.0
    delta = action_gap_defect(route, structural)[0]  # 2.0
    assert np.isclose(gamma, 1.0) and np.isclose(eta, 1.0)
    assert delta >= gamma + eta - 1e-12


def test_complete_conflict_margin_bound_random() -> None:
    rng = np.random.default_rng(12)
    for _ in range(20):
        structural = rng.uniform(0.0, 1.0, size=(80, 5))
        route = rng.uniform(0.0, 1.0, size=(80, 5))
        delta = action_gap_defect(route, structural)
        gamma = structural_conflict_margin(route, structural)
        eta = route_conflict_margin(route, structural)
        conflict = complete_conflict_indicator(route, structural)
        for t in np.flatnonzero(conflict):
            assert delta[t] >= gamma[t] + eta[t] - 1e-12


def test_conflict_margins_nan_outside_complete_conflict() -> None:
    structural = np.array([[0.0, 1.0], [0.0, 0.0]])
    route = np.array([[0.5, 0.6], [0.0, 0.0]])
    gamma = structural_conflict_margin(route, structural)
    eta = route_conflict_margin(route, structural)
    assert np.isnan(gamma[0]) and np.isnan(eta[0])
    assert np.isnan(gamma[1]) and np.isnan(eta[1])


def test_eta_not_manufactured_when_every_route_action_optimal() -> None:
    structural = np.array([[0.0, 1.0]])
    route = np.array([[0.0, 0.0]])  # every route action optimal
    assert not complete_conflict_indicator(route, structural)[0]
    eta = route_conflict_margin(route, structural)
    assert np.isnan(eta[0])


# ---------------------------------------------------------------------------
# 12. Regret stability for deterministic and random action sequences
# ---------------------------------------------------------------------------
def test_regret_stability_deterministic_and_random() -> None:
    rng = np.random.default_rng(13)
    structural = rng.uniform(0.0, 1.0, size=(200, 6))
    route = rng.uniform(0.0, 1.0, size=(200, 6))
    delta = action_gap_defect(route, structural)
    alignment_budget = float(np.sum(delta))
    for deterministic in (True, False):
        if deterministic:
            actions = np.argmin(structural, axis=1)
        else:
            actions = rng.integers(0, structural.shape[1], size=structural.shape[0])
        structural_regret = float(np.sum(structural_regret_increment(actions, structural)))
        route_regret = float(np.sum(route_regret_increment(actions, route)))
        assert abs(structural_regret - route_regret) <= alignment_budget + 1e-9
        rate, tolerance = regret_stability_slack(
            structural_regret, route_regret, alignment_budget, structural.shape[0]
        )
        assert rate >= -tolerance


def test_transfer_slack_one_sided_still_available() -> None:
    rate, _ = transfer_slack(0.3, 0.5, 0.4, 100)
    assert np.isclose(rate, (0.5 + 0.4 - 0.3) / 100)


# ---------------------------------------------------------------------------
# 13. Default shift path is scientifically identical to explicit g/c scales
# ---------------------------------------------------------------------------
def test_default_exact_shift_matches_explicit_scales() -> None:
    config = FAST_STRUCTURAL
    base = generate_smooth_bounded_ar1_path(config, 20000)
    default = generate_exact_valid_shift_path(base)
    explicit = generate_exact_valid_shift_path(base, g_scale=0.6, c_scale=0.1)
    assert np.array_equal(default.structural_loss_matrix, explicit.structural_loss_matrix)
    assert default.path_hash == explicit.path_hash
    assert default.parameter_payload["g_scale"] == 0.6
    assert default.parameter_payload["c_scale"] == 0.1


# ---------------------------------------------------------------------------
# 14. Exact-cardinal shift sweep: all delta/rho/chi zero
# ---------------------------------------------------------------------------
def test_exact_cardinal_shift_sweep_all_zero() -> None:
    config = FAST_STRUCTURAL
    rows, checks = exact_shift_sweep_rows(
        config,
        RUN.fast_seeds,
        geometric_probability=0.06188280296766341,
        delay_config=DELAY,
        scales=THEORY_SWEEP.exact_shift_scales,
    )
    assert rows
    assert checks["passed"]
    assert checks["delta_all_zero"] and checks["rho_all_zero"] and checks["chi_all_zero"]
    # Raw actionwise level error may grow with c_scale while validity holds.
    by_scale = {}
    for row in rows:
        by_scale.setdefault(row["c_scale"], []).append(row["mean_absolute_actionwise_level_error"])
    means = {scale: float(np.mean(values)) for scale, values in by_scale.items()}
    assert means[0.0] < means[0.05] < means[0.10] < means[0.20]


# ---------------------------------------------------------------------------
# 15. Margin sweep: realized delta/mu == prespecified ratio; threshold
# ---------------------------------------------------------------------------
def test_margin_threshold_sweep_ratios_and_thresholds() -> None:
    config = FAST_STRUCTURAL
    rows, checks = margin_threshold_sweep_rows(
        config, RUN.fast_seeds, ratios=THEORY_SWEEP.margin_distortion_ratios
    )
    assert rows
    assert checks["passed"]
    assert checks["realized_delta_over_mu_matches_ratio"]
    assert checks["threshold_behavior_correct"]
    assert checks["no_clipping"]
    for row in rows:
        ratio = row["ratio"]
        if ratio < 1.0:
            assert np.isclose(row["mean_chi"], 0.0)
        elif ratio == 1.0:
            assert np.isclose(row["mean_chi"], 0.5)
        else:
            assert np.isclose(row["mean_chi"], 1.0)


def test_margin_sweep_single_round_construction() -> None:
    """Verify the perturbation construction on one hand-built round."""
    structural = np.array([[0.2, 0.5, 0.9]])
    best = int(np.argmin(structural[0]))  # 0
    competitor = 1
    mu = structural[0, competitor] - structural[0, best]  # 0.3
    r = 1.0
    d = r * mu
    error = np.zeros(3)
    error[best] = d / 2.0
    error[competitor] = -d / 2.0
    route = structural + error[None, :]
    delta = action_gap_defect(route, structural)[0]
    assert np.isclose(delta / mu, r)
    chi = directed_choice_disagreement(route, structural)[0]
    assert chi == 0.5
    # No clipping: perturbed losses stay within [0, 1] and within the
    # original best/competitor range.
    assert np.min(route) >= 0.0 - 1e-12 and np.max(route) <= 1.0 + 1e-12


# ---------------------------------------------------------------------------
# 16. MECHANISM_ORDER unchanged
# ---------------------------------------------------------------------------
def test_mechanism_order_frozen() -> None:
    assert MECHANISM_ORDER == (
        "zero_delay",
        "exact_valid_shift",
        "geometric_delay",
        "mixture_delay",
        "state_coupled_delay",
        "systematic_misbinding",
    )
