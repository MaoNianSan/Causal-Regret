"""MCAR, ambiguity-selective, IPW, and full-population audit designs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from exp4.configuration.parameters import MODULE_B
from exp4.simulation.trajectory import hash_array


@dataclass(frozen=True)
class AuditInclusionDesign:
    design_id: str
    evidence_rate: float
    inclusion_mask: np.ndarray
    inclusion_probabilities: np.ndarray
    weights: np.ndarray
    mask_hash: str
    probability_hash: str


def _expit(values: np.ndarray) -> np.ndarray:
    output = np.empty_like(values, dtype=np.float64)
    positive = values >= 0.0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    output[~positive] = exp_values / (1.0 + exp_values)
    return output


def standardize_ambiguity(ambiguity_score: np.ndarray) -> np.ndarray:
    values = np.asarray(ambiguity_score, dtype=np.float64)
    standard_deviation = float(np.std(values))
    if standard_deviation <= 1e-14:
        return np.zeros_like(values)
    return (values - float(np.mean(values))) / standard_deviation


def solve_selective_inclusion_probabilities(
    standardized_ambiguity: np.ndarray, evidence_rate: float
) -> np.ndarray:
    if not 0.0 < evidence_rate < 1.0:
        raise ValueError("selective evidence_rate must be between zero and one")

    def probabilities(intercept: float) -> np.ndarray:
        raw = _expit(intercept + MODULE_B.ambiguity_slope * standardized_ambiguity)
        return np.clip(raw, MODULE_B.inclusion_lower_bound, MODULE_B.inclusion_upper_bound)

    lower, upper = -60.0, 60.0
    for _ in range(240):
        midpoint = 0.5 * (lower + upper)
        if float(np.mean(probabilities(midpoint))) < evidence_rate:
            lower = midpoint
        else:
            upper = midpoint
    result = probabilities(0.5 * (lower + upper))
    discrepancy = abs(float(np.mean(result)) - float(evidence_rate))
    if discrepancy >= MODULE_B.inclusion_rate_tolerance:
        raise RuntimeError(
            f"Selective inclusion solver failed: target={evidence_rate}, error={discrepancy:.3e}"
        )
    return result


def _design(
    design_id: str,
    evidence_rate: float,
    mask: np.ndarray,
    probabilities: np.ndarray,
    weights: np.ndarray,
) -> AuditInclusionDesign:
    return AuditInclusionDesign(
        design_id=design_id,
        evidence_rate=float(evidence_rate),
        inclusion_mask=mask,
        inclusion_probabilities=probabilities,
        weights=weights,
        mask_hash=hash_array(mask.astype(np.uint8)),
        probability_hash=hash_array(probabilities.astype(np.float64)),
    )


def construct_audit_designs(
    ambiguity_score: np.ndarray,
    audit_uniform_mcar: np.ndarray,
    audit_uniform_selective: np.ndarray,
) -> list[AuditInclusionDesign]:
    standardized = standardize_ambiguity(ambiguity_score)
    designs: list[AuditInclusionDesign] = []
    for rate in MODULE_B.audit_evidence_rates:
        if rate >= 1.0:
            ones = np.ones(len(ambiguity_score), dtype=np.float64)
            designs.append(
                _design("full_population", 1.0, ones.astype(bool), ones, ones)
            )
            continue
        mcar_probabilities = np.full(len(ambiguity_score), rate, dtype=np.float64)
        mcar_mask = audit_uniform_mcar < rate
        designs.append(
            _design(
                "mcar_unweighted",
                rate,
                mcar_mask,
                mcar_probabilities,
                np.ones(len(ambiguity_score), dtype=np.float64),
            )
        )
        selective_probabilities = solve_selective_inclusion_probabilities(
            standardized, rate
        )
        selective_mask = audit_uniform_selective < selective_probabilities
        designs.append(
            _design(
                "ambiguity_selective_unweighted",
                rate,
                selective_mask,
                selective_probabilities,
                np.ones(len(ambiguity_score), dtype=np.float64),
            )
        )
        designs.append(
            _design(
                "ambiguity_selective_ipw",
                rate,
                selective_mask,
                selective_probabilities,
                1.0 / selective_probabilities,
            )
        )
    return designs
