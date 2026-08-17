from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from exp4.audit.estimators import estimate_hajek_ipw_mean, estimate_unweighted_mean
from exp4.audit.inclusion import AuditInclusionDesign, construct_audit_designs
from exp4.audit.support import compute_effective_sample_size
from exp4.metrics.action_gaps import compute_gap_discrepancies
from exp4.modules.module_b import MODULE_B_ESTIMAND_ID, _evaluate_design


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


def _discrepancies_fixture() -> object:
    structural = np.array(
        [
            [0.0, 1.0, 3.0],
            [0.0, 1.0, 2.0],
            [1.0, 1.5, 2.0],
            [0.0, 0.5, 3.0],
        ]
    )
    route = np.array(
        [
            [2.0, 1.0, 3.0],
            [0.0, 2.0, 1.0],
            [2.0, 1.5, 1.0],
            [0.0, 2.0, 3.0],
        ]
    )
    return compute_gap_discrepancies(structural, route)


def _diagnostics_fixture(n: int) -> SimpleNamespace:
    return SimpleNamespace(
        contributor_count=np.ones(n, dtype=int),
        maximum_assignment_mass=np.ones(n, dtype=float),
    )


def _design(design_id: str, included: np.ndarray, weights: np.ndarray, rate: float) -> AuditInclusionDesign:
    return AuditInclusionDesign(
        design_id=design_id,
        evidence_rate=float(rate),
        inclusion_mask=np.asarray(included, dtype=bool),
        inclusion_probabilities=np.full(len(included), float(rate), dtype=np.float64),
        weights=np.asarray(weights, dtype=np.float64),
        mask_hash=f"mask_{design_id}",
        probability_hash=f"prob_{design_id}",
    )


def _evaluate(design: AuditInclusionDesign, discrepancies) -> tuple[dict, object]:
    n = len(discrepancies.round_mean_pairwise_discrepancy)
    ambiguity = np.linspace(0.0, 1.0, n)
    return _evaluate_design(
        0,
        design,
        discrepancies,
        ambiguity,
        (ambiguity - float(np.mean(ambiguity))) / float(np.std(ambiguity)),
        _diagnostics_fixture(n),
        slice(None),
        np.zeros(n, dtype=bool),
    )


def test_full_population_audit_matches_population_pairwise_discrepancy() -> None:
    discrepancies = _discrepancies_fixture()
    n = len(discrepancies.round_mean_pairwise_discrepancy)
    design = _design("full_population", np.ones(n, dtype=bool), np.ones(n), 1.0)
    record, frame = _evaluate(design, discrepancies)
    assert record["estimand_id"] == MODULE_B_ESTIMAND_ID == "mean_pairwise_gap_discrepancy"
    assert np.isclose(
        record["audited_mean_pairwise_gap_discrepancy"],
        discrepancies.population_mean_pairwise_discrepancy,
    )
    assert np.isclose(record["absolute_audit_error"], 0.0)
    assert np.allclose(
        frame["true_unit_mean_pairwise_gap_discrepancy"],
        discrepancies.round_mean_pairwise_discrepancy,
    )


def test_mcar_estimator_consumes_pair_average_unit_contribution() -> None:
    """Unit contribution d_i_pair is the pair average, never the max defect."""
    discrepancies = _discrepancies_fixture()
    n = len(discrepancies.round_mean_pairwise_discrepancy)
    included = np.array([True, True, False, True])
    design = _design("mcar_unweighted", included, np.ones(n), 0.75)
    record, _ = _evaluate(design, discrepancies)
    expected = float(np.mean(discrepancies.round_mean_pairwise_discrepancy[included]))
    assert np.isclose(record["audited_mean_pairwise_gap_discrepancy"], expected)
    # The estimator target differs from the max-defect-based value on this map.
    max_target = float(np.mean(discrepancies.round_max_gap_defect[included]))
    assert not np.isclose(expected, max_target)
    assert np.isclose(record["population_mean_pairwise_gap_discrepancy"], discrepancies.population_mean_pairwise_discrepancy)


def test_ipw_and_unweighted_designs_share_the_same_unit_target() -> None:
    discrepancies = _discrepancies_fixture()
    n = len(discrepancies.round_mean_pairwise_discrepancy)
    included = np.array([True, False, True, True])
    unit = discrepancies.round_mean_pairwise_discrepancy[included]
    unweighted = _design("ambiguity_selective_unweighted", included, np.ones(n), 0.5)
    ipw_weights = np.where(included, 2.0, 0.0)
    ipw = _design("ambiguity_selective_ipw", included, ipw_weights, 0.5)
    record_u, frame_u = _evaluate(unweighted, discrepancies)
    record_i, frame_i = _evaluate(ipw, discrepancies)
    # Identical d_i_pair before weighting/selection.
    assert np.allclose(
        frame_u["true_unit_mean_pairwise_gap_discrepancy"].to_numpy(),
        frame_i["true_unit_mean_pairwise_gap_discrepancy"].to_numpy(),
    )
    assert np.isclose(record_u["audited_mean_pairwise_gap_discrepancy"], float(np.mean(unit)))
    assert np.isclose(record_i["audited_mean_pairwise_gap_discrepancy"], float(np.mean(unit)))
    assert record_u["estimand_id"] == record_i["estimand_id"] == "mean_pairwise_gap_discrepancy"
