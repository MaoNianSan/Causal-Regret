from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from audit_design import AuditDesign
from bootstrap_evaluation import _run_replication
from config import DEFAULT_CONFIG
from evaluate_recoverability import compute_metrics
from evaluation_artifacts import EvaluationArrays
from self_check_helpers import boundary_quarantine_summary_matches, target_reuse_summary_matches


def _resampling_fixture():
    actions = ("a0", "a1", "a2")
    source_sum = np.array(
        [
            [[10.0, 0.0, 1.0]],
            [[0.0, 9.0, 0.0]],
            [[8.0, 0.0, 1.0]],
            [[0.0, 7.0, 0.0]],
        ]
    )
    source_count = np.array(
        [
            [[1.0, 1.0, 1.0]],
            [[1.0, 1.0, 0.0]],
            [[1.0, 1.0, 1.0]],
            [[1.0, 1.0, 0.0]],
        ]
    )
    arrays = EvaluationArrays(
        user_ids=("u0", "u1", "u2", "u3"),
        calendar_days=("2022-04-22",),
        candidate_actions=actions,
        user_group_ids=np.zeros(4, dtype=int),
        reference_fold_ids=np.array([0, 0, 1, 1]),
        source_target_sum=source_sum,
        source_target_count=source_count,
        arrival_target_sum=source_sum.copy(),
        arrival_target_count=source_count.copy(),
        fixed_route_scores={
            "history_mean_control": np.array([[[2.0, 1.0, 0.0]]]),
            "ridge_proxy": np.array([[[1.0, 2.0, 0.0]]]),
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
    cfg = replace(DEFAULT_CONFIG, history_prior_count=1.0)
    return arrays, design, cfg, compute_metrics(arrays, design, cfg=cfg)


def test_bootstrap_does_not_refit_ridge(monkeypatch: pytest.MonkeyPatch) -> None:
    arrays, design, cfg, point = _resampling_fixture()

    def fail_refit(*args, **kwargs):
        raise AssertionError("Ridge refit is forbidden inside user resampling")

    monkeypatch.setattr("ridge_selection.fit_ridge_coefficients", fail_refit)
    result = _run_replication(0, arrays, design, point, {}, cfg)
    assert result[-1] is None


def test_resampling_rebuilds_support_and_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    arrays, design, cfg, point = _resampling_fixture()
    monkeypatch.setattr(
        "bootstrap_evaluation._bootstrap_weights",
        lambda user_count, seed, replication_id: np.array([0.0, 2.0, 0.0, 2.0]),
    )
    _, _, _, support, structure, error = _run_replication(
        7, arrays, design, point, {}, cfg
    )
    assert error is None
    assert support is not None and structure is not None
    assert float(support.iloc[0]["action_coverage"]) < float(
        point.support_metrics.iloc[0]["action_coverage"]
    )
    assert (structure["support_set_switch_rate"] > 0).all()
    assert (structure["reference_action_switch_rate"] > 0).all()


def test_target_reuse_and_quarantine_summaries_reconstruct(tmp_path: Path) -> None:
    from run_reporting import boundary_quarantine_table, target_reuse_table

    targeted = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2"],
            "long_view": [1, 0, 1],
            "is_like": [0, 0, 0],
            "is_comment": [0, 0, 0],
            "is_forward": [0, 0, 0],
            "is_follow": [0, 0, 0],
            "source_windows_per_outcome_event": [1, 2, 3],
            "is_target_eligible": [True, True, False],
        }
    )
    audits = []
    positive_reuse = np.array([1.0, 3.0])
    for split_id in ("history", "evaluation"):
        path = tmp_path / "processed" / f"exp3_{split_id}_events_with_targets.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        targeted.to_csv(path, index=False)
        audits.append(
            {
                "split_id": split_id,
                "unique_user_count": 2,
                "source_event_count": 3,
                "eligible_source_event_count": 2,
                "positive_outcome_event_count": 2,
                "right_censoring_rate": 1 / 3,
                "outcome_event_reuse_rate": 0.5,
                "mean_source_windows_per_outcome_event": float(positive_reuse.mean()),
                "median_source_windows_per_outcome_event": float(np.median(positive_reuse)),
                "p90_source_windows_per_outcome_event": float(np.quantile(positive_reuse, 0.9)),
                "maximum_source_windows_per_outcome_event": float(np.max(positive_reuse)),
                "mean_source_events_per_user": 1.5,
                "p90_source_events_per_user": 1.9,
            }
        )
    tables = tmp_path / "tables"
    tables.mkdir()
    target_reuse_table(audits[0], audits[1]).to_csv(
        tables / "exp3_target_reuse_audit.csv", index=False
    )
    split = {
        "timezone_name": "Asia/Shanghai",
        "timezone_rule": "Asia/Shanghai_epoch_day",
        "boundary_policy": "quarantine_events_outside_frozen_split_boundaries",
        "raw_strict_event_time_nonoverlap": False,
        "raw_overlap_width_ms": 10,
        "strict_event_time_nonoverlap": True,
        "history_events_excluded_before_start": 2,
        "history_prestart_fraction": 0.001,
        "max_prestart_history_fraction": 0.001,
        "evaluation_events_excluded_before_boundary": 3,
        "evaluation_preboundary_fraction": 0.001,
        "max_preboundary_evaluation_fraction": 0.001,
    }
    design = tmp_path / "design"
    design.mkdir()
    (design / "exp3_split_manifest.json").write_text(
        json.dumps(split), encoding="utf-8"
    )
    boundary_quarantine_table(split).to_csv(
        tables / "exp3_boundary_quarantine_audit.csv", index=False
    )
    assert target_reuse_summary_matches(tmp_path)[0]
    assert boundary_quarantine_summary_matches(tmp_path)[0]
    restored = pd.read_csv(tables / "exp3_boundary_quarantine_audit.csv")
    assert not restored["raw_strict_event_time_nonoverlap"].astype(bool).any()
    assert restored["retained_strict_event_time_nonoverlap"].astype(bool).all()
