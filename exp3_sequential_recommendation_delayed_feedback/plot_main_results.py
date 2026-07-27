"""Paper-style score--gap--ranking figure from frozen derived tables only."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from figure_bundle import write_figure_bundle
from utilities import sha256_file

ROUTE_ORDER = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
DISPLAY = {
    "arrival_carrier": "Arrival carrier",
    "history_mean_control": "Historical mean",
    "ridge_proxy": "Ridge proxy",
}
MARKERS = {"arrival_carrier": "o", "history_mean_control": "s", "ridge_proxy": "D"}
COLORS = {
    "arrival_carrier": "#B24A3A",
    "history_mean_control": "#4C72B0",
    "ridge_proxy": "#2A7F62",
}
PANEL_A_TITLE = "History-based score calibration on common held-out support"
SENSITIVITY_CAPTION = (
    "The open markers and horizontal ranges summarize the empirical user-cluster "
    "resampling distribution. They are sensitivity diagnostics rather than confidence "
    "intervals and need not contain the full-sample estimate."
)


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _validated_range(low: float, high: float) -> tuple[float, float]:
    values = np.asarray([low, high], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Non-finite sensitivity range: {values.tolist()}")
    if low > high:
        raise ValueError(f"Invalid sensitivity range ordering: lower={low}, upper={high}")
    return float(low), float(high)


def _evaluation_exposure_scope(table: pd.DataFrame, scope: str) -> tuple[int, float]:
    selected = table[(table["split_id"] == "evaluation") & (table["design_scope"] == scope)]
    if len(selected) != 1:
        raise RuntimeError(f"Expected exactly one evaluation exposure-mass row for {scope}")
    return (
        int(selected.iloc[0]["selected_action_count"]),
        float(selected.iloc[0]["selected_action_exposure_mass_coverage"]),
    )


def _draw_sensitivity_distribution(
    ax: plt.Axes,
    *,
    point: float,
    median: float,
    low: float,
    high: float,
    y: float,
    route_id: str,
) -> None:
    """Separate the full-sample point from the empirical resampling distribution."""
    low, high = _validated_range(low, high)
    cap = 0.10
    ax.hlines(y, low, high, color=COLORS[route_id], linewidth=1.6, alpha=0.65, zorder=1)
    ax.vlines([low, high], y - cap, y + cap, color=COLORS[route_id], linewidth=0.9, alpha=0.65, zorder=1)
    ax.plot(
        median,
        y,
        marker=MARKERS[route_id],
        markerfacecolor="white",
        markeredgecolor=COLORS[route_id],
        markersize=5.0,
        linestyle="none",
        zorder=2,
    )
    ax.plot(
        point,
        y,
        marker=MARKERS[route_id],
        color=COLORS[route_id],
        markersize=5.2,
        linestyle="none",
        zorder=3,
    )


def _axis_limits(values: list[float], *, include_zero: bool, right_pad: float = 0.08) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return (0.0, 1.0)
    lower = float(finite.min())
    upper = float(finite.max())
    if include_zero:
        lower = min(0.0, lower)
        upper = max(0.0, upper)
    span = max(upper - lower, 1e-6)
    return lower - 0.04 * span, upper + right_pad * span


def plot_main_figure(output_dir: Path, run_tier: str, paper_result: bool) -> None:
    source_paths = [
        output_dir / "tables" / "exp3_primary_route_results.csv",
        output_dir / "tables" / "exp3_decile_calibration.csv",
        output_dir / "tables" / "exp3_support_coverage.csv",
        output_dir / "tables" / "exp3_paired_ranking_contrast.csv",
        output_dir / "tables" / "exp3_action_space_coverage.csv",
    ]
    results = _read(source_paths[0])
    calibration = _read(source_paths[1])
    support = _read(source_paths[2]).iloc[0]
    paired = _read(source_paths[3]).iloc[0]
    action_coverage = _read(source_paths[4])
    selected_action_count, exposure_mass = _evaluation_exposure_scope(
        action_coverage, "active_run"
    )
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    missing = [route for route in ROUTE_ORDER if route not in set(results["route_id"])]
    if missing:
        raise RuntimeError(f"Main figure is missing routes: {missing}")
    results = results.set_index("route_id").loc[ROUTE_ORDER].reset_index()

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
        }
    )
    fig = plt.figure(figsize=(7.35, 5.35), constrained_layout=False)
    outer = fig.add_gridspec(2, 1, height_ratios=[1.22, 1.0], hspace=0.56)
    ax_score = fig.add_subplot(outer[0, 0])
    bottom = outer[1, 0].subgridspec(1, 4, width_ratios=[1.25, 0.38, 1.25, 0.34], wspace=0.12)
    ax_gap = fig.add_subplot(bottom[0, 0])
    ax_sign = fig.add_subplot(bottom[0, 1], sharey=ax_gap)
    ax_rank = fig.add_subplot(bottom[0, 2], sharey=ax_gap)
    ax_top = fig.add_subplot(bottom[0, 3], sharey=ax_gap)
    source_rows: list[dict[str, object]] = []

    # Panel A reports the primary full-sample calibration only. Resampling
    # sensitivity for calibration remains in the table/audit, avoiding a false
    # confidence-band interpretation.
    label_positions: list[tuple[float, float, str, str]] = []
    for route_id in ("history_mean_control", "ridge_proxy"):
        route = calibration[calibration["route_id"] == route_id].sort_values("calibration_decile")
        x = route["mean_predicted_target"].to_numpy(float)
        y = route["mean_observed_target"].to_numpy(float)
        ax_score.plot(x, y, color=COLORS[route_id], linewidth=0.9, alpha=0.68, zorder=2)
        ax_score.plot(
            x,
            y,
            marker=MARKERS[route_id],
            color=COLORS[route_id],
            markersize=3.8,
            linestyle="none",
            zorder=3,
        )
        if len(route):
            label_positions.append((float(x[-1]), float(y[-1]), route_id, DISPLAY[route_id]))
        for record in route.to_dict("records"):
            source_rows.append({"panel_id": "panel_a_score", **record})

    finite = calibration[["mean_predicted_target", "mean_observed_target"]].to_numpy(float)
    finite = finite[np.isfinite(finite)]
    lower = float(finite.min()) if finite.size else 0.0
    upper = float(finite.max()) if finite.size else 1.0
    padding = max(0.04, 0.08 * max(upper - lower, 1e-6))
    lower -= padding
    upper += 2.2 * padding
    ax_score.plot([lower, upper], [lower, upper], linestyle="--", color="0.40", linewidth=0.9)
    for x, y, route_id, label in label_positions:
        ax_score.annotate(
            label,
            xy=(x, y),
            xytext=(6, 0),
            textcoords="offset points",
            color=COLORS[route_id],
            fontsize=7,
            va="center",
            fontweight="semibold",
        )
    ax_score.set_xlim(lower, upper)
    ax_score.set_ylim(lower, upper)
    ax_score.set_xlabel("Mean predicted constructed 6h target (log1p)")
    ax_score.set_ylabel("Mean held-out constructed 6h target (log1p)")
    ax_score.set_title(f"(a) {PANEL_A_TITLE}", loc="left", fontweight="semibold")
    ax_score.grid(alpha=0.18, linewidth=0.6)

    y_positions = np.arange(len(ROUTE_ORDER), dtype=float)
    gap_values: list[float] = []
    rank_values: list[float] = []
    for y_pos, route_id in zip(y_positions, ROUTE_ORDER):
        row = results[results["route_id"] == route_id].iloc[0]

        gap_point = float(row.heldout_gap_defect)
        gap_median = float(row.heldout_gap_defect_resampling_median)
        gap_low = float(row.heldout_gap_defect_sensitivity_lower)
        gap_high = float(row.heldout_gap_defect_sensitivity_upper)
        _draw_sensitivity_distribution(
            ax_gap,
            point=gap_point,
            median=gap_median,
            low=gap_low,
            high=gap_high,
            y=y_pos,
            route_id=route_id,
        )
        gap_values.extend([gap_point, gap_median, gap_low, gap_high])
        ax_sign.text(0.5, y_pos, f"{float(row.gap_sign_agreement):.2f}", ha="center", va="center", fontsize=7)
        source_rows.append(
            {
                "panel_id": "panel_b_gap",
                "route_id": route_id,
                "full_sample_estimate": gap_point,
                "resampling_median": gap_median,
                "sensitivity_lower": gap_low,
                "sensitivity_upper": gap_high,
                "gap_sign_agreement": row.gap_sign_agreement,
                "pair_coverage": support.pair_coverage,
                "valid_audit_unit_count": row.valid_audit_unit_count,
            }
        )

        rank_point = float(row.cross_fitted_ranking_shortfall)
        rank_median = float(row.cross_fitted_ranking_shortfall_resampling_median)
        rank_low = float(row.cross_fitted_ranking_shortfall_sensitivity_lower)
        rank_high = float(row.cross_fitted_ranking_shortfall_sensitivity_upper)
        _draw_sensitivity_distribution(
            ax_rank,
            point=rank_point,
            median=rank_median,
            low=rank_low,
            high=rank_high,
            y=y_pos,
            route_id=route_id,
        )
        rank_values.extend([rank_point, rank_median, rank_low, rank_high])
        ax_top.text(0.5, y_pos, f"{float(row.top_action_match_rate):.2f}", ha="center", va="center", fontsize=7)
        source_rows.append(
            {
                "panel_id": "panel_c_ranking",
                "route_id": route_id,
                "full_sample_estimate": rank_point,
                "resampling_median": rank_median,
                "sensitivity_lower": rank_low,
                "sensitivity_upper": rank_high,
                "top_action_match_rate": row.top_action_match_rate,
                "valid_audit_unit_count": row.valid_audit_unit_count,
            }
        )

    ax_gap.axvline(0.0, linestyle="--", color="0.45", linewidth=0.8)
    ax_gap.set_xlim(*_axis_limits(gap_values, include_zero=True))
    ax_gap.set_yticks(y_positions, [DISPLAY[route] for route in ROUTE_ORDER])
    ax_gap.invert_yaxis()
    ax_gap.set_xlabel("Maximum held-out gap error\n(lower is better)")
    ax_gap.set_title("(b) Action-gap recovery", loc="left", fontweight="semibold")
    ax_gap.grid(axis="x", alpha=0.18, linewidth=0.6)

    ax_rank.axvline(0.0, linestyle="--", color="0.45", linewidth=0.8)
    ax_rank.set_xlim(*_axis_limits(rank_values, include_zero=True))
    ax_rank.tick_params(axis="y", labelleft=False)
    ax_rank.set_xlabel("Selected-action value shortfall\n(signed; lower is better)")
    ax_rank.set_title("(c) Offline ranking recovery", loc="left", fontweight="semibold")
    ax_rank.grid(axis="x", alpha=0.18, linewidth=0.6)

    for metric_ax, title in ((ax_sign, "Sign\nagreement"), (ax_top, "Top-action\nmatch")):
        metric_ax.set_xlim(0.0, 1.0)
        metric_ax.set_xticks([])
        metric_ax.tick_params(axis="y", left=False, labelleft=False)
        for spine in metric_ax.spines.values():
            spine.set_visible(False)
        metric_ax.set_title(title, fontsize=7, fontweight="semibold", pad=5)

    legend = [
        Line2D([0], [0], marker="o", color="0.25", markerfacecolor="0.25", linestyle="none", label="Full-sample estimate"),
        Line2D([0], [0], marker="o", color="0.45", markerfacecolor="white", linestyle="-", label="Resampling median and 95% sensitivity range"),
    ]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.065), ncol=2, frameon=False, fontsize=6.5)
    fig.text(
        0.10,
        0.018,
        (
            f"Primary support is complete within the selected top-{selected_action_count} action space; "
            f"these actions cover {exposure_mass:.1%} of evaluation exposure mass.  "
            f"Pair/audit-unit coverage: {float(support.pair_coverage):.2f}/{float(support.audit_unit_coverage):.2f}."
        ),
        ha="left",
        va="bottom",
        fontsize=6.2,
    )
    fig.subplots_adjust(left=0.14, right=0.98, bottom=0.19, top=0.95)

    figure_id = "exp3_main_score_gap_ranking"
    source_data = pd.DataFrame(source_rows)
    scope_note = (
        f"Primary support is complete within the selected top-{selected_action_count} action "
        f"space; these actions cover {exposure_mass:.1%} of evaluation exposure mass."
    )
    source_data = pd.concat(
        [
            source_data,
            pd.DataFrame(
                [
                    {
                        "panel_id": "figure_scope_summary",
                        "selected_action_count": selected_action_count,
                        "selected_action_exposure_mass_evaluation": exposure_mass,
                        "scope_note": scope_note,
                        "caption_source": SENSITIVITY_CAPTION,
                        "interval_role": "sensitivity",
                        "formal_ci_validated": False,
                    }
                ]
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    for key, value in {
        "run_id": manifest.get("run_id", "unknown"),
        "run_tier": run_tier,
        "paper_result": paper_result,
        "analysis_tier": "primary",
        "experiment_id": "exp3",
        "config_hash": manifest.get("config_hash", "unknown"),
        "input_manifest_hash": manifest.get("input_manifest_hash", "unknown"),
        "code_version_type": manifest.get("code_version_type", "unknown"),
        "code_version": manifest.get("code_version", "unknown"),
    }.items():
        source_data[key] = value
    metadata = {
        "experiment_id": "exp3",
        "run_tier": run_tier,
        "paper_result": paper_result,
        "panel_definitions": {
            "panel_a": "history-based held-out action-cell calibration for Historical mean and Ridge proxy",
            "panel_b": "full-sample gap defect plus empirical user-resampling sensitivity distribution",
            "panel_c": "full-sample signed ranking shortfall plus empirical user-resampling sensitivity distribution",
        },
        "route_order": ROUTE_ORDER,
        "uncertainty_definition": SENSITIVITY_CAPTION,
        "caption_source": SENSITIVITY_CAPTION,
        "interval_role": "sensitivity",
        "formal_ci_validated": False,
        "support_definition": "common two-fold event support within day-by-user-group audit units",
        "selected_action_count": selected_action_count,
        "selected_action_exposure_mass_evaluation": exposure_mass,
        "scope_note": scope_note,
        "interpretation_boundary": "logged-support recoverability diagnostic; not OPE, causal policy value, or structural causal regret",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_derived_files": [path.relative_to(output_dir).as_posix() for path in source_paths],
        "source_file_hashes": {path.relative_to(output_dir).as_posix(): sha256_file(path) for path in source_paths},
        "code_version_type": manifest.get("code_version_type", "unknown"),
        "code_version": manifest.get("code_version", "unknown"),
        "config_hash": manifest.get("config_hash", "unknown"),
        "input_manifest_hash": manifest.get("input_manifest_hash", "unknown"),
        "axis_definitions": {
            "panel_a_x": "mean predicted constructed 6h target",
            "panel_a_y": "mean held-out constructed 6h target",
            "panel_b_x": "maximum held-out action-gap defect; nonnegative estimand",
            "panel_c_x": "signed cross-fitted ranking shortfall; negative values allowed",
        },
        "range_rendering": "Sensitivity ranges represent the empirical resampling distribution and are not expected to contain the full-sample point.",
    }
    write_figure_bundle(fig, source_data, output_dir, figure_id, metadata)
    plt.close(fig)
