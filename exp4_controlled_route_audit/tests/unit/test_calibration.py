from __future__ import annotations

import numpy as np

from exp4.calibration.affine import fit_weighted_affine_calibration
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
