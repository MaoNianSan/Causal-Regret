"""Layout-level regression tests for the presentation renderers.

Every test renders through the real presentation pipeline into a temporary
preview root, then inspects the recorded ``layout_checks`` that were measured
on a real canvas draw (matplotlib renderer bounding boxes).  No scientific
computation is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from presentation.common import PreviewLayout, sha256_file
from presentation.layout import PROFILES
from presentation.renderers import render_source, write_appendix_order, write_overview_table
from presentation.validation import validate_preview
from presentation_sources import get_source


def _layout_checks(layout) -> dict[str, dict]:
    # Find the main figure id from the presentation manifest.
    manifest_path = layout.base / "manifests/presentation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    figure_ids = manifest.get("figure_ids", [])
    assert figure_ids
    metadata_path = layout.base / "figures/main/metadata" / f"{figure_ids[0]}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    checks = metadata.get("layout_checks", [])
    assert checks, f"no layout checks recorded for {figure_ids[0]}"
    return {row["check"]: row for row in checks}


def _assert_all_passed(checks: dict[str, dict]) -> None:
    failed = [name for name, row in checks.items() if not row["passed"]]
    assert not failed, f"layout gates failed: {failed}"


def test_layout_profiles_registered() -> None:
    expected = {"exp1_main", "exp2_main", "exp3_main", "exp4_main", "appendix"}
    assert expected <= set(PROFILES)


def test_exp1_main_gates_mean_delay_clear_of_title(tmp_path: Path) -> None:
    source = get_source("1")
    result = render_source(source, tmp_path)
    checks = _layout_checks(result["layout"])
    _assert_all_passed(checks)
    assert checks["layout:exp1_mean_delay_vs_title"]["passed"]
    assert "clear" in checks["layout:exp1_mean_delay_vs_title"]["details"]
    assert checks["layout:canvas_containment"]["passed"]
    assert checks["layout:title_inside_canvas"]["passed"]
    assert checks["layout:cross_panel_title_collision"]["passed"]


def test_exp2_main_gates_legend_inside_canvas_and_clear_of_xlabels(
    tmp_path: Path,
) -> None:
    source = get_source("2")
    result = render_source(source, tmp_path)
    checks = _layout_checks(result["layout"])
    _assert_all_passed(checks)
    assert checks["layout:legend_inside_canvas"]["passed"]
    assert checks["layout:legend_xlabel_clearance"]["passed"]
    assert "clear" in checks["layout:legend_xlabel_clearance"]["details"]


def test_exp3_main_gates_no_long_legend_and_no_title_collisions(
    tmp_path: Path,
) -> None:
    source = get_source("3")
    result = render_source(source, tmp_path)
    checks = _layout_checks(result["layout"])
    _assert_all_passed(checks)
    assert checks["layout:no_long_legend_text"]["passed"]
    assert checks["layout:legend_inside_canvas"]["passed"]
    assert checks["layout:legend_xlabel_clearance"]["passed"]
    assert checks["layout:cross_panel_title_collision"]["passed"]


def test_exp4_main_gates_display_labels_only(tmp_path: Path) -> None:
    source = get_source("4")
    result = render_source(source, tmp_path)
    checks = _layout_checks(result["layout"])
    _assert_all_passed(checks)
    assert checks["layout:no_internal_ids_in_labels"]["passed"]
    assert checks["layout:canvas_containment"]["passed"]


@pytest.mark.parametrize("key", ["1", "2", "3", "4"])
def test_publication_mode_render_and_validate_all_gates(tmp_path: Path, key: str) -> None:
    source = get_source(key, mode="publication")
    write_overview_table(
        PreviewLayout(tmp_path, source.experiment_id, source.run_id, mode="publication"),
        paper_result=source.paper_result,
    )
    result = render_source(source, tmp_path)
    layout = result["layout"]
    write_appendix_order(layout, paper_result=source.paper_result)
    checks = _layout_checks(layout)
    _assert_all_passed(checks)
    report = validate_preview(source, tmp_path, mode="publication")
    assert report["passed"] is True
    # Every recorded gate is re-checked by validation and passes.
    gate_rows = [
        row
        for row in report["checks"]
        if row["check"].startswith(f"{source.main_figure_id}:layout:")
    ]
    assert gate_rows and all(row["passed"] for row in gate_rows)


def test_render_never_modifies_scientific_source_files(tmp_path: Path) -> None:
    scientific_files = {
        "1": get_source("1").source_run / "figures/data/fig_exp1_alignment_transfer_data.csv",
        "2": get_source("2").source_run / "figures/figure_exp2_attribution_sensitivity_source.csv",
        "3": get_source("3").source_run / "tables/exp3_primary_route_results.csv",
        "4": get_source("4").source_run / "derived/module_a/exp4_module_a_population_summary.csv",
    }
    before = {key: sha256_file(path) for key, path in scientific_files.items()}
    for key in ("1", "2", "3", "4"):
        render_source(get_source(key, mode="publication"), tmp_path / key)
    after = {key: sha256_file(path) for key, path in scientific_files.items()}
    assert before == after
