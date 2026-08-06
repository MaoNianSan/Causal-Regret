from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)

from plot_main_results import plot_main_figure
from plot_scope_note import build_scope_note
from self_check_redesign import main_figure_data_matches


ROUTES = ("arrival_carrier", "history_mean_control", "ridge_proxy")
ROUTE_METRICS = (
    "pooled_supported_cell_spearman",
    "pooled_supported_cell_mae",
    "maximum_heldout_reference_pair_gap_error",
    "heldout_reference_pair_sign_agreement",
    "top_action_agreement_with_fold_reference",
)


def _write_main_figure_contract(output_dir: Path) -> None:
    tables = output_dir / "tables"
    metadata = output_dir / "metadata"
    tables.mkdir(parents=True)
    metadata.mkdir(parents=True)
    primary_rows = []
    for route_index, route_id in enumerate(ROUTES):
        row: dict[str, object] = {"route_id": route_id}
        for metric_index, metric_id in enumerate(ROUTE_METRICS):
            value = 0.2 + 0.1 * route_index + 0.01 * metric_index
            row[metric_id] = value
            row[f"{metric_id}_resampling_median"] = value + 0.005
            row[f"{metric_id}_sensitivity_lower"] = value - 0.02
            row[f"{metric_id}_sensitivity_upper"] = value + 0.02
        primary_rows.append(row)
    pd.DataFrame(primary_rows).to_csv(
        tables / "exp3_primary_route_results.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "contrast_id": "ridge_over_historical",
                "metric_id": "ridge_over_historical_paired_value_gain",
                "full_sample_estimate": 0.02,
                "resampling_median": 0.01,
                "sensitivity_lower": -0.03,
                "sensitivity_upper": 0.04,
            }
        ]
    ).to_csv(tables / "exp3_paired_ranking_contrast.csv", index=False)
    pd.DataFrame(
        [
            {
                "action_coverage": 0.9,
                "reference_pair_coverage": 0.88,
                "audit_unit_coverage": 0.95,
                "supported_action_count_mean": 18.1,
            }
        ]
    ).to_csv(tables / "exp3_support_coverage.csv", index=False)
    pd.DataFrame(
        [
            {
                "split_id": "evaluation",
                "design_scope": "active_run",
                "selected_action_count": 20,
                "selected_action_exposure_mass_coverage": 0.85,
            }
        ]
    ).to_csv(tables / "exp3_action_space_coverage.csv", index=False)
    pd.DataFrame(
        {
            "metric_id": [*ROUTE_METRICS, "ridge_over_historical_paired_value_gain"],
            "deprecated": False,
        }
    ).to_csv(
        tables / "exp3_metric_registry.csv", index=False
    )
    (metadata / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "fixture-run",
                "config_hash": "config",
                "input_manifest_hash": "inputs",
                "code_version_type": "source_tree_sha256",
                "code_version": "code",
                "metric_registry_hash": "registry",
                "design_contract_hash": "design",
            }
        ),
        encoding="utf-8",
    )
    (metadata / "exp3_ridge_selection_manifest.json").write_text(
        json.dumps({"selected_alpha": 3.0}), encoding="utf-8"
    )


def _render(output_dir: Path) -> pd.DataFrame:
    _write_main_figure_contract(output_dir)
    plot_main_figure(output_dir, "fast", paper_result=False)
    return pd.read_csv(
        output_dir / "figures" / "data" / "exp3_main_score_gap_ranking_data.csv"
    )


def test_main_figure_reads_frozen_tables_only(tmp_path: Path) -> None:
    assert not (tmp_path / "derived").exists()
    assert not (tmp_path / "processed").exists()
    figure = _render(tmp_path)
    assert not figure.empty
    assert not (tmp_path / "derived").exists()
    assert not (tmp_path / "processed").exists()


def test_main_figure_uses_canonical_metric_names(tmp_path: Path) -> None:
    figure = _render(tmp_path)
    metric_ids = set(figure["metric_id"].dropna().astype(str))
    assert set(ROUTE_METRICS).issubset(metric_ids)
    assert "heldout_gap_defect" not in metric_ids
    assert "top_action_match_rate" not in metric_ids


def test_scope_note_matches_active_support_table() -> None:
    support = pd.Series(
        {
            "action_coverage": 0.9,
            "reference_pair_coverage": 0.8,
            "audit_unit_coverage": 0.7,
            "supported_action_count_mean": 12.5,
        }
    )
    coverage = pd.DataFrame(
        [
            {
                "split_id": "evaluation",
                "design_scope": "active_run",
                "selected_action_count": 20,
                "selected_action_exposure_mass_coverage": 0.85,
            }
        ]
    )
    note = build_scope_note(support, coverage)
    assert "Top-20" in note and "85.0%" in note
    assert "reference-pair coverage 80.0%" in note


def test_no_complete_support_claim_when_coverage_below_one() -> None:
    support = pd.Series(
        {
            "action_coverage": 0.9,
            "reference_pair_coverage": 0.8,
            "audit_unit_coverage": 0.7,
            "supported_action_count_mean": 12.5,
        }
    )
    coverage = pd.DataFrame(
        [
            {
                "split_id": "evaluation",
                "design_scope": "active_run",
                "selected_action_count": 20,
                "selected_action_exposure_mass_coverage": 0.85,
            }
        ]
    )
    assert "complete" not in build_scope_note(support, coverage).lower()


def test_ranking_panel_contains_paired_gain(tmp_path: Path) -> None:
    figure = _render(tmp_path)
    paired = figure[
        figure["metric_id"] == "ridge_over_historical_paired_value_gain"
    ]
    assert len(paired) == 1
    assert paired.iloc[0]["panel_id"] == "panel_c_ranking"


def test_figure_data_reproduces_primary_tables(tmp_path: Path) -> None:
    _render(tmp_path)
    passed, detail = main_figure_data_matches(tmp_path)
    assert passed, detail
