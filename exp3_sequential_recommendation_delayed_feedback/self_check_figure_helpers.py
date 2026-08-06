"""Frozen-source reconstruction checks for Exp3 figure bundles."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from plot_appendix_support import _prepare_full_support_preflight
from self_check_common import frames_equal, load_json
from utilities import sha256_file


def full_preflight_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    action_path = output_dir / "derived" / "exp3_full_design_support_by_action.csv"
    figure_path = (
        output_dir
        / "figures"
        / "data"
        / "exp3_appendix_full_design_support_preflight_data.csv"
    )
    if not action_path.exists() or pd.read_csv(action_path).empty:
        return (not figure_path.exists()), "full-design support figure correctly omitted when preflight is not evaluable"
    expected_actions, expected_metrics = _prepare_full_support_preflight(
        pd.read_csv(action_path),
        pd.read_csv(output_dir / "tables" / "exp3_full_design_support_preflight.csv"),
        pd.read_csv(output_dir / "tables" / "exp3_action_space_coverage.csv"),
        pd.read_csv(output_dir / "design" / "exp3_full_design_action_vocabulary.csv"),
    )
    figure = pd.read_csv(figure_path)
    action_columns = [
        "action_id",
        "audit_unit_count",
        "supported_unit_rate",
        "minimum_fold_count_min",
        "minimum_fold_count_p10",
        "minimum_fold_count_median",
        "minimum_fold_count_p90",
        "minimum_fold_count_max",
        "action_display_name",
        "action_rank",
    ]
    metric_columns = ["metric_id", "display_name", "value"]
    actual_action_rows = figure[
        figure["panel_id"] == "panel_a_full_design_action_support"
    ].reset_index(drop=True)
    expected_action_rows = expected_actions.reset_index(drop=True)
    scientific_match = frames_equal(
        actual_action_rows[action_columns],
        expected_actions[action_columns],
        ["action_rank"],
    ) and frames_equal(
        figure[figure["panel_id"] == "panel_b_full_design_readiness"][metric_columns],
        expected_metrics[metric_columns],
        ["metric_id"],
    )
    provenance_match = True
    for column in (
        "run_id",
        "run_tier",
        "paper_result",
        "analysis_tier",
        "experiment_id",
        "config_hash",
        "input_manifest_hash",
    ):
        if column in expected_actions.columns:
            provenance_match = provenance_match and actual_action_rows[column].astype(
                str
            ).equals(expected_action_rows[column].astype(str))
    provenance_match = bool(
        provenance_match
        and "figure_analysis_tier" in figure.columns
        and set(figure["figure_analysis_tier"].dropna().astype(str)) == {"appendix"}
    )
    return (
        bool(scientific_match and provenance_match),
        "full-design figure scientific fields reconstruct and display provenance remains separate",
    )


def _panel_sources_match(
    figure: pd.DataFrame,
    sources: dict[str, pd.DataFrame],
    label: str,
) -> tuple[bool, str]:
    for panel_id, source in sources.items():
        actual = figure[figure["panel_id"] == panel_id]
        columns = [column for column in source.columns if column in actual.columns]
        if not columns or not frames_equal(actual[columns], source[columns], columns[:1]):
            return False, f"{label} figure mismatch: {panel_id}"
    return True, f"{label} figure scientific fields reconstruct from frozen tables"


def arrival_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    figure = pd.read_csv(
        output_dir
        / "figures"
        / "data"
        / "exp3_appendix_arrival_carrier_diagnostic_data.csv"
    )
    return _panel_sources_match(
        figure,
        {
            "panel_a_carrier_lag": pd.read_csv(
                output_dir / "diagnostics" / "exp3_arrival_carrier_audit.csv"
            ),
            "panel_b_action_match": pd.read_csv(
                output_dir / "diagnostics" / "exp3_arrival_carrier_action_audit.csv"
            ),
        },
        "arrival-carrier",
    )


def dependence_figure_data_matches(output_dir: Path) -> tuple[bool, str]:
    figure = pd.read_csv(
        output_dir
        / "figures"
        / "data"
        / "exp3_appendix_dependence_and_selection_structure_data.csv"
    )
    return _panel_sources_match(
        figure,
        {
            "panel_a_outcome_reuse": pd.read_csv(
                output_dir / "derived" / "exp3_outcome_reuse_quantiles.csv"
            ),
            "panel_b_selection_instability": pd.read_csv(
                output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv"
            ),
        },
        "dependence and selection",
    )


def figure_metadata_hashes_match(output_dir: Path) -> tuple[bool, str]:
    files = sorted((output_dir / "figures" / "metadata").glob("*.json"))
    if not files:
        return False, "no figure metadata files found"
    for path in files:
        hashes = load_json(path).get("source_file_hashes", {})
        for relative, expected in hashes.items():
            source = output_dir / relative
            if not source.exists() or sha256_file(source) != expected:
                return False, f"source hash mismatch: {relative}"
    return True, f"verified {len(files)} figure metadata bundles"
