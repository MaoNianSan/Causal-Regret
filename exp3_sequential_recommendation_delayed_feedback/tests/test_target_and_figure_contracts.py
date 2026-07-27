from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bootstrap_evaluation import _bootstrap_weights
from bootstrap_intervals import MetricBounds, ROUTE_METRIC_BOUNDS, basic_interval_audit, interval_audit
from config import DEFAULT_CONFIG
from construct_delayed_targets import _target_one_user
from plot_main_results import _validated_range
from proxy_routes import _design_matrix
from route_diagnostics import summarize_route_selection
from self_check_helpers import (
    bootstrap_interval_audit_matches,
    boundary_quarantine_summary_matches,
    full_preflight_figure_data_matches,
    target_reuse_summary_matches,
)


def _event_frame(times: list[int], long_view: list[float]) -> pd.DataFrame:
    cfg = DEFAULT_CONFIG
    n = len(times)
    return pd.DataFrame(
        {
            cfg.user_col: ["u1"] * n,
            cfg.time_col: times,
            cfg.long_view_col: long_view,
            cfg.like_col: np.zeros(n),
            cfg.comment_col: np.zeros(n),
            cfg.forward_col: np.zeros(n),
            cfg.follow_col: np.zeros(n),
        }
    )


def test_target_window_is_left_closed_right_open() -> None:
    cfg = DEFAULT_CONFIG
    horizon = cfg.target_horizon_ms
    frame = _event_frame([0, horizon - 1, horizon], [2.0, 3.0, 5.0])
    result = _target_one_user(frame, split_end_ms=2 * horizon, cfg=cfg)
    assert result.loc[0, "future_engagement_value_6h"] == 0.5 * (2.0 + 3.0)
    assert result.loc[1, "future_engagement_value_6h"] == 0.5 * (3.0 + 5.0)
    assert result["source_windows_per_outcome_event"].tolist() == [1, 2, 2]


def test_reported_sensitivity_endpoints_are_not_silently_truncated() -> None:
    low, high = _validated_range(0.03, 0.04)
    assert (low, high) == (0.03, 0.04)


def test_percentile_sensitivity_is_primary_and_basic_is_audit_only() -> None:
    values = np.array([2.0, 3.0, 4.0, 5.0])
    basic_low, basic_high = basic_interval_audit(3.0, values, 0.50, MetricBounds(0.0, 4.0))
    qlow, qhigh = np.quantile(values, [0.25, 0.75])
    assert np.isclose(basic_low, max(0.0, 6.0 - qhigh))
    assert np.isclose(basic_high, min(4.0, 6.0 - qlow))
    audit = interval_audit(
        metric_id="m",
        point_estimate=3.0,
        values=values,
        range_level=0.50,
        bounds=MetricBounds(0.0, 4.0),
    )
    assert audit["sensitivity_range_method"] == "percentile_user_cluster_sensitivity"
    assert audit["formal_ci_validated"] is False
    assert np.isclose(audit["sensitivity_lower"], qlow)
    assert np.isclose(audit["sensitivity_upper"], qhigh)
    assert audit["legacy_basic_lower_audit_only"] == basic_low
    assert audit["legacy_basic_upper_audit_only"] == basic_high


def test_bootstrap_seed_is_replication_id_deterministic() -> None:
    a = _bootstrap_weights(20, seed=123, replication_id=7)
    b = _bootstrap_weights(20, seed=123, replication_id=7)
    c = _bootstrap_weights(20, seed=123, replication_id=8)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert a.sum() == 20


def test_ridge_design_matrix_uses_frozen_compact_features() -> None:
    frame = pd.DataFrame(
        {
            "action_rank": [0, 1],
            "lag_proxy_mean": [0.1, 0.2],
            "lag_proxy_count": [10, 20],
            "lag_proxy_missing": [0.0, 0.0],
        }
    )
    matrix, names = _design_matrix(frame, 2)
    assert matrix.shape == (2, 6)
    assert {"lag_proxy_mean", "log1p_lag_proxy_count", "lag_proxy_missing"}.issubset(names)
    assert not any("ewma" in name for name in names)


def test_route_selection_diagnostic_detects_equivalence() -> None:
    units = pd.DataFrame(
        {
            "audit_unit_id": ["u1", "u1", "u1", "u1"],
            "selection_fold_id": [0, 1, 0, 1],
            "route_id": ["history_mean_control", "history_mean_control", "ridge_proxy", "ridge_proxy"],
            "route_selected_action_id": ["a", "a", "a", "a"],
        }
    )
    summary, contrast = summarize_route_selection(units)
    assert contrast["complete_selection_equivalence"] is True
    assert summary.set_index("route_id").loc["ridge_proxy", "all_directions_same_action"]


def test_full_design_support_preflight_figure_renders(tmp_path: Path) -> None:
    from plot_appendix_results import _draw_full_support_preflight, _prepare_full_support_preflight

    action_summary = pd.DataFrame(
        {
            "action_id": ["action_01", "action_02", "action_03"],
            "supported_unit_rate": [1.0, 0.9, 0.7],
            "minimum_fold_count_p10": [600.0, 450.0, 300.0],
            "minimum_fold_count_median": [900.0, 700.0, 520.0],
            "minimum_fold_count_p90": [1300.0, 1000.0, 800.0],
        }
    )
    preflight_summary = pd.DataFrame(
        {
            "split_id": ["evaluation"],
            "action_coverage": [0.9],
            "pair_coverage": [0.85],
            "audit_unit_coverage": [0.8],
        }
    )
    coverage = pd.DataFrame(
        {
            "split_id": ["evaluation"],
            "design_scope": ["full_design_preflight"],
            "selected_action_exposure_mass_coverage": [0.62],
        }
    )
    vocabulary = pd.DataFrame(
        {
            "action_id": ["action_01", "action_02", "action_03"],
            "action_display_name": ["A", "B", "C"],
            "is_candidate_action": [True, True, True],
        }
    )
    actions, metrics = _prepare_full_support_preflight(action_summary, preflight_summary, coverage, vocabulary)
    figure = _draw_full_support_preflight(actions, metrics, threshold=500, group_count=10, status="READY")
    target = tmp_path / "support_preflight.png"
    figure.savefig(target, dpi=100)
    assert target.exists() and target.stat().st_size > 0


def test_numeric_action_label_round_trip_is_unambiguous(tmp_path: Path) -> None:
    from preprocess_events import _freeze_action_vocabulary

    history = pd.DataFrame({"primary_tag": ["18", "18", "7", "7"]})
    vocabulary, _, _ = _freeze_action_vocabulary(history, 2, DEFAULT_CONFIG)
    path = tmp_path / "vocabulary.csv"
    vocabulary.to_csv(path, index=False)
    restored = pd.read_csv(path)
    labels = restored.loc[restored["is_candidate_action"], "action_display_name"].tolist()
    assert labels == ["Tag 18", "Tag 7"]


def test_real_like_nonempty_preflight_contract_preserves_scientific_provenance(tmp_path: Path) -> None:
    from plot_appendix_results import _attach_figure_provenance, _prepare_full_support_preflight

    action_summary = pd.DataFrame(
        {
            "action_id": ["action_01", "action_02"],
            "audit_unit_count": [10, 10],
            "supported_unit_rate": [0.9, 0.8],
            "minimum_fold_count_min": [500.0, 450.0],
            "minimum_fold_count_p10": [550.0, 500.0],
            "minimum_fold_count_median": [700.0, 650.0],
            "minimum_fold_count_p90": [900.0, 850.0],
            "minimum_fold_count_max": [1000.0, 950.0],
            "run_id": ["run", "run"],
            "run_tier": ["fast", "fast"],
            "paper_result": [False, False],
            "analysis_tier": ["primary", "primary"],
            "experiment_id": ["exp3", "exp3"],
            "config_hash": ["cfg", "cfg"],
            "input_manifest_hash": ["input", "input"],
        }
    )
    preflight = pd.DataFrame(
        {"split_id": ["evaluation"], "action_coverage": [0.9], "pair_coverage": [0.85], "audit_unit_coverage": [1.0]}
    )
    coverage = pd.DataFrame(
        {"split_id": ["evaluation"], "design_scope": ["full_design_preflight"], "selected_action_exposure_mass_coverage": [0.75]}
    )
    vocabulary = pd.DataFrame(
        {
            "action_id": ["action_01", "action_02"],
            "action_display_name": ["Tag 18", "Tag 7"],
            "is_candidate_action": [True, True],
        }
    )
    actions, metrics = _prepare_full_support_preflight(action_summary, preflight, coverage, vocabulary)
    source = pd.concat(
        [
            actions.assign(panel_id="panel_a_full_design_action_support"),
            metrics.assign(panel_id="panel_b_full_design_readiness"),
        ],
        ignore_index=True,
        sort=False,
    )
    source = _attach_figure_provenance(source, {"analysis_tier": "appendix", "run_id": "run"})
    for relative, frame in (
        ("derived/exp3_full_design_support_by_action.csv", action_summary),
        ("tables/exp3_full_design_support_preflight.csv", preflight),
        ("tables/exp3_action_space_coverage.csv", coverage),
        ("design/exp3_full_design_action_vocabulary.csv", vocabulary),
        ("figures/data/exp3_appendix_full_design_support_preflight_data.csv", source),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    passed, _ = full_preflight_figure_data_matches(tmp_path)
    restored = pd.read_csv(tmp_path / "figures/data/exp3_appendix_full_design_support_preflight_data.csv")
    action_rows = restored[restored["panel_id"] == "panel_a_full_design_action_support"]
    assert passed
    assert set(action_rows["analysis_tier"]) == {"primary"}
    assert set(restored["figure_analysis_tier"]) == {"appendix"}


def test_bootstrap_point_draw_metric_mapping_reconstructs_and_detects_swap(tmp_path: Path) -> None:
    point_rows = []
    draw_rows = []
    audit_rows = []
    for route_index, route_id in enumerate(("arrival_carrier", "ridge_proxy")):
        point = {"route_id": route_id}
        for metric_index, metric in enumerate(
            (
                "score_spearman_correlation",
                "score_calibration_mae",
                "heldout_gap_defect",
                "gap_sign_agreement",
                "gap_reversal_rate",
                "cross_fitted_ranking_shortfall",
                "top_action_match_rate",
            )
        ):
            value = 0.1 + 0.05 * route_index + 0.01 * metric_index
            point[metric] = value
        point_rows.append(point)
        for replication_id in range(5):
            draw = {"route_id": route_id, "replication_id": replication_id}
            for metric in point:
                if metric != "route_id":
                    draw[metric] = point[metric] + 0.001 * (replication_id - 2)
            draw_rows.append(draw)
        route_draws = pd.DataFrame(draw_rows)[lambda frame: frame["route_id"] == route_id]
        for metric, bounds in ROUTE_METRIC_BOUNDS.items():
            audit = interval_audit(
                metric_id=metric,
                point_estimate=point[metric],
                values=route_draws[metric].to_numpy(float),
                range_level=DEFAULT_CONFIG.resampling_range_level,
                bounds=bounds,
            )
            audit.update({"object_type": "route_metric", "object_id": route_id})
            audit_rows.append(audit)
    (tmp_path / "derived").mkdir()
    (tmp_path / "checks").mkdir()
    pd.DataFrame(point_rows).to_csv(tmp_path / "derived/exp3_route_metrics_point.csv", index=False)
    pd.DataFrame(draw_rows).to_csv(tmp_path / "derived/exp3_bootstrap_route_draws.csv", index=False)
    audit_frame = pd.DataFrame(audit_rows)
    audit_frame.to_csv(tmp_path / "checks/exp3_resampling_sensitivity_audit.csv", index=False)
    assert bootstrap_interval_audit_matches(tmp_path)[0]
    audit_frame.loc[audit_frame.index[0], "object_id"] = "ridge_proxy"
    audit_frame.to_csv(tmp_path / "checks/exp3_resampling_sensitivity_audit.csv", index=False)
    assert not bootstrap_interval_audit_matches(tmp_path)[0]


def test_target_reuse_and_quarantine_summaries_reconstruct(tmp_path: Path) -> None:
    import json

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
    target_reuse_table(audits[0], audits[1]).to_csv(tables / "exp3_target_reuse_audit.csv", index=False)
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
    (design / "exp3_split_manifest.json").write_text(json.dumps(split), encoding="utf-8")
    boundary_quarantine_table(split).to_csv(tables / "exp3_boundary_quarantine_audit.csv", index=False)
    assert target_reuse_summary_matches(tmp_path)[0]
    assert boundary_quarantine_summary_matches(tmp_path)[0]
    restored_boundary = pd.read_csv(tables / "exp3_boundary_quarantine_audit.csv")
    assert not restored_boundary["raw_strict_event_time_nonoverlap"].astype(bool).any()
    assert restored_boundary["retained_strict_event_time_nonoverlap"].astype(bool).all()
