from __future__ import annotations

import numpy as np

from exp4.calibration.affine import fit_weighted_affine_calibration
from exp4.calibration.evaluation import evaluate_cross_fitted_calibration
from exp4.calibration.temporal_folds import construct_contiguous_temporal_folds


def test_temporal_folds_are_contiguous_complete_and_balanced() -> None:
    folds = construct_contiguous_temporal_folds(103, 5)
    assert set(folds) == set(range(5))
    sizes = [np.sum(folds == fold) for fold in range(5)]
    assert max(sizes) - min(sizes) <= 1
    for fold in range(5):
        positions = np.flatnonzero(folds == fold)
        assert np.array_equal(positions, np.arange(positions[0], positions[-1] + 1))


def test_affine_fit_recovers_parameters_and_has_no_fallback() -> None:
    x = np.linspace(-2.0, 2.0, 200)
    y = 0.2 + 1.5 * x
    fit = fit_weighted_affine_calibration(x, y, np.ones_like(x))
    assert fit.estimable
    assert np.isclose(fit.intercept, 0.2)
    assert np.isclose(fit.slope, 1.5)
    small = fit_weighted_affine_calibration(x[:20], y[:20], np.ones(20))
    assert not small.estimable
    assert small.status == "INSUFFICIENT_SUPPORT"
    assert np.isnan(small.intercept)


def _pairwise_calibration_toy() -> (
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]
):
    rng = np.random.default_rng(11)
    rounds = 2000
    pair_count = 45
    structural_gaps = rng.normal(0.0, 0.3, size=(rounds, pair_count))
    # Pair-dependent constant error e(p) chosen so pair-average != max.
    errors = np.linspace(0.0, 0.9, pair_count)
    route_gaps = 0.2 + 1.5 * structural_gaps + errors[None, :]
    fold_ids = construct_contiguous_temporal_folds(rounds, 5)
    inclusion = rng.random(rounds) < 0.30
    weights = np.ones(rounds, dtype=np.float64)
    return route_gaps, structural_gaps, fold_ids, inclusion, weights


def test_calibration_aggregation_is_pair_average_not_max() -> None:
    route_gaps, structural_gaps, fold_ids, inclusion, weights = (
        _pairwise_calibration_toy()
    )
    evaluation = evaluate_cross_fitted_calibration(
        "affine_linked",
        route_gaps,
        structural_gaps,
        fold_ids,
        inclusion,
        weights,
        replication_id=0,
        true_intercept=0.2,
        true_slope=1.5,
    )
    assert evaluation.estimable
    raw_pair_error = np.abs(route_gaps - structural_gaps)
    raw_unit = np.mean(raw_pair_error, axis=1)
    expected_raw = float(np.mean(raw_unit[inclusion]))
    assert np.isclose(evaluation.raw_pairwise_discrepancy, expected_raw)
    # The pair-average and the max-defect aggregations differ on this toy.
    expected_max = float(np.mean(np.max(raw_pair_error, axis=1)[inclusion]))
    assert not np.isclose(expected_raw, expected_max)
    # OOF-calibrated discrepancy is also a pair average (near-perfect affine
    # recovery, so it is far below the raw discrepancy).
    assert np.isfinite(evaluation.oof_calibrated_pairwise_discrepancy)
    assert (
        evaluation.oof_calibrated_pairwise_discrepancy
        < evaluation.raw_pairwise_discrepancy
    )
    assert np.isfinite(evaluation.recoverability)
