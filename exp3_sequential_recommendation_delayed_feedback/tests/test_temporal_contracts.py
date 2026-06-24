"""Minimal dependency-free temporal-contract tests for Exp3 v5."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DEFAULT_CONFIG
from proxy_models import (
    _feature_state_by_bin,
    action_proxy_cells,
    build_main_proxy_scores,
    history_mean_static_scores,
)
from recoverability import _same_user_current_action_at_arrival_indices
from report_tables import build_proxy_static_control_table


def test_carrier_never_uses_future_exposure() -> None:
    cfg = DEFAULT_CONFIG
    events = pd.DataFrame(
        {
            cfg.user_col: ["u", "u", "u"],
            cfg.time_col: [10, 20, 30],
            "arrival_time": [15, 25, 35],
            "action_bucket": ["a", "b", "c"],
        }
    )
    carrier = _same_user_current_action_at_arrival_indices(
        events, cfg, {"a": 0, "b": 1, "c": 2}
    )
    assert carrier.tolist() == [0, 1, 2], carrier.tolist()


def test_main_feature_state_ignores_future_bins() -> None:
    cfg = DEFAULT_CONFIG
    width = cfg.sequential_bin_ms
    bins = np.asarray([0, width], dtype=np.int64)
    base = pd.DataFrame(
        {
            "source_bin": [0, width],
            "action_idx": [0, 0],
            "action_bucket": ["a", "a"],
            "proxy_count": [10.0, 10.0],
            "proxy_sum": [2.0, 8.0],
            "composite_sum": [2.0, 8.0],
        }
    )
    changed_future = base.copy()
    changed_future.loc[changed_future["source_bin"] == width, "proxy_sum"] = 8000.0
    state_a = _feature_state_by_bin(
        base, bins, 1, cfg, initial_proxy_totals=(4.0, 20.0)
    )
    state_b = _feature_state_by_bin(
        changed_future, bins, 1, cfg, initial_proxy_totals=(4.0, 20.0)
    )
    for left, right in zip(state_a[0], state_b[0]):
        assert np.allclose(left, right), (left, right)


def test_history_static_control_uses_history_only() -> None:
    cfg = DEFAULT_CONFIG
    history = pd.DataFrame(
        {
            cfg.user_col: ["u", "u", "v", "v"],
            cfg.time_col: [0, 1, 0, 1],
            "action_bucket": ["a", "a", "b", "b"],
            f"valid_for_{cfg.primary_horizon}": [1, 1, 1, 1],
            f"y_long_value_log_{cfg.primary_horizon}": [1.0, 3.0, 2.0, 4.0],
        }
    )
    scores = history_mean_static_scores(history, ["a", "b"], cfg)
    assert np.allclose(scores, [2.0, 3.0]), scores


def test_static_control_table_reports_paired_effect() -> None:
    cfg = DEFAULT_CONFIG
    summary = pd.DataFrame(
        [
            {
                "delay_condition": cfg.primary_delay_condition,
                "method_id": "history_mean_static",
                "point_estimate": 0.10,
                "ci_lower": 0.05,
                "ci_upper": 0.15,
                "ci_level": 0.95,
                "n_bootstrap": 10,
            },
            {
                "delay_condition": cfg.primary_delay_condition,
                "method_id": "short_term_ridge_proxy",
                "point_estimate": 0.08,
                "ci_lower": 0.04,
                "ci_upper": 0.14,
                "ci_level": 0.95,
                "n_bootstrap": 10,
            },
        ]
    )
    effects = pd.DataFrame(
        [
            {
                "delay_condition": cfg.primary_delay_condition,
                "method_id": "short_term_ridge_proxy",
                "comparator_method_id": "history_mean_static",
                "point_estimate": 0.02,
                "ci_lower": -0.01,
                "ci_upper": 0.05,
            }
        ]
    )
    table = build_proxy_static_control_table(summary, effects, cfg)
    row = table[table["method_id"] == "short_term_ridge_proxy"].iloc[0]
    assert row["comparator_method_id"] == "history_mean_static"
    assert np.isclose(row["paired_regret_reduction_vs_history_mean"], 0.02)


# This protects the storage-recovery case where a zip extraction leaves a
# surrogate code point in a directory name.
def test_utf8_safe_output_text() -> None:
    from utils import utf8_safe_text

    recovered = utf8_safe_text("broken_\udca9_path")
    recovered.encode("utf-8")
    assert "\\udca9" in recovered


def main() -> int:
    test_carrier_never_uses_future_exposure()
    test_main_feature_state_ignores_future_bins()
    test_history_static_control_uses_history_only()
    test_static_control_table_reports_paired_effect()
    test_utf8_safe_output_text()
    print("TEMPORAL CONTRACT TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
