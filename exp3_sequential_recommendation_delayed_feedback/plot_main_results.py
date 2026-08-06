"""Render the canonical two-row, three-column Exp3 main figure."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

from figure_bundle import write_figure_bundle
from plot_contract import (
    COLORS,
    PANEL_A_TITLE,
    SENSITIVITY_CAPTION,
    _evaluation_exposure_scope,
    _validated_range,
    load_main_figure_inputs,
)
from plot_gap_panel import draw_gap_panels
from plot_ranking_panel import draw_ranking_panels
from plot_scope_note import build_scope_note
from plot_score_panel import draw_score_panels
from utilities import sha256_file


def plot_main_figure(output_dir: Path, run_tier: str, paper_result: bool) -> None:
    inputs = load_main_figure_inputs(output_dir)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.5,
            "axes.titlesize": 8.5,
            "axes.labelsize": 7.2,
            "xtick.labelsize": 6.7,
            "ytick.labelsize": 6.7,
            "axes.linewidth": 0.8,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(10.2, 5.5), constrained_layout=False)
    rows = []
    rows += draw_score_panels(axes[0, 0], axes[1, 0], inputs.primary)
    rows += draw_gap_panels(axes[0, 1], axes[1, 1], inputs.primary)
    rows += draw_ranking_panels(axes[0, 2], axes[1, 2], inputs.primary, inputs.paired)
    scope_note = build_scope_note(inputs.support, inputs.action_coverage)
    rows.append(
        {
            "panel_id": "figure_scope_summary",
            "metric_id": "support_scope",
            "scope_note": scope_note,
            "formal_ci_validated": False,
            "ridge_refit_in_resampling": False,
        }
    )
    legend = [
        Line2D([0], [0], marker="o", color="0.25", linestyle="none", label="Full-sample estimate"),
        Line2D([0], [0], marker="o", markerfacecolor="white", color="0.45", label="Resampling median and sensitivity range"),
    ]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.055), ncol=2, frameon=False)
    fig.text(0.06, 0.012, scope_note, ha="left", va="bottom", fontsize=6.5)
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.21, top=0.94, wspace=0.34, hspace=0.48)
    source = pd.DataFrame(rows)
    for key, value in {
        "run_id": inputs.manifest.get("run_id", "unknown"),
        "run_tier": run_tier,
        "paper_result": paper_result,
        "analysis_tier": "primary",
        "experiment_id": "exp3",
        "config_hash": inputs.manifest.get("config_hash", "unknown"),
        "input_manifest_hash": inputs.manifest.get("input_manifest_hash", "unknown"),
        "code_version_type": inputs.manifest.get("code_version_type", "unknown"),
        "code_version": inputs.manifest.get("code_version", "unknown"),
    }.items():
        source[key] = value
    metadata = {
        "experiment_id": "exp3",
        "run_tier": run_tier,
        "paper_result": paper_result,
        "evidence_chain": [
            "score recovery",
            "held-out reference-pair gap recovery",
            "logged-supported ranking recovery",
        ],
        "source_derived_files": [path.relative_to(output_dir).as_posix() for path in inputs.source_paths],
        "source_file_hashes": {
            path.relative_to(output_dir).as_posix(): sha256_file(path) for path in inputs.source_paths
        },
        "metric_registry_hash": inputs.manifest.get("metric_registry_hash"),
        "selected_alpha": inputs.selection["selected_alpha"],
        "design_hash": inputs.manifest.get("design_contract_hash"),
        "full_sample_role": "primary_estimate",
        "resampling_role": "empirical_user_resampling_sensitivity_distribution",
        "formal_ci_validated": False,
        "ridge_refit_in_resampling": False,
        "support_scope": "common_logged_supported_action_cells",
        "code_source_tree_hash": inputs.manifest.get("code_version"),
        "code_version_type": inputs.manifest.get("code_version_type"),
        "code_version": inputs.manifest.get("code_version"),
        "scope_note": scope_note,
        "uncertainty_definition": SENSITIVITY_CAPTION,
        "interpretation_boundary": "logged-supported recovery; not OPE, deployment value, or structural causal regret",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_figure_bundle(fig, source, output_dir, "exp3_main_score_gap_ranking", metadata)
    plt.close(fig)
