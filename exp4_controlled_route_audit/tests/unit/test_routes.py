from __future__ import annotations

import numpy as np

from exp4.routes.common import candidate_sources, compute_candidate_weights


def test_candidate_weights_are_positive_finite_and_normalized() -> None:
    candidates = candidate_sources(5, 10, 20)
    assert np.array_equal(candidates, np.arange(5))
    weights = compute_candidate_weights(
        np.array([[0.0], [0.5], [1.0], [1.5], [2.0]]),
        np.array([1.0]),
        np.array([5, 4, 3, 2, 1]),
        0.5,
        np.full(20, 1.0 / 20.0),
    )
    assert np.all(np.isfinite(weights))
    assert np.all(weights > 0.0)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(candidates < 5)
