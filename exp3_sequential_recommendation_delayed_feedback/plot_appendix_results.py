"""Appendix support-preflight and arrival-carrier diagnostics from frozen files."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from figure_bundle import write_figure_bundle
from plot_appendix_additional import plot_additional_appendix_figures
from plot_appendix_diagnostics import _draw_arrival_carrier, _draw_dependence_structure
from plot_appendix_support import (
    _candidate_labels,
    _draw_full_support_preflight,
    _prepare_full_support_preflight,
)
from utilities import sha256_file


def _attach_figure_provenance(
    source_data: pd.DataFrame,
    provenance: dict[str, object],
) -> pd.DataFrame:
    """Add display provenance without replacing scientific row provenance."""
    output = source_data.copy()
    for key, value in provenance.items():
        if key != "generated_at_utc":
            output[f"figure_{key}"] = value
    return output

def _provenance(output_dir: Path, run_tier: str, paper_result: bool) -> dict[str, object]:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "run_id": manifest.get("run_id", "unknown"),
        "run_tier": run_tier,
        "paper_result": paper_result,
        "analysis_tier": "appendix",
        "experiment_id": "exp3",
        "config_hash": manifest.get("config_hash", "unknown"),
        "input_manifest_hash": manifest.get("input_manifest_hash", "unknown"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_version_type": manifest.get("code_version_type", "unknown"),
        "code_version": manifest.get("code_version", "unknown"),
    }


def plot_appendix_figures(output_dir: Path, run_tier: str, paper_result: bool) -> None:
    provenance = _provenance(output_dir, run_tier, paper_result)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 6.5,
            "axes.linewidth": 0.8,
        }
    )

    preflight_path = output_dir / "diagnostics" / "exp3_full_design_support_preflight.json"
    action_support_path = output_dir / "derived" / "exp3_full_design_support_by_action.csv"
    preflight_summary_path = output_dir / "tables" / "exp3_full_design_support_preflight.csv"
    coverage_path = output_dir / "tables" / "exp3_action_space_coverage.csv"
    full_vocab_path = output_dir / "design" / "exp3_full_design_action_vocabulary.csv"
    support_sources = [preflight_path, action_support_path, preflight_summary_path, coverage_path, full_vocab_path]
    if all(path.exists() for path in support_sources):
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        action_summary = pd.read_csv(action_support_path)
        if not action_summary.empty:
            actions, metrics = _prepare_full_support_preflight(
                action_summary,
                pd.read_csv(preflight_summary_path),
                pd.read_csv(coverage_path),
                pd.read_csv(full_vocab_path),
            )
            figure = _draw_full_support_preflight(
                actions,
                metrics,
                int(preflight["support_threshold"]),
                int(preflight["display_user_group_count"]),
                str(preflight["status"]),
            )
            source_data = pd.concat(
                [
                    actions.assign(panel_id="panel_a_full_design_action_support"),
                    metrics.assign(panel_id="panel_b_full_design_readiness"),
                ],
                ignore_index=True,
                sort=False,
            )
            source_data = _attach_figure_provenance(source_data, provenance)
            write_figure_bundle(
                figure,
                source_data,
                output_dir,
                "exp3_appendix_full_design_support_preflight",
                {
                    **provenance,
                    "source_derived_files": [path.relative_to(output_dir).as_posix() for path in support_sources],
                    "source_file_hashes": {path.relative_to(output_dir).as_posix(): sha256_file(path) for path in support_sources},
                    "interpretation": "Full top-20, formal-threshold support readiness and selected-action exposure scope; this does not alter the active fast estimand.",
                },
                figure_section="appendix",
            )
            plt.close(figure)

    plot_additional_appendix_figures(output_dir, provenance)

    delay_path = output_dir / "diagnostics" / "exp3_arrival_carrier_audit.csv"
    action_path = output_dir / "diagnostics" / "exp3_arrival_carrier_action_audit.csv"
    summary_path = output_dir / "diagnostics" / "exp3_arrival_carrier_summary.json"
    vocab_path = output_dir / "design" / "exp3_action_vocabulary.csv"
    arrival_sources = [delay_path, action_path, summary_path, vocab_path]
    if all(path.exists() for path in arrival_sources):
        delay = pd.read_csv(delay_path)
        action = pd.read_csv(action_path).merge(_candidate_labels(pd.read_csv(vocab_path)), on="action_id", how="left")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not delay.empty and not action.empty:
            figure = _draw_arrival_carrier(delay, action, float(summary["source_carrier_exact_match_rate"]))
            source_data = pd.concat(
                [
                    delay.assign(panel_id="panel_a_carrier_lag"),
                    action.assign(panel_id="panel_b_action_match"),
                ],
                ignore_index=True,
                sort=False,
            )
            source_data = _attach_figure_provenance(source_data, provenance)
            write_figure_bundle(
                figure,
                source_data,
                output_dir,
                "exp3_appendix_arrival_carrier_diagnostic",
                {
                    **provenance,
                    "source_derived_files": [path.relative_to(output_dir).as_posix() for path in arrival_sources],
                    "source_file_hashes": {path.relative_to(output_dir).as_posix(): sha256_file(path) for path in arrival_sources},
                    "interpretation": "Mechanism diagnostic for pseudo-arrival carrier lag and source-action matching; exact source-event matching is reported as annotation only.",
                },
                figure_section="appendix",
            )
            plt.close(figure)

    reuse_path = output_dir / "derived" / "exp3_outcome_reuse_quantiles.csv"
    dependence_path = output_dir / "tables" / "exp3_data_dependence_structure.csv"
    resampling_structure_path = output_dir / "tables" / "exp3_resampling_structure_diagnostics.csv"
    dependence_json_path = output_dir / "diagnostics" / "exp3_data_dependence_structure.json"
    selection_json_path = output_dir / "diagnostics" / "exp3_resampling_structure_diagnostics.json"
    dependence_sources = [
        reuse_path, dependence_path, resampling_structure_path, dependence_json_path, selection_json_path
    ]
    if all(path.exists() for path in dependence_sources):
        reuse = pd.read_csv(reuse_path)
        resampling_structure = pd.read_csv(resampling_structure_path)
        if not reuse.empty and not resampling_structure.empty:
            figure = _draw_dependence_structure(reuse, resampling_structure)
            source_data = pd.concat(
                [
                    reuse.assign(panel_id="panel_a_outcome_reuse"),
                    resampling_structure.assign(panel_id="panel_b_selection_instability"),
                ],
                ignore_index=True,
                sort=False,
            )
            source_data = _attach_figure_provenance(source_data, provenance)
            write_figure_bundle(
                figure,
                source_data,
                output_dir,
                "exp3_appendix_dependence_and_selection_structure",
                {
                    **provenance,
                    "source_derived_files": [path.relative_to(output_dir).as_posix() for path in dependence_sources],
                    "source_file_hashes": {path.relative_to(output_dir).as_posix(): sha256_file(path) for path in dependence_sources},
                    "interpretation": (
                        "Overlapping six-hour target windows and data-dependent support/reference/argmax changes explain "
                        "why user-cluster resampling is reported as sensitivity analysis rather than formal confidence inference."
                    ),
                    "formal_ci_validated": False,
                },
                figure_section="appendix",
            )
            plt.close(figure)
