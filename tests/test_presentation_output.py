from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import matplotlib.pyplot as plt
import pandas as pd

from presentation import SPEC_ID
from presentation.common import (
    LONG_FORM_COLUMNS,
    PreviewLayout,
    sanitize_run_id,
    standardize_long_form,
    write_figure_bundle,
)
from presentation.renderers import (
    figure_metadata,
    load_renderer_module,
    write_appendix_order,
    write_manifest,
)
from presentation.validation import validate_preview
from presentation_sources import PresentationSource, get_source


EXP1_MODULE = load_renderer_module("Exp1")
EXP2_MODULE = load_renderer_module("Exp2")
EXP3_MODULE = load_renderer_module("Exp3")
EXP4_MODULE = load_renderer_module("Exp4")
EXP1_CONTRACT = EXP1_MODULE.MAIN_CONTRACT
EXP2_CONTRACT = EXP2_MODULE.MAIN_CONTRACT
EXP3_CONTRACT = EXP3_MODULE.MAIN_CONTRACT
EXP4_CONTRACT = EXP4_MODULE.MAIN_CONTRACT
build_exp1_long = EXP1_MODULE.build_main_long_form
build_exp2_long = EXP2_MODULE.build_main_long_form
build_exp3_long = EXP3_MODULE.build_main_long_form
build_exp4_long = EXP4_MODULE.build_main_long_form


REQUIRED_METADATA_KEYS = {
    "spec_id",
    "figure_id",
    "figure_version",
    "experiment_id",
    "narrative_claim",
    "panel_definitions",
    "metric_definitions",
    "interpretation_boundary",
    "run_id",
    "run_tier",
    "paper_result",
    "scientific_source_paper_result",
    "promotion_status",
    "result_schema",
    "config_hash",
    "input_manifest_hash",
    "scientific_source_lineage",
    "presentation_source_lineage",
    "source_file_hashes",
    "figure_file_hashes",
    "source_data_file_hash",
    "uncertainty_definition",
    "generated_at",
    "source_run_path",
    "presentation_build_commit",
    "presentation_code_hash",
    "preview_root_relative_path",
}


def test_source_registry_resolves_every_frozen_render_input() -> None:
    exp1 = get_source("1")
    assert exp1.config_hash == "483df70d6daceef6ffbb42b5c59d98e50373a606a8d9d6e9da8f317eee8af914"
    assert exp1.run_id == "exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00"
    assert get_source("2").scientific_source_paper_result is True
    assert get_source("3").run_id == "exp3-full-20260807T072340Z"
    exp4 = get_source("4")
    assert exp4.result_schema == "exp4_controlled_route_audit_v3"
    assert exp4.scientific_source_paper_result is False
    assert all(not source.missing_files() for source in map(get_source, ("1", "2", "3", "4")))


def test_windows_run_id_is_sanitized() -> None:
    safe = sanitize_run_id("exp2:full/2026\\08*17?")
    assert all(character not in safe for character in '<>:"/\\|?*')


def test_plan_is_read_only_and_reports_sources(tmp_path: Path) -> None:
    before = set(tmp_path.rglob("*"))
    result = subprocess.run(
        [
            sys.executable,
            "render_presentation.py",
            "plan",
            "--spec",
            SPEC_ID,
            "--exp",
            "all",
            "--preview-root",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["mode"] == "read_only_plan"
    assert len(payload["experiments"]) == 4
    assert all(not item["missing_source_files"] for item in payload["experiments"])
    assert set(tmp_path.rglob("*")) == before


def test_main_contract_shapes_and_exclusions() -> None:
    assert EXP1_CONTRACT["layout"] == [1, 3]
    assert len(EXP1_CONTRACT["mechanisms"]) == 6
    assert EXP1_CONTRACT["main_exclusions"] == ["ranking_reversal_rate"]
    assert EXP2_CONTRACT["layout"] == [2, 2]
    assert EXP2_CONTRACT["source_vs_arrival_rows"] == 4
    assert EXP2_CONTRACT["source_pair_rows"] == 6
    assert EXP2_CONTRACT["metrics"] == ["allocation_tv", "kendall_tau_b"]
    assert EXP3_CONTRACT["layout"] == [2, 3]
    assert EXP3_CONTRACT["scope_paragraph_on_canvas"] is False
    assert EXP4_CONTRACT["layout"] == [2, 2]
    assert EXP4_CONTRACT["panel_a_source_fields"] == [
        "mean_pairwise_gap_discrepancy_mean",
        "mean_pairwise_gap_discrepancy_ci_lower",
        "mean_pairwise_gap_discrepancy_ci_upper",
    ]
    assert EXP4_CONTRACT["panel_d_controls"] == [
        "affine_linked",
        "blocked_correspondence_destroyed",
    ]
    assert EXP4_CONTRACT["main_exclusions"] == ["effective_support"]


def test_exp1_long_form_reconstructs_named_source_rows() -> None:
    source = get_source("1")
    frame = pd.read_csv(source.source_run / "figures/data/fig_exp1_alignment_transfer_data.csv")
    long = build_exp1_long(frame, source)
    assert list(long.columns) == LONG_FORM_COLUMNS
    assert set(long.condition_id) == set(EXP1_CONTRACT["mechanisms"])
    assert "ranking_reversal_rate" not in set(long.series_id)
    assert {"generated_mean_delay", "alignment_budget_rate"} <= set(
        long[long.panel_id.eq("a")].series_id
    )
    assert {"structural_regret_rate", "transfer_bound_rate"} <= set(
        long[long.panel_id.eq("b")].series_id
    )
    assert {"arrival_clock", "source_round", "paired_contrast"} <= set(
        long[long.panel_id.eq("c")].series_id
    )
    for row in long.itertuples(index=False):
        original = frame.loc[int(row.source_row_key)]
        assert row.point_estimate == original.estimate
        assert row.source_table == "fig_exp1_alignment_transfer_data.csv"


def test_exp2_long_form_has_four_plus_six_rows_and_no_topk() -> None:
    source = get_source("2")
    frame = pd.read_csv(source.source_run / "figures/figure_exp2_attribution_sensitivity_source.csv")
    long = build_exp2_long(frame, source)
    assert set(long.metric_id) == {"allocation_tv", "kendall_tau_b"}
    assert long[long.panel_id.eq("source_vs_arrival")].condition_id.nunique() == 4
    assert long[long.panel_id.eq("source_pair")].condition_id.nunique() == 6
    assert not any("top_k" in str(value) for value in long.metric_id)
    assert long.resampling_median.notna().all()
    assert long.uncertainty_method.str.contains("not a confidence interval").all()
    for row in long.itertuples(index=False):
        original = frame.loc[int(row.source_row_key)]
        assert row.point_estimate == original[row.metric_id]
        assert row.resampling_median == original[f"{row.metric_id}_resampling_q500"]


def test_exp3_current_source_and_long_form_guard() -> None:
    source = get_source("3")
    primary = pd.read_csv(source.source_run / "tables/exp3_primary_route_results.csv")
    value = primary.loc[
        primary.route_id.eq("arrival_carrier"),
        "maximum_heldout_reference_pair_gap_error",
    ]
    assert len(value) == 1
    assert abs(float(value.iloc[0]) - 0.6417907611) < 1e-9
    frame = pd.read_csv(source.source_run / "figures/data/exp3_main_score_gap_ranking_data.csv")
    long = build_exp3_long(frame, source)
    assert "support_scope" not in set(long.metric_id)
    assert long.paper_result.eq(False).all()
    assert long.uncertainty_method.str.contains("not a confidence interval").all()
    assert "ridge_over_historical_paired_value_gain" in set(long.metric_id)
    for row in long.itertuples(index=False):
        original = frame.loc[int(row.source_row_key)]
        assert row.point_estimate == original.full_sample_estimate


def test_exp4_long_form_uses_dpair_mcse_and_two_calibration_controls() -> None:
    source = get_source("4")
    module_a = pd.read_csv(source.source_run / "derived/module_a/exp4_module_a_population_summary.csv")
    audit = pd.read_csv(source.source_run / "derived/module_b/exp4_module_b_audit_performance.csv")
    controls = pd.read_csv(source.source_run / "derived/module_c/exp4_module_c_control_summary.csv")
    long = build_exp4_long(module_a, audit, controls, source)
    panel_a = long[long.panel_id.eq("a")]
    assert set(panel_a.metric_id) == {"mean_pairwise_gap_discrepancy_mean"}
    assert not any("population_action_gap_defect" in value for value in panel_a.metric_id)
    deterministic_a = panel_a[panel_a.condition_id.eq("q_route=1")]
    assert deterministic_a.interval_lower.isna().all()
    assert deterministic_a.interval_upper.isna().all()
    for row in panel_a.itertuples(index=False):
        original = module_a.loc[int(row.source_row_key)]
        assert row.point_estimate == original.mean_pairwise_gap_discrepancy_mean

    for panel_id, metric in (("b", "bias"), ("c", "rmse")):
        panel = long[long.panel_id.eq(panel_id)]
        assert set(panel.metric_id) == {metric}
        uncertain = panel[panel.series_id.ne("full_population")]
        for row in uncertain.itertuples(index=False):
            original = audit.loc[int(row.source_row_key)]
            assert row.interval_lower == original[metric] - 1.96 * original[f"{metric}_mcse"]
            assert row.interval_upper == original[metric] + 1.96 * original[f"{metric}_mcse"]
    panel_d = long[long.panel_id.eq("d")]
    assert set(panel_d.condition_id) == set(EXP4_CONTRACT["panel_d_controls"])
    assert {"raw_pairwise_discrepancy", "oof_calibrated_pairwise_discrepancy", "recoverability"} == set(panel_d.metric_id)
    assert not any("effective_support" in str(value) for value in long.metric_id)


def test_metadata_lineages_are_separate_for_all_sources() -> None:
    for key in ("1", "2", "3", "4"):
        source = get_source(key)
        metadata = figure_metadata(
            source,
            claim="fixture",
            panels={"a": "fixture"},
            metrics={"metric": "fixture"},
            boundary="fixture",
            code_paths=[Path("tests/test_presentation_output.py")],
            contract={"layout": [1, 1]},
            uncertainty="fixture",
        )
        assert metadata["scientific_source_lineage"]
        assert metadata["presentation_source_lineage"].startswith("presentation:")
        assert metadata["scientific_source_lineage"] != metadata["presentation_source_lineage"]


def test_fixture_bundle_writes_complete_hashable_artifacts(tmp_path: Path) -> None:
    layout = PreviewLayout(tmp_path, "fixture", "run:1")
    frame = standardize_long_form(
        pd.DataFrame(
            {
                "panel_id": ["a"],
                "metric_id": ["metric"],
                "point_estimate": [0.12345678901234568],
                "source_table": ["fixture.csv"],
                "source_row_key": ["0"],
            }
        ),
        figure_id="fixture_figure",
        experiment_id="fixture",
        run_id="run:1",
        run_tier="fixture",
        paper_result=False,
    )
    source_path = tmp_path / "fixture.csv"
    source_path.write_text("value\n0.12345678901234568\n", encoding="utf-8")
    fig, axis = plt.subplots(figsize=(7.1, 3.6), constrained_layout=True)
    axis.plot([0, 1], [0, 1], marker="o")
    axis.set_title("Live text")
    files = write_figure_bundle(
        fig,
        frame,
        layout,
        figure_id="fixture_figure",
        section="main",
        metadata={
            "experiment_id": "fixture",
            "run_id": "run:1",
            "run_tier": "fixture",
            "scientific_source_paper_result": False,
            "result_schema": "fixture",
            "config_hash": "fixture",
            "input_manifest_hash": "fixture",
            "scientific_source_lineage": "science",
            "presentation_source_lineage": "presentation",
            "presentation_build_commit": "fixture",
            "presentation_code_hash": "code",
            "source_run_path": str(tmp_path),
        },
        source_files=[source_path],
    )
    assert all(path.exists() and path.stat().st_size > 0 for path in files.values())
    assert "<text" in files["svg"].read_text(encoding="utf-8")
    loaded = pd.read_csv(files["data"], float_precision="round_trip")
    assert loaded.loc[0, "point_estimate"] == frame.loc[0, "point_estimate"]
    metadata = json.loads(files["metadata"].read_text(encoding="utf-8"))
    assert REQUIRED_METADATA_KEYS <= set(metadata)
    assert metadata["paper_result"] is False
    assert metadata["canvas_size_inches"] == [7.1, 3.6]
    assert metadata["png_dpi"] == 300
    assert set(metadata["figure_file_hashes"]) == {
        "fixture_figure.pdf",
        "fixture_figure.svg",
        "fixture_figure.png",
    }
    assert metadata["source_data_file_hash"]
    fixture_source = PresentationSource(
        experiment="Fixture",
        experiment_id="fixture",
        run_id="run:1",
        source_run=tmp_path,
        scientific_source_paper_result=False,
        run_tier="fixture",
        result_schema="fixture",
        config_hash="fixture",
        required_files=(),
        main_figure_id="fixture_figure",
    )
    write_manifest(layout, fixture_source, figure_ids=["fixture_figure"])
    write_appendix_order(layout)
    report = validate_preview(fixture_source, tmp_path)
    assert report["passed"] is True
    assert (layout.base / "validation/presentation_validation.json").exists()


def test_appendix_order_preserves_figure_ids_and_artifact_hashes(tmp_path: Path) -> None:
    source = get_source("1")
    layout = PreviewLayout(tmp_path, source.experiment_id, source.run_id)
    layout.ensure()
    artifact = layout.base / "tables/csv/example.csv"
    artifact.write_text("value\n1\n", encoding="utf-8")
    write_manifest(layout, source, appendix=True, figure_ids=["appendix_one"])
    write_appendix_order(layout)
    manifest = json.loads(
        (layout.base / "manifests/appendix_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["figure_ids"] == ["appendix_one"]
    assert "tables/csv/example.csv" in manifest["artifact_hashes"]
    assert [item["id"] for item in manifest["appendix_order"]] == [
        "C.1",
        "C.2",
        "C.3",
        "C.4",
        "C.5",
        "C.6",
    ]
