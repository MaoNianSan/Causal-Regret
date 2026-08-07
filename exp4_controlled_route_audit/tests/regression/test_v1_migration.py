from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from exp4.configuration.schema import FIELD_MIGRATION, RESULT_SCHEMA, V1_RESULT_SCHEMA
from exp4.metrics.action_gaps import compute_action_gap_defect


def test_v1_defect_snapshot_and_schema_migration() -> None:
    structural = np.array([[0.0, 0.5, 1.0]])
    route = np.array([[0.1, 0.4, 0.9]])
    assert np.isclose(compute_action_gap_defect(structural, route).population_action_gap_defect, 0.2)
    assert RESULT_SCHEMA != V1_RESULT_SCHEMA
    assert FIELD_MIGRATION["population_raw_action_gap_defect"] == "population_action_gap_defect"
    assert FIELD_MIGRATION["labelled_support_coefficient"] is None


def test_v1_full_output_remains_v1() -> None:
    baseline = Path(__file__).resolve().parents[2] / "outputs" / "runs" / "full_20260726T140240Z_1be8996e" / "logs" / "run_config.json"
    if not baseline.exists():
        pytest.skip("v1 full run baseline not present (removed during normalization)")
    assert V1_RESULT_SCHEMA in baseline.read_text(encoding="utf-8")
