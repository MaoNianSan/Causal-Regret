"""Cancellation sweep and realized stability-utilization tests (Exp1, V2).

These tests pin the authorized targeted diagnostics of the 2026-09-10
execution instruction:

    L_route[t, a] = L[t, a] + alpha_shared * c_t + u_t[a]

with the action-invariant shared profile ``c_t`` (``static_shared`` = 1,
``state_varying_shared`` = 1 + S_t) and the best/nearest-competitor residual
``u_t`` of the margin sweep, plus the realized stability utilization

    regret_stability_utilization = abs(R_c - R_r) / A

defined only when the alignment budget exceeds the derived tolerance
``stability_tolerance_rate * T``. Below that the ratio is NaN with
``utilization_defined = False`` and is never reported as a manufactured zero.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import FAST_STRUCTURAL, MECHANISM_ORDER, RUN, THEORY_SWEEP
from src.contracts import ScientificInvariantError
from src.derived import regret_stability_utilization
from src.metrics import (
    action_gap_defect,
    complete_conflict_indicator,
    directed_choice_disagreement,
    optimal_mask,
    pairwise_sign_disagreement,
    regret_stability_slack,
)
from src.structural_process import generate_smooth_bounded_ar1_path
from src.theory_sweeps import (
    CANCELLATION_DELTA_RATIO_TOLERANCE,
    CANCELLATION_ROUNDOFF_SAFETY_FACTOR,
    CANCELLATION_SWEEP_ID,
    SWEEP_TOLERANCE,
    _actionwise_regret_map,
    _cancellation_structural_audit,
    _nearest_competitor,
    _shared_component,
    cancellation_native_gate,
    cancellation_sweep_rows,
)


# Frozen hashes of the primary Exp1 paper-candidate scientific artifacts as
# recorded before the 2026-09-10 targeted patch. They may only change under a
# separate human-authorized promotion, so this mapping is the preservation
# guard for the primary seed-level and derived files.
PRIMARY_PAPER_CANDIDATE_HASHES = {
    "seed_metrics/exp1_learner_seed_metrics.csv": (
        "bfdffe7ea89a4ffe144cd6705dc13136012a7c30b378fe836ed751401fca37a6"
    ),
    "seed_metrics/exp1_learner_seed_metrics.parquet": (
        "710f1a4a5ce672b8c17299d9c0f1a38e609601d9760189803990c9d7c807dd67"
    ),
    "seed_metrics/exp1_route_seed_metrics.csv": (
        "cd8b0b2ef7e692195d2bde5ca77a4603bea7860a1452151446519037d31577ec"
    ),
    "seed_metrics/exp1_route_seed_metrics.parquet": (
        "68c8ef244768d960b5c695ccd46e460e3cc94e87ed1a19aa943ac360dbaaa670"
    ),
    "derived/exp1_actual_learner_contrasts.csv": (
        "7aa7d92119fc4cd71ad5794e76a97e073001edc050b3d0da6d5faf38ed1d46ff"
    ),
    "derived/exp1_learner_summary.csv": (
        "9090e7ae0fc4b2dc3aabfb15f582bf1545a48d53c670703d8ba5f403700079b2"
    ),
    "derived/exp1_primary_summary.csv": (
        "06aad460decb680176a6c7c5eb639a920a0c9a4807353c9b4f138a481fee688e"
    ),
    "derived/exp1_route_summary.csv": (
        "d0e15e092d64affd40f143ff6aecbe066644b3ce3bf85bca48efd020e5691401"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _loss_matrix() -> np.ndarray:
    """Deterministic supported-round loss matrix: unique optima, positive margin."""
    return np.array(
        [
            [0.00, 0.40, 1.10],
            [0.70, 0.10, 0.90],
            [0.20, 0.60, 0.30],
            [1.30, 0.50, 0.00],
            [0.45, 0.15, 0.95],
        ],
        dtype=float,
    )


def _state_vector() -> np.ndarray:
    """Deterministic bounded structural-state slice on the same rounds."""
    return np.array([0.40, -0.70, 0.90, 0.00, -0.20], dtype=float)


def _residual(loss: np.ndarray, ratio: float) -> tuple[np.ndarray, np.ndarray]:
    """Best/nearest-competitor residual u_t and the structural margin mu_t."""
    rounds = np.arange(loss.shape[0])
    best = np.argmin(loss, axis=1)
    competitor = np.asarray(
        [_nearest_competitor(loss[i], int(best[i])) for i in rounds], dtype=int
    )
    mu = loss[rounds, competitor] - loss[rounds, best]
    assert np.all(mu > 0.0)
    residual = np.zeros_like(loss)
    residual[rounds, best] = 0.5 * ratio * mu
    residual[rounds, competitor] = -0.5 * ratio * mu
    return residual, mu


def _decision_objects(loss: np.ndarray, reference: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "delta": action_gap_defect(loss, reference),
        "rho": pairwise_sign_disagreement(loss, reference),
        "chi": directed_choice_disagreement(loss, reference),
        "complete_conflict": complete_conflict_indicator(loss, reference),
        "regret_map": _actionwise_regret_map(loss),
        "optimal_mask": optimal_mask(loss),
    }


def _assert_objects_equal(
    left: dict[str, np.ndarray], right: dict[str, np.ndarray]
) -> None:
    for key in sorted(left):
        np.testing.assert_allclose(
            np.asarray(left[key], dtype=float),
            np.asarray(right[key], dtype=float),
            atol=SWEEP_TOLERANCE,
            rtol=0.0,
            err_msg=f"decision object {key} changed under an action-invariant shift",
        )


# ---------------------------------------------------------------------------
# 1-2. Shared profiles preserve the decision objects
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alpha_shared", THEORY_SWEEP.cancellation_shared_scales)
def test_static_shared_shift_preserves_decision_objects(alpha_shared: float) -> None:
    loss = _loss_matrix()
    shared = _shared_component("static_shared", _state_vector())
    np.testing.assert_array_equal(shared, np.ones(loss.shape[0]))

    route = loss + (alpha_shared * shared)[:, None]
    _assert_objects_equal(
        _decision_objects(route, loss), _decision_objects(loss, loss)
    )
    # The level error grows with the shared amplitude while decisions do not.
    assert float(np.mean(np.abs(route - loss))) == pytest.approx(alpha_shared)


@pytest.mark.parametrize("alpha_shared", THEORY_SWEEP.cancellation_shared_scales)
def test_state_varying_shared_shift_preserves_decision_objects(
    alpha_shared: float,
) -> None:
    loss = _loss_matrix()
    state = _state_vector()
    shared = _shared_component("state_varying_shared", state)
    np.testing.assert_array_equal(shared, 1.0 + state)
    assert float(np.min(shared)) >= 0.0
    assert float(np.max(shared)) <= 2.0

    route = loss + (alpha_shared * shared)[:, None]
    _assert_objects_equal(
        _decision_objects(route, loss), _decision_objects(loss, loss)
    )

    # The shared term is added identically to every action of a round.
    error = route - loss
    assert float(np.max(error - error[:, :1])) <= SWEEP_TOLERANCE

    # The generated structural state itself satisfies the frozen 1 + S_t rule.
    path = generate_smooth_bounded_ar1_path(FAST_STRUCTURAL, RUN.fast_seeds[0])
    generated = _shared_component("state_varying_shared", path.structural_state)
    np.testing.assert_array_equal(generated, 1.0 + path.structural_state)


# ---------------------------------------------------------------------------
# 3-4. Shared shift on a nonzero residual, and profile equivalence
# ---------------------------------------------------------------------------
def test_shared_shift_on_nonzero_residual_preserves_residual_decision_objects() -> None:
    loss = _loss_matrix()
    state = _state_vector()
    residual, _mu = _residual(loss, 0.50)
    residual_route = loss + residual
    # The residual itself is not decision-neutral, so the comparison is not vacuous.
    assert float(np.mean(action_gap_defect(residual_route, loss))) > 0.0

    for profile in THEORY_SWEEP.cancellation_shared_profiles:
        shared = _shared_component(profile, state)
        for alpha_shared in THEORY_SWEEP.cancellation_shared_scales:
            route = residual_route + (alpha_shared * shared)[:, None]
            _assert_objects_equal(
                _decision_objects(route, loss),
                _decision_objects(residual_route, loss),
            )


def test_static_and_state_varying_profiles_match_at_fixed_residual() -> None:
    loss = _loss_matrix()
    state = _state_vector()
    for ratio in THEORY_SWEEP.cancellation_dep_ratios:
        residual, _mu = _residual(loss, ratio)
        for alpha_shared in THEORY_SWEEP.cancellation_shared_scales:
            static_route = (
                loss
                + (alpha_shared * _shared_component("static_shared", state))[:, None]
                + residual
            )
            state_route = (
                loss
                + (alpha_shared * _shared_component("state_varying_shared", state))[
                    :, None
                ]
                + residual
            )
            _assert_objects_equal(
                _decision_objects(state_route, loss),
                _decision_objects(static_route, loss),
            )


# ---------------------------------------------------------------------------
# 5-6. Residual amplitude and the choice threshold at 1
# ---------------------------------------------------------------------------
def test_c4_ordinary_margin_passes_native_and_conditioned_ratio_gates() -> None:
    structural = np.array([[0.10, 0.30, 0.80]])
    route = np.array([[0.15, 0.25, 0.80]])
    mu = np.array([0.20])
    delta = action_gap_defect(route, structural)
    gate = cancellation_native_gate(delta, mu, 0.50, structural, route)
    assert gate["native_pass"] is True
    assert bool(np.all(gate["ratio_gate_applicable"])) is True
    assert gate["ratio_pass"] is True
    assert float(gate["abs_error"][0]) <= float(gate["native_tolerance"][0])
    assert float(gate["ratio_error"][0]) <= CANCELLATION_DELTA_RATIO_TOLERANCE


def test_c4_tiny_margin_round_is_not_failed_by_normalization() -> None:
    structural = np.array([[0.0, 1e-7, 1.0]])
    route = structural.copy()
    mu = np.array([1e-7])
    # Intended value is exactly zero; only a one-ulp floating artefact remains.
    delta = np.array([np.finfo(float).eps])
    gate = cancellation_native_gate(delta, mu, 0.0, structural, route)
    assert gate["native_pass"] is True
    assert bool(gate["ratio_conditioned"][0]) is False
    assert bool(gate["ratio_gate_applicable"][0]) is False
    assert gate["ratio_pass"] is True
    # The same round fails the old unconditional ratio gate, hence the repair.
    assert float(gate["ratio_error"][0]) > CANCELLATION_DELTA_RATIO_TOLERANCE


def test_c4_wrong_delta_beyond_native_tolerance_fails() -> None:
    structural = np.array([[0.10, 0.30, 0.80]])
    route = np.array([[0.15, 0.25, 0.80]])
    mu = np.array([0.20])
    delta = action_gap_defect(route, structural) + 1e-6
    gate = cancellation_native_gate(delta, mu, 0.50, structural, route)
    assert gate["native_pass"] is False
    assert gate["ratio_pass"] is False


def test_c4_large_margin_ratio_error_beyond_tolerance_fails() -> None:
    structural = np.array([[0.0, 1.0, 5.0]])
    route = np.array([[0.5, 0.5, 5.0]])
    mu = np.array([1.0])
    delta = action_gap_defect(route, structural) + 1e-6
    gate = cancellation_native_gate(delta, mu, 1.0, structural, route)
    assert bool(gate["ratio_conditioned"][0]) is True
    assert gate["ratio_pass"] is False
    assert gate["native_pass"] is False


def test_c4_conditioned_rounds_keep_native_and_ratio_gates_equivalent() -> None:
    structural = np.array([[0.0, 1.0, 5.0], [0.2, 0.9, 4.0]])
    route = np.array([[0.5, 0.5, 5.0], [0.55, 0.55, 4.0]])
    mu = np.array([1.0, 0.7])
    delta = action_gap_defect(route, structural) + np.array([1e-7, -5e-8])
    gate = cancellation_native_gate(delta, mu, 1.0, structural, route)
    conditioned = gate["ratio_conditioned"]
    assert bool(np.all(conditioned)) is True
    native_ok = gate["abs_error"] <= gate["native_tolerance"]
    ratio_ok = gate["ratio_error"] <= gate["ratio_allowance"]
    np.testing.assert_array_equal(native_ok, ratio_ok)


def test_c4_alpha_dep_zero_is_not_exempt_and_not_spuriously_failed() -> None:
    structural = np.array([[0.10, 0.30, 0.80]])
    route = structural.copy()
    mu = np.array([0.20])
    # (a) alpha_dep = 0 is not exempt: a wrong delta must still fail the gate.
    wrong = cancellation_native_gate(np.array([1e-5]), mu, 0.0, structural, route)
    assert wrong["native_pass"] is False
    # (b) a one-ulp artefact on a tiny margin is not failed by normalization.
    tiny_structural = np.array([[0.0, 1e-7, 1.0]])
    tiny = cancellation_native_gate(
        np.array([np.finfo(float).eps]),
        np.array([1e-7]),
        0.0,
        tiny_structural,
        tiny_structural.copy(),
    )
    assert tiny["native_pass"] is True
    assert tiny["ratio_pass"] is True


def test_c4_alpha_dep_1_01_tiny_margin_uses_the_same_conditioning_rule() -> None:
    structural = np.array([[0.0, 1e-7, 1.0]])
    route = structural.copy()
    mu = np.array([1e-7])
    ulp = np.finfo(float).eps
    for ratio, intended in ((0.0, 0.0), (1.01, 1.01e-7)):
        gate = cancellation_native_gate(
            np.array([intended + ulp]), mu, ratio, structural, route
        )
        assert gate["native_pass"] is True
        assert bool(gate["ratio_conditioned"][0]) is False
        assert gate["ratio_pass"] is True
    assert CANCELLATION_ROUNDOFF_SAFETY_FACTOR == 32.0
    assert CANCELLATION_DELTA_RATIO_TOLERANCE == 1e-9


def test_realized_delta_over_mu_matches_configured_ratio() -> None:
    loss = _loss_matrix()
    for ratio in THEORY_SWEEP.cancellation_dep_ratios:
        residual, mu = _residual(loss, ratio)
        realized = action_gap_defect(loss + residual, loss) / mu
        np.testing.assert_allclose(
            realized,
            np.full(mu.shape, ratio),
            atol=CANCELLATION_DELTA_RATIO_TOLERANCE,
        )


def test_choice_threshold_semantics_around_one() -> None:
    loss = _loss_matrix()
    expected = {0.00: 0.0, 0.50: 0.0, 0.99: 0.0, 1.00: 0.5, 1.01: 1.0, 1.50: 1.0}
    assert set(expected) == set(THEORY_SWEEP.cancellation_dep_ratios)
    for ratio, chi in expected.items():
        residual, _mu = _residual(loss, ratio)
        np.testing.assert_allclose(
            directed_choice_disagreement(loss + residual, loss),
            np.full(loss.shape[0], chi),
            atol=1e-12,
        )
    # No closed form is imposed on rho beyond the pairwise-sign calculation.
    residual, _mu = _residual(loss, 0.50)
    np.testing.assert_allclose(
        pairwise_sign_disagreement(loss + residual, loss), np.zeros(loss.shape[0])
    )


# ---------------------------------------------------------------------------
# 7-9. Realized stability-utilization definition, tolerance and range
# ---------------------------------------------------------------------------
def test_utilization_undefined_below_derived_tolerance() -> None:
    horizon = 1000
    # The derived tolerance is stability_tolerance_rate * T from the frozen
    # regret_stability_slack helper: no unrelated epsilon is introduced.
    _rate, tolerance_rate = regret_stability_slack(0.0, 0.0, 0.0, horizon)
    expected_tolerance = tolerance_rate * horizon
    assert expected_tolerance > 0.0

    utilization, defined, budget_tolerance = regret_stability_utilization(
        0.0, 0.0, 0.0, horizon
    )
    assert defined is False
    assert np.isnan(utilization)
    assert budget_tolerance == pytest.approx(expected_tolerance)

    # Equality with the tolerance is still undefined, never a manufactured zero.
    utilization, defined, _tol = regret_stability_utilization(
        0.0, 0.0, expected_tolerance, horizon
    )
    assert defined is False and np.isnan(utilization)

    # Just above the tolerance the ratio becomes defined.
    utilization, defined, _tol = regret_stability_utilization(
        0.0, 0.0, 2.0 * expected_tolerance, horizon
    )
    assert defined is True and utilization == pytest.approx(0.0)


def test_utilization_equals_absolute_regret_gap_over_budget() -> None:
    structural_regret, route_regret, budget, horizon = 1.00, 0.70, 0.50, 100
    utilization, defined, budget_tolerance = regret_stability_utilization(
        structural_regret, route_regret, budget, horizon
    )
    _rate, tolerance_rate = regret_stability_slack(
        structural_regret, route_regret, budget, horizon
    )
    assert defined is True
    assert budget_tolerance == pytest.approx(tolerance_rate * horizon)
    assert utilization == pytest.approx(
        abs(structural_regret - route_regret) / budget
    )


def test_defined_utilization_satisfies_stability_bound_and_range() -> None:
    cases = ((1.00, 0.70, 0.50), (0.80, 0.95, 0.30), (2.00, 2.00, 0.25))
    for structural_regret, route_regret, budget in cases:
        horizon = 250
        utilization, defined, budget_tolerance = regret_stability_utilization(
            structural_regret, route_regret, budget, horizon
        )
        assert defined is True
        assert 0.0 <= utilization <= 1.0 + budget_tolerance / budget

    # A ratio outside the tolerance-adjusted interval fails closed.
    with pytest.raises(ScientificInvariantError):
        regret_stability_utilization(1.00, 0.00, 0.10, 10)


# ---------------------------------------------------------------------------
# 10. Targeted output schemas
# ---------------------------------------------------------------------------
TARGETED_DIR = PROJECT_ROOT / "outputs" / "fast" / "targeted"


def _read_csv_header(name: str) -> list[str]:
    path = TARGETED_DIR / name
    if not path.exists():
        pytest.skip(f"targeted output not present locally: {name}")
    with path.open("r", encoding="utf-8") as handle:
        return handle.readline().strip().split(",")


def test_targeted_cancellation_artifacts_are_present_and_non_paper() -> None:
    path = TARGETED_DIR / "exp1_targeted_cancellation_sweep.csv"
    if not path.exists():
        pytest.skip("targeted cancellation sweep not present locally")
    import pandas as pd

    frame = pd.read_csv(path)
    assert frame["cancellation_sweep_id"].unique().tolist() == [CANCELLATION_SWEEP_ID]
    assert sorted(frame["shared_profile"].unique()) == sorted(
        THEORY_SWEEP.cancellation_shared_profiles
    )
    assert sorted(frame["alpha_shared"].unique()) == sorted(
        THEORY_SWEEP.cancellation_shared_scales
    )
    assert sorted(frame["alpha_dep"].unique()) == sorted(
        THEORY_SWEEP.cancellation_dep_ratios
    )
    assert frame.groupby("seed").size().unique().tolist() == [48]

    invariants = json.loads(
        (TARGETED_DIR / "exp1_targeted_cancellation_invariants.json").read_text(
            encoding="utf-8"
        )
    )
    assert invariants["status"] == "PASS"
    assert invariants["paper_result"] is False
    assert invariants["horizon_levels"] == [1000, 5000, 10000]

    report = json.loads(
        (TARGETED_DIR / "exp1_targeted_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["paper_result"] is False
    assert report["status"] == "PASS"


def test_targeted_output_schemas_contain_required_columns() -> None:
    horizon_columns = set(
        _read_csv_header("exp1_targeted_horizon_route_seed_metrics.csv")
    )
    assert {
        "seed",
        "mechanism_id",
        "route_id",
        "target_horizon",
        "n_rounds",
        "structural_regret",
        "route_regret",
        "alignment_budget",
        "structural_regret_rate",
        "route_regret_rate",
        "alignment_budget_rate",
        "complete_conflict_rate",
        "regret_stability_slack_rate",
        "regret_stability_tolerance",
        "regret_stability_utilization",
        "utilization_defined",
        "structural_path_hash",
        "delay_path_hash",
        "bundle_hash",
        "targeted_component",
        "run_id",
        "run_tier",
        "paper_result",
    } <= horizon_columns

    horizon_summary_columns = set(
        _read_csv_header("exp1_targeted_horizon_route_summary.csv")
    )
    assert {
        "target_horizon",
        "route_id",
        "manuscript_facing",
        "metric_id",
        "n_seeds",
        "n_total_seeds",
        "n_defined",
        "estimate",
        "ci_lower",
        "ci_upper",
        "bootstrap_repetitions",
        "ci_level",
        "paper_result",
    } <= horizon_summary_columns

    sweep_columns = set(_read_csv_header("exp1_targeted_cancellation_sweep.csv"))
    assert {
        "cancellation_sweep_id",
        "seed",
        "shared_profile",
        "alpha_shared",
        "alpha_dep",
        "eligible_rounds",
        "mean_absolute_actionwise_level_error",
        "mean_delta",
        "max_delta",
        "alignment_budget",
        "alignment_budget_rate",
        "mean_rho",
        "mean_chi",
        "complete_conflict_rate",
        "regret_map_linf_to_structural",
        "delta_linf_to_shared_reference",
        "rho_linf_to_shared_reference",
        "chi_linf_to_shared_reference",
        "regret_map_linf_to_shared_reference",
        "optimal_mask_mismatch_count_to_shared_reference",
    } <= sweep_columns

    summary_columns = set(_read_csv_header("exp1_targeted_cancellation_summary.csv"))
    assert {
        "cancellation_sweep_id",
        "shared_profile",
        "alpha_shared",
        "alpha_dep",
        "metric_id",
        "n_seeds",
        "estimate",
        "se",
        "ci_lower",
        "ci_upper",
        "bootstrap_repetitions",
        "ci_level",
        "paper_result",
    } <= summary_columns

    invariants = json.loads(
        (TARGETED_DIR / "exp1_targeted_cancellation_invariants.json").read_text(
            encoding="utf-8"
        )
    )["cancellation_sweep"]
    gates = {key: value for key, value in invariants.items() if key.startswith("C")}
    assert {
        "C1_pure_shared",
        "C2_shared_amplitude_invariance",
        "C3_profile_invariance",
        "C4_delta_margin_ratio",
        "C5_choice_threshold",
        "C6_no_clipping_no_learner",
    } <= set(gates)
    assert all(entry["passed"] is True for entry in gates.values())
    assert "max_numerical_deviation" in invariants


# ---------------------------------------------------------------------------
# 11. Primary paper-candidate preservation
# ---------------------------------------------------------------------------
def test_primary_paper_candidate_scientific_hashes_unchanged() -> None:
    candidate_root = PROJECT_ROOT / "outputs" / "paper_candidate"
    for relpath, expected in PRIMARY_PAPER_CANDIDATE_HASHES.items():
        artifact = candidate_root / relpath
        if not artifact.exists():
            pytest.skip(f"paper-candidate artifact missing locally: {relpath}")
        assert _sha256(artifact) == expected, f"paper artifact changed: {relpath}"

    promotion = candidate_root / "exp1_promotion_manifest.json"
    if not promotion.exists():
        return
    manifest = {
        item["path"].replace("\\", "/"): item["sha256"]
        for item in json.loads(promotion.read_text(encoding="utf-8"))["artifacts"]
    }
    for relpath, expected in PRIMARY_PAPER_CANDIDATE_HASHES.items():
        assert manifest.get(relpath) == expected, f"promotion manifest drifted: {relpath}"


# ---------------------------------------------------------------------------
# Integration: the sweep itself passes C1-C6 on the fast configuration
# ---------------------------------------------------------------------------
def test_cancellation_sweep_gates_pass_on_fast_config() -> None:
    rows, checks = cancellation_sweep_rows(FAST_STRUCTURAL, RUN.fast_seeds)
    assert checks["passed"] is True
    assert checks["grid_cells_per_seed"] == 48
    assert checks["n_seeds"] == len(RUN.fast_seeds)
    assert len(rows) == 48 * len(RUN.fast_seeds)
    for gate in (
        "C1_pure_shared",
        "C2_shared_amplitude_invariance",
        "C3_profile_invariance",
        "C4_delta_margin_ratio",
        "C5_choice_threshold",
        "C6_no_clipping_no_learner",
    ):
        assert checks[gate]["passed"] is True, f"{gate} failed"
    assert checks["max_numerical_deviation"] <= max(
        SWEEP_TOLERANCE, CANCELLATION_DELTA_RATIO_TOLERANCE
    )
    assert checks["reference_agreement_mask_mismatches"] == 0

    # C4 is checked in the native scale, with the normalized ratio gated only
    # where it is numerically conditioned; C1/C2/C3/C5/C6 semantics are unchanged.
    c4 = checks["C4_delta_margin_ratio"]
    assert c4["passed"] is True
    assert c4["c4_native_identity_pass"] is True
    assert c4["c4_ratio_conditioned_pass"] is True
    assert c4["c4_native_max_tolerance_ratio"] <= 1.0
    assert (
        c4["c4_ratio_conditioned_rounds"] + c4["c4_ratio_unconditioned_rounds"]
        == c4["round_evaluations"]
    )
    assert (
        c4["c4_ratio_max_error_all_diagnostic"]
        >= c4["c4_ratio_max_error_conditioned"]
    )
    assert c4["ratio_tol"] == CANCELLATION_DELTA_RATIO_TOLERANCE
    assert c4["roundoff_safety_factor"] == CANCELLATION_ROUNDOFF_SAFETY_FACTOR
    assert c4["machine_eps"] == float(np.finfo(float).eps)

    # C6: no clipping, no learner, no artifact write, primary registry untouched.
    assert _cancellation_structural_audit() == {
        "clipping_calls": 0,
        "learner_calls": 0,
        "write_calls": 0,
    }
    assert checks["C6_no_clipping_no_learner"]["mechanism_order_intact"] is True
    assert not set(THEORY_SWEEP.cancellation_shared_profiles) & set(MECHANISM_ORDER)
    assert len(MECHANISM_ORDER) == 6
