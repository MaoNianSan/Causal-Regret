from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG
from preprocess_events import _enforce_temporal_split_contract, _normalize_log
from synthetic_data import create_fast_fixture
from utilities import calendar_day, day_start_ms, next_day_start_ms, stable_group, stable_uniform


def test_hashes_are_deterministic_and_salt_separated() -> None:
    user = "user_0001"
    assert stable_group(user, 10, "a") == stable_group(user, 10, "a")
    assert stable_uniform(user, "delay") == stable_uniform(user, "delay")
    # The contract requires separate salts; equality by chance is possible for
    # a modulo group, so test the underlying uniform instead.
    assert stable_uniform(user, "group") != stable_uniform(user, "fold")


def test_fast_fixture_has_required_schema(tmp_path: Path) -> None:
    create_fast_fixture(tmp_path, DEFAULT_CONFIG)
    data = tmp_path / "data"
    history = pd.read_csv(data / DEFAULT_CONFIG.history_log, nrows=10)
    evaluation = pd.read_csv(data / DEFAULT_CONFIG.evaluation_log, nrows=10)
    video = pd.read_csv(data / DEFAULT_CONFIG.video_basic_file, nrows=10)
    required = {
        DEFAULT_CONFIG.user_col,
        DEFAULT_CONFIG.video_col,
        DEFAULT_CONFIG.time_col,
        DEFAULT_CONFIG.duration_col,
    }
    assert required.issubset(history.columns)
    assert required.issubset(evaluation.columns)
    assert {DEFAULT_CONFIG.video_col, DEFAULT_CONFIG.tag_col}.issubset(video.columns)
    assert np.isfinite(history[DEFAULT_CONFIG.time_col]).all()


def test_normalization_drops_missing_identifier_tokens() -> None:
    cfg = DEFAULT_CONFIG
    frame = pd.DataFrame(
        {
            cfg.user_col: ["u1", None, "nan", "  "],
            cfg.video_col: ["v1", "v2", "v3", "null"],
            cfg.time_col: [1, 2, 3, 4],
            cfg.duration_col: [10, 10, 10, 10],
        }
    )
    normalized = _normalize_log(frame, "fixture", cfg)
    assert normalized[cfg.user_col].tolist() == ["u1"]
    assert normalized[cfg.video_col].tolist() == ["v1"]


def test_calendar_days_and_boundaries_use_frozen_timezone() -> None:
    cfg = DEFAULT_CONFIG
    local_midnight = day_start_ms("2022-04-22", cfg.timezone_name)
    days = calendar_day(
        np.array([local_midnight - 1, local_midnight]), cfg.timezone_name
    )
    assert days.tolist() == ["2022-04-21", "2022-04-22"]
    assert next_day_start_ms("2022-04-21", cfg.timezone_name) == local_midnight


def test_temporal_contract_quarantines_only_small_preboundary_tail() -> None:
    cfg = DEFAULT_CONFIG
    boundary = day_start_ms(cfg.split_boundary_local_date, cfg.timezone_name)
    history = pd.DataFrame({cfg.time_col: [boundary - 2, boundary - 1]})
    evaluation = pd.DataFrame(
        {cfg.time_col: [boundary - 1, *range(boundary, boundary + 1000)]}
    )

    retained_history, retained_evaluation, audit = _enforce_temporal_split_contract(
        history, evaluation, cfg
    )

    assert len(retained_history) == 2
    assert len(retained_evaluation) == 1000
    assert int(retained_evaluation[cfg.time_col].min()) == boundary
    assert audit["evaluation_events_excluded_before_boundary"] == 1
    assert audit["strict_event_time_nonoverlap"] is True


def test_temporal_contract_rejects_material_preboundary_contamination() -> None:
    import pytest

    cfg = replace(DEFAULT_CONFIG, max_preboundary_evaluation_fraction=0.10)
    boundary = day_start_ms(cfg.split_boundary_local_date, cfg.timezone_name)
    history = pd.DataFrame({cfg.time_col: [boundary - 2]})
    evaluation = pd.DataFrame({cfg.time_col: [boundary - 1, boundary]})

    with pytest.raises(RuntimeError, match="INPUT_EVALUATION_PREBOUNDARY_EXCESS"):
        _enforce_temporal_split_contract(history, evaluation, cfg)


def test_temporal_contract_rejects_material_prestart_history() -> None:
    import pytest

    cfg = replace(DEFAULT_CONFIG, max_prestart_history_fraction=0.10)
    history_start = day_start_ms(cfg.history_start_local_date, cfg.timezone_name)
    boundary = day_start_ms(cfg.split_boundary_local_date, cfg.timezone_name)
    history = pd.DataFrame({cfg.time_col: [history_start - 1, history_start]})
    evaluation = pd.DataFrame({cfg.time_col: [boundary]})

    with pytest.raises(RuntimeError, match="INPUT_HISTORY_PRESTART_EXCESS"):
        _enforce_temporal_split_contract(history, evaluation, cfg)


def test_fast_input_contract_does_not_silently_create_fixture(tmp_path: Path) -> None:
    import pytest

    from runner import run_pipeline

    with pytest.raises(FileNotFoundError, match="uses the frozen KuaiRand inputs by default"):
        run_pipeline(
            tmp_path,
            "fast",
            output_dir=tmp_path / "outputs" / "exp3-fast-test",
            run_id="exp3-fast-test",
        )
    assert not (tmp_path / "inputs" / "_fast_fixture").exists()


def test_synthetic_fixture_requires_explicit_fast_flag() -> None:
    from main import build_parser

    default_args = build_parser().parse_args(["fast"])
    fixture_args = build_parser().parse_args(["fast", "--synthetic-fixture"])
    assert default_args.synthetic_fixture is False
    assert fixture_args.synthetic_fixture is True


def test_latest_run_resolvers_separate_completed_audited_and_resumable(tmp_path: Path) -> None:
    import json
    from runner import (
        resolve_latest_audited_pass_run,
        resolve_latest_completed_run,
        resolve_latest_resumable_run,
    )
    from code_version import code_version

    outputs = tmp_path / "outputs"
    version = code_version(tmp_path)
    passed = outputs / "exp3-fast-20260727T010000Z"
    failed = outputs / "exp3-fast-20260727T020000Z"
    for path in (passed, failed):
        (path / "metadata").mkdir(parents=True)
    (passed / "metadata" / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_tier": "fast",
                "pipeline_execution_status": "PASS",
                "independent_self_check_status": "PASS",
                "final_engineering_status": "PASS",
                "completed_at_utc": "x",
                **version,
            }
        )
    )
    (failed / "metadata" / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_tier": "fast",
                "pipeline_execution_status": "PASS",
                "independent_self_check_status": "FAIL",
                "final_engineering_status": "FAIL",
                "completed_at_utc": "y",
                **version,
            }
        )
    )
    for relative in (
        "design/exp3_design_freeze.json",
        "derived/exp3_evaluation_arrays.npz",
        "derived/exp3_route_metrics_point.csv",
        "metadata/run_config_snapshot.json",
        "checks/exp3_bootstrap_checkpoint.csv",
    ):
        target = failed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
    assert resolve_latest_completed_run(tmp_path, "fast") == failed.resolve()
    assert resolve_latest_audited_pass_run(tmp_path, "fast") == passed.resolve()
    assert resolve_latest_resumable_run(tmp_path, "fast") == failed.resolve()


def test_full_support_ready_does_not_imply_full_run_recommended() -> None:
    from run_reporting import readiness_fields

    fields = readiness_fields(
        {
            "run_tier": "fast",
            "input_audit_status": "PASS",
            "pipeline_execution_status": "PASS",
            "independent_self_check_status": "PASS",
            "final_engineering_status": "PASS",
            "scientific_contract_status": "PASS",
            "figure_data_contract_status": "FAIL",
            "scientific_uncertainty_status": "SENSITIVITY_ONLY_ACCEPTED",
            "formal_ci_validated": False,
            "full_design_support_ready": True,
        }
    )
    assert fields["full_design_support_ready"] is True
    assert fields["full_run_recommended"] is False
    assert fields["paper_promotion_eligible"] is False


def test_self_check_failure_report_status_is_synchronized(tmp_path: Path) -> None:
    import json

    from run_reporting import write_run_report

    for relative, payload in (
        (
            "design/exp3_split_manifest.json",
            {
                "timezone_rule": "Asia/Shanghai_epoch_day",
                "boundary_policy": "quarantine_events_outside_frozen_split_boundaries",
                "strict_event_time_nonoverlap": True,
            },
        ),
        ("checks/exp3_bootstrap_diagnostics.json", {"resampling_output_role": "sensitivity_only", "displayed_range_method": "percentile_user_cluster_sensitivity", "formal_ci_validated": False, "resampling_centering_status": "PASS"}),
        ("diagnostics/exp3_full_design_support_preflight.json", {"status": "READY"}),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    manifest = {
        "run_id": "exp3-fast-test",
        "run_tier": "fast",
        "pipeline_execution_status": "PASS",
        "independent_self_check_status": "FAIL",
        "final_engineering_status": "FAIL",
        "scientific_contract_status": "PASS",
        "scientific_uncertainty_status": "SENSITIVITY_ONLY_ACCEPTED",
        "formal_ci_validated": False,
        "full_design_support_ready": True,
        "full_run_recommended": False,
        "paper_promotion_eligible": False,
    }
    report = write_run_report(tmp_path, manifest).read_text(encoding="utf-8")
    assert "Pipeline execution status: **PASS**" in report
    assert "Independent self-check status: **FAIL**" in report
    assert "Final engineering status: **FAIL**" in report
    assert "Full run recommended: **false**" in report


def test_full_preflight_reports_insufficient_fixture_actions(tmp_path: Path) -> None:
    from support_preflight import run_full_design_support_preflight

    empty = pd.DataFrame()
    result = run_full_design_support_preflight(
        empty,
        empty,
        ["action_01"],
        tmp_path,
        DEFAULT_CONFIG,
        synthetic_fixture=True,
    )
    assert result["status"] == "NOT_EVALUATED_FIXTURE_INSUFFICIENT_ACTIONS"
    assert result["full_design_support_ready"] is False
    assert "full_recommended" not in result
