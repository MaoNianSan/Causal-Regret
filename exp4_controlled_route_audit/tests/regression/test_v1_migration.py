from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from exp4.configuration.schema import (
    FIELD_MIGRATION,
    RECOMPUTE_REQUIRED_FOR_V3_PRIMARY,
    RESULT_SCHEMA,
    V1_RESULT_SCHEMA,
    V2_RESULT_SCHEMA,
    V2_TO_V3_SEMANTIC_MIGRATION,
    v3_pairwise_recompute_required,
)
from exp4.metrics.action_gaps import compute_action_gap_defect, compute_gap_discrepancies


def test_v1_defect_snapshot_and_schema_migration() -> None:
    structural = np.array([[0.0, 0.5, 1.0]])
    route = np.array([[0.1, 0.4, 0.9]])
    assert np.isclose(compute_action_gap_defect(structural, route).population_action_gap_defect, 0.2)
    assert RESULT_SCHEMA != V1_RESULT_SCHEMA
    assert RESULT_SCHEMA != V2_RESULT_SCHEMA
    assert FIELD_MIGRATION["population_raw_action_gap_defect"] == "population_action_gap_defect"
    assert FIELD_MIGRATION["labelled_support_coefficient"] is None


def test_v2_to_v3_semantic_migration_is_not_a_rename() -> None:
    """v2 population_action_gap_defect means mean_round_max_gap_defect (A_T/T).

    It must never be accepted as the v3 pair-average primary.
    """
    migration = V2_TO_V3_SEMANTIC_MIGRATION["population_action_gap_defect"]
    assert migration["v2_semantic"] == "mean_round_max_gap_defect"
    assert migration["v3_primary_mapping"] is None
    assert migration["recompute_required_for_v3_primary"] is True
    assert RECOMPUTE_REQUIRED_FOR_V3_PRIMARY is True


def test_v2_max_scalar_cannot_be_accepted_as_v3_pair_average() -> None:
    # A legacy v2 artifact carrying only the max-based scalar must be marked
    # for recomputation; it is never the pair-average primary.
    legacy_fields = {"population_action_gap_defect", "route_optimal_set_conflict_rate"}
    assert v3_pairwise_recompute_required(legacy_fields) is True
    v3_fields = {"mean_pairwise_gap_discrepancy", "population_action_gap_defect"}
    assert v3_pairwise_recompute_required(v3_fields) is False


def test_v2_scalar_equals_max_defect_not_pair_average() -> None:
    structural = np.array([[0.0, 1.0, 3.0]])
    route = np.array([[2.0, 1.0, 3.0]])
    legacy = compute_action_gap_defect(structural, route)
    v3 = compute_gap_discrepancies(structural, route)
    assert np.isclose(legacy.population_action_gap_defect, v3.mean_round_max_gap_defect)
    assert not np.isclose(legacy.population_action_gap_defect, v3.population_mean_pairwise_discrepancy)


def test_v1_full_output_remains_v1() -> None:
    baseline = Path(__file__).resolve().parents[2] / "outputs" / "runs" / "full_20260726T140240Z_1be8996e" / "logs" / "run_config.json"
    if not baseline.exists():
        pytest.skip("v1 full run baseline not present (removed during normalization)")
    assert V1_RESULT_SCHEMA in baseline.read_text(encoding="utf-8")
