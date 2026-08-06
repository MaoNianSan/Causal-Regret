from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from audit_design import AuditDesign
from config import DEFAULT_CONFIG
from evaluate_recoverability import compute_metrics
from evaluation_artifacts import EvaluationArrays
from ranking_metrics import ridge_over_historical_paired_value_gain
from ridge_selection import choose_alpha, rolling_origin_splits, select_ridge_alpha
from target_audit import audit_target_components


def _two_fold_result():
    actions = ("a0", "a1", "a2")
    source_sum = np.array(
        [
            [[[10.0, 5.0, 1.0]]],
            [[[1.0, 9.0, 2.0]]],
        ]
    )
    source_count = np.ones_like(source_sum)
    arrival_sum = np.array(
        [
            [[[8.0, 1.0, 2.0]]],
            [[[1.0, 7.0, 2.0]]],
        ]
    )
    arrays = EvaluationArrays(
        user_ids=("u0", "u1"),
        calendar_days=("2022-04-22",),
        candidate_actions=actions,
        user_group_ids=np.array([0, 0]),
        reference_fold_ids=np.array([0, 1]),
        source_target_sum=source_sum,
        source_target_count=source_count,
        arrival_target_sum=arrival_sum,
        arrival_target_count=np.ones_like(arrival_sum),
        fixed_route_scores={
            "history_mean_control": np.array([[[0.0, 2.0, 1.0]]]),
            "ridge_proxy": np.array([[[3.0, 1.0, 0.0]]]),
        },
        history_scores=np.zeros((1, 3)),
    )
    design = AuditDesign(
        user_group_count=1,
        support_min_events_per_fold=1,
        near_tie_threshold=0.0,
        candidate_actions=actions,
        history_support_summary=pd.DataFrame(),
        design_freeze={},
    )
    cfg = replace(DEFAULT_CONFIG, history_prior_count=0.0)
    return compute_metrics(arrays, design, cfg=cfg)


def test_route_action_uses_selection_fold() -> None:
    units = _two_fold_result().audit_unit_metrics
    arrival = units[units["route_id"] == "arrival_carrier"].set_index("selection_fold_id")
    assert arrival.loc[0, "route_selected_action_id"] == "a0"
    assert arrival.loc[1, "route_selected_action_id"] == "a1"


def test_route_gap_uses_selection_fold() -> None:
    units = _two_fold_result().audit_unit_metrics
    row = units[
        (units["route_id"] == "arrival_carrier") & (units["selection_fold_id"] == 0)
    ].iloc[0]
    assert np.isclose(row["maximum_heldout_reference_pair_gap_error"], 15.0)


def test_heldout_value_uses_opposite_fold() -> None:
    units = _two_fold_result().audit_unit_metrics
    row = units[
        (units["route_id"] == "history_mean_control")
        & (units["selection_fold_id"] == 0)
    ].iloc[0]
    assert np.isclose(
        row["signed_cross_fitted_reference_minus_route_value_difference"], -8.0
    )


def test_reference_action_uses_selection_fold() -> None:
    units = _two_fold_result().audit_unit_metrics
    references = units.drop_duplicates("selection_fold_id").set_index("selection_fold_id")
    assert references.loc[0, "reference_action_id"] == "a0"
    assert references.loc[1, "reference_action_id"] == "a1"


def test_arrival_route_changes_when_fold_scores_differ() -> None:
    units = _two_fold_result().audit_unit_metrics
    selected = units[units["route_id"] == "arrival_carrier"]["route_selected_action_id"]
    assert selected.nunique() == 2


def test_fixed_history_routes_remain_fold_invariant_when_expected() -> None:
    units = _two_fold_result().audit_unit_metrics
    for route_id in ("history_mean_control", "ridge_proxy"):
        selected = units[units["route_id"] == route_id]["route_selected_action_id"]
        assert selected.nunique() == 1


def _ridge_training(days: int = 10) -> pd.DataFrame:
    rows = []
    for day in range(days):
        for action_rank in range(2):
            rows.append(
                {
                    "calendar_day": f"2022-04-{day + 8:02d}",
                    "user_group_id": 0,
                    "action_id": f"a{action_rank}",
                    "action_rank": action_rank,
                    "lag_proxy_mean": 0.1 * day + action_rank,
                    "lag_proxy_count": 10 + day,
                    "lag_proxy_missing": 0.0,
                    "target_mean": 0.2 * day + 0.5 * action_rank,
                    "target_count": 20 + action_rank,
                }
            )
    return pd.DataFrame(rows)


def test_ridge_alpha_selection_uses_history_only() -> None:
    selection = select_ridge_alpha(_ridge_training(), 2, DEFAULT_CONFIG)
    assert selection.manifest["selection_scope"] == "history_only"
    assert selection.manifest["evaluation_data_used"] is False


def test_ridge_selector_rejects_evaluation_frame() -> None:
    with pytest.raises(ValueError, match="rejects evaluation data"):
        select_ridge_alpha(
            _ridge_training(),
            2,
            DEFAULT_CONFIG,
            evaluation_frame=pd.DataFrame({"evaluation": [1]}),
        )


def test_rolling_origin_has_strict_temporal_order() -> None:
    splits = rolling_origin_splits(_ridge_training(), min_train_days=7)
    assert splits
    assert all(max(train_days) < validation_day for train_days, validation_day in splits)


def test_alpha_tie_prefers_larger_regularization() -> None:
    aggregate = pd.DataFrame(
        {
            "alpha": [0.1, 1.0, 10.0],
            "macro_supported_cell_mae_mean": [0.2, 0.20005, 0.4],
        }
    )
    selected, tie_applied = choose_alpha(aggregate, 1e-4, "larger_alpha")
    assert selected == 1.0
    assert tie_applied is True


def test_selected_alpha_is_persisted_not_source_mutated() -> None:
    selection = select_ridge_alpha(_ridge_training(), 2, DEFAULT_CONFIG)
    assert selection.selected_alpha in DEFAULT_CONFIG.ridge_alpha_grid
    assert not hasattr(DEFAULT_CONFIG, "ridge_alpha")


def test_paired_gain_sign_convention() -> None:
    metrics = pd.DataFrame(
        {
            "route_id": ["history_mean_control", "ridge_proxy"],
            "signed_cross_fitted_reference_minus_route_value_difference": [0.3, 0.1],
        }
    )
    assert np.isclose(ridge_over_historical_paired_value_gain(metrics), 0.2)


def test_paired_gain_zero_when_routes_identical() -> None:
    metrics = pd.DataFrame(
        {
            "route_id": ["history_mean_control", "ridge_proxy"],
            "signed_cross_fitted_reference_minus_route_value_difference": [0.2, 0.2],
        }
    )
    assert ridge_over_historical_paired_value_gain(metrics) == 0.0


def _target_frame() -> pd.DataFrame:
    cfg = DEFAULT_CONFIG
    return pd.DataFrame(
        {
            cfg.long_view_col: [1.0, 0.0],
            cfg.like_col: [0.0, 1.0],
            cfg.comment_col: [0.0, 0.0],
            cfg.forward_col: [0.0, 0.0],
            cfg.follow_col: [0.0, 0.0],
            "is_target_eligible": [True, False],
            "future_engagement_value_6h": [1.5, np.nan],
            "future_engagement_target_6h": [np.log1p(1.5), np.nan],
        }
    )


def test_target_component_audit_does_not_modify_targets() -> None:
    frame = _target_frame()
    before = frame.copy(deep=True)
    audit_target_components(frame, "history")
    pd.testing.assert_frame_equal(frame, before)


def test_target_audit_matches_constructed_target_formula() -> None:
    audit = audit_target_components(_target_frame(), "history")
    contract = audit[audit["record_type"] == "contract"].iloc[0]
    assert bool(contract["constructed_formula_matches"])
    assert contract["target_interval"] == "[t,t+6h)"
