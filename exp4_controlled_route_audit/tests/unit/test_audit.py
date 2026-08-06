from __future__ import annotations

import numpy as np

from exp4.audit.estimators import estimate_hajek_ipw_mean, estimate_unweighted_mean
from exp4.audit.inclusion import construct_audit_designs
from exp4.audit.support import compute_effective_sample_size


def test_selective_unweighted_and_ipw_share_masks() -> None:
    ambiguity = np.linspace(0.0, 1.0, 1000)
    uniforms = np.random.default_rng(1).random(1000)
    designs = construct_audit_designs(ambiguity, np.random.default_rng(2).random(1000), uniforms)
    selective = [design for design in designs if design.design_id.startswith("ambiguity_selective")]
    for rate in (0.1, 0.3, 0.5):
        rows = [design for design in selective if np.isclose(design.evidence_rate, rate)]
        assert len(rows) == 2
        assert rows[0].mask_hash == rows[1].mask_hash
        assert rows[0].probability_hash == rows[1].probability_hash


def test_hajek_estimator_and_effective_sample_size() -> None:
    values = np.array([1.0, 3.0])
    weights = np.array([1.0, 2.0])
    assert estimate_unweighted_mean(values).estimate == 2.0
    assert np.isclose(estimate_hajek_ipw_mean(values, weights).estimate, 7.0 / 3.0)
    assert np.isclose(compute_effective_sample_size(weights), 9.0 / 5.0)
