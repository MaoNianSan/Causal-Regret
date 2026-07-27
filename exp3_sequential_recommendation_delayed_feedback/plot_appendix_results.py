"""Appendix support-preflight and arrival-carrier diagnostics from frozen files."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figure_bundle import write_figure_bundle
from utilities import sha256_file


READY_COLOR = "#2A7F62"
LIMITED_COLOR = "#9C3D35"
ACTION_COLOR = "#4C72B0"


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


def _candidate_labels(vocabulary: pd.DataFrame) -> pd.DataFrame:
    required = {"action_id", "action_display_name", "is_candidate_action"}
    missing = required.difference(vocabulary.columns)
    if missing:
        raise ValueError(f"Action vocabulary is missing columns: {sorted(missing)}")
    candidate = vocabulary.copy()
    candidate["is_candidate_action"] = candidate["is_candidate_action"].astype(str).str.lower().isin({"true", "1"})
    return candidate[candidate["is_candidate_action"]][["action_id", "action_display_name"]].drop_duplicates("action_id")


def _prepare_full_support_preflight(
    action_summary: pd.DataFrame,
    preflight_summary: pd.DataFrame,
    action_space_coverage: pd.DataFrame,
    vocabulary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "action_id",
        "supported_unit_rate",
        "minimum_fold_count_p10",
        "minimum_fold_count_median",
        "minimum_fold_count_p90",
    }
    missing = required.difference(action_summary.columns)
    if missing:
        raise ValueError(f"Full-design action support file is missing columns: {sorted(missing)}")
    actions = action_summary.merge(_candidate_labels(vocabulary), on="action_id", how="left", validate="one_to_one")
    if actions["action_display_name"].isna().any():
        raise ValueError("Full-design support actions are missing display labels")
    actions = actions.sort_values(["minimum_fold_count_median", "action_id"], kind="stable").reset_index(drop=True)
    actions["action_rank"] = np.arange(1, len(actions) + 1)

    evaluation = preflight_summary[preflight_summary["split_id"] == "evaluation"]
    if len(evaluation) != 1:
        raise ValueError("Full-design preflight must contain one displayed evaluation summary")
    row = evaluation.iloc[0]
    mass = action_space_coverage[
        (action_space_coverage["split_id"] == "evaluation")
        & (action_space_coverage["design_scope"] == "full_design_preflight")
    ]
    if len(mass) != 1:
        raise ValueError("Action-space coverage must contain one evaluation full-design row")
    metrics = pd.DataFrame(
        [
            {"metric_id": "action_coverage", "display_name": "Action support", "value": float(row["action_coverage"])},
            {"metric_id": "pair_coverage", "display_name": "Pair support", "value": float(row["pair_coverage"])},
            {"metric_id": "audit_unit_coverage", "display_name": "Valid units", "value": float(row["audit_unit_coverage"])},
            {
                "metric_id": "exposure_mass_coverage",
                "display_name": "Exposure mass",
                "value": float(mass.iloc[0]["selected_action_exposure_mass_coverage"]),
            },
        ]
    )
    if not np.isfinite(metrics["value"]).all() or ((metrics["value"] < 0) | (metrics["value"] > 1)).any():
        raise ValueError("Full-design coverage metrics must lie in [0, 1]")
    return actions, metrics


def _draw_full_support_preflight(
    actions: pd.DataFrame,
    metrics: pd.DataFrame,
    threshold: int,
    group_count: int,
    status: str,
) -> plt.Figure:
    height = max(4.4, 2.7 + 0.20 * len(actions))
    fig = plt.figure(figsize=(7.5, height))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.75, 0.80], wspace=0.62)
    ax_actions = fig.add_subplot(grid[0, 0])
    ax_metrics = fig.add_subplot(grid[0, 1])

    y = np.arange(len(actions), dtype=float)
    low = actions["minimum_fold_count_p10"].to_numpy(float)
    median = actions["minimum_fold_count_median"].to_numpy(float)
    high = actions["minimum_fold_count_p90"].to_numpy(float)
    rates = actions["supported_unit_rate"].to_numpy(float)
    ax_actions.hlines(y, low, high, linewidth=1.8, color=ACTION_COLOR)
    ax_actions.scatter(median, y, s=25, c=[READY_COLOR if rate >= 0.8 else LIMITED_COLOR for rate in rates], zorder=3)
    ax_actions.axvline(threshold, linestyle="--", linewidth=1.0, color="0.35")
    labels = []
    for display, rate in zip(actions["action_display_name"].astype(str), rates):
        short = display if len(display) <= 20 else display[:17] + "…"
        labels.append(f"{short} ({rate:.0%})")
    ax_actions.set_yticks(y, labels)
    ax_actions.invert_yaxis()
    ax_actions.set_xlabel("Minimum events per fold (median; 10–90% range)")
    ax_actions.set_title("(a) Full-design cell support by action", loc="left", fontweight="semibold")
    ax_actions.grid(axis="x", alpha=0.18)

    y2 = np.arange(len(metrics), dtype=float)
    values = metrics["value"].to_numpy(float)
    ax_metrics.hlines(y2, 0, values, color="0.72", linewidth=2.0)
    ax_metrics.scatter(values, y2, s=35, c=[READY_COLOR if value >= 0.8 else LIMITED_COLOR for value in values], zorder=3)
    ax_metrics.axvline(0.8, linestyle="--", linewidth=1.0, color="0.35")
    ax_metrics.set_xlim(0, 1.03)
    ax_metrics.set_yticks(y2, metrics["display_name"].astype(str))
    ax_metrics.invert_yaxis()
    ax_metrics.set_xlabel("Coverage")
    ax_metrics.set_title(
        f"(b) Readiness and scope\nG={group_count}; threshold={threshold}/fold",
        loc="left",
        fontweight="semibold",
    )
    ax_metrics.grid(axis="x", alpha=0.18)
    for value, yy in zip(values, y2):
        ax_metrics.text(min(value + 0.025, 1.0), yy, f"{value:.0%}", va="center", fontsize=7)
    ax_metrics.text(
        0.02,
        -0.09,
        f"Status: {status}",
        transform=ax_metrics.transAxes,
        fontsize=7,
        va="top",
    )
    fig.subplots_adjust(left=0.15, right=0.98, top=0.91, bottom=0.13)
    return fig


def _draw_arrival_carrier(delay: pd.DataFrame, actions: pd.DataFrame, exact_rate: float) -> plt.Figure:
    fig = plt.figure(figsize=(7.25, 3.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.0], wspace=0.42)
    ax_lag = fig.add_subplot(grid[0, 0])
    ax_action = fig.add_subplot(grid[0, 1])

    x = np.arange(len(delay), dtype=float)
    low = delay["lag_hours_p10"].to_numpy(float)
    median = delay["lag_hours_median"].to_numpy(float)
    high = delay["lag_hours_p90"].to_numpy(float)
    ax_lag.vlines(x, low, high, color=ACTION_COLOR, linewidth=2.0)
    ax_lag.scatter(x, median, color=ACTION_COLOR, s=28)
    ax_lag.set_xticks(x, delay["delay_bin"].astype(str))
    ax_lag.set_ylabel("Source-to-carrier lag (hours)")
    ax_lag.set_xlabel("Pseudo-arrival delay bin")
    ax_lag.set_title("(a) Carrier lag distribution", loc="left", fontweight="semibold")
    ax_lag.grid(axis="y", alpha=0.18)

    actions = actions.sort_values("action_match_rate", kind="stable").reset_index(drop=True)
    y = np.arange(len(actions), dtype=float)
    rates = actions["action_match_rate"].to_numpy(float)
    ax_action.hlines(y, 0, rates, color="0.72", linewidth=2.0)
    ax_action.scatter(rates, y, color=ACTION_COLOR, s=28)
    ax_action.set_xlim(0, max(0.5, float(rates.max()) * 1.12))
    ax_action.set_yticks(y, actions["action_display_name"].astype(str))
    ax_action.set_xlabel("Source–carrier action match rate")
    ax_action.set_title("(b) Match rate by source action", loc="left", fontweight="semibold")
    ax_action.grid(axis="x", alpha=0.18)
    ax_action.text(
        0.98,
        0.04,
        f"Exact source-event match: {exact_rate:.2%}",
        transform=ax_action.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
    )
    fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.17)
    return fig



def _draw_dependence_structure(
    reuse_quantiles: pd.DataFrame,
    resampling_structure: pd.DataFrame,
) -> plt.Figure:
    fig = plt.figure(figsize=(7.35, 3.5))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.42)
    ax_reuse = fig.add_subplot(grid[0, 0])
    ax_switch = fig.add_subplot(grid[0, 1])

    split_display = {"history": "History", "evaluation": "Evaluation"}
    markers = {"history": "o", "evaluation": "s"}
    for split_id, group in reuse_quantiles.groupby("split_id", observed=True):
        group = group.sort_values("quantile")
        ax_reuse.plot(
            100.0 * group["quantile"].to_numpy(float),
            group["source_windows_per_outcome_event"].to_numpy(float),
            marker=markers.get(str(split_id), "o"),
            markersize=3.5,
            linewidth=1.1,
            label=split_display.get(str(split_id), str(split_id)),
        )
    ax_reuse.set_yscale("log")
    ax_reuse.set_xlabel("Outcome-event reuse quantile (%)")
    ax_reuse.set_ylabel("Source windows containing one outcome event")
    ax_reuse.set_title("(a) Overlapping-target dependence", loc="left", fontweight="semibold")
    ax_reuse.grid(alpha=0.18)
    ax_reuse.legend(frameon=False, fontsize=7)

    route_order = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
    route_display = {
        "arrival_carrier": "Arrival carrier",
        "history_mean_control": "Historical mean",
        "ridge_proxy": "Ridge proxy",
    }
    metric_specs = (
        ("support_set_switch_rate_mean", "Support set", "o"),
        ("reference_action_switch_rate_mean", "Reference action", "s"),
        ("route_selected_action_switch_rate_mean", "Selected action", "D"),
    )
    table = resampling_structure.set_index("route_id").reindex(route_order)
    y = np.arange(len(route_order), dtype=float)
    offsets = np.linspace(-0.18, 0.18, len(metric_specs))
    for offset, (column, label, marker) in zip(offsets, metric_specs):
        values = table[column].to_numpy(float)
        ax_switch.scatter(values, y + offset, marker=marker, s=28, label=label)
    ax_switch.set_yticks(y, [route_display[route] for route in route_order])
    ax_switch.invert_yaxis()
    ax_switch.set_xlim(left=0.0)
    ax_switch.set_xlabel("Mean switch rate across user resamples")
    ax_switch.set_title("(b) Data-dependent selection instability", loc="left", fontweight="semibold")
    ax_switch.grid(axis="x", alpha=0.18)
    ax_switch.legend(frameon=False, fontsize=6.8, loc="lower right")
    fig.subplots_adjust(left=0.11, right=0.98, top=0.91, bottom=0.17)
    return fig

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
