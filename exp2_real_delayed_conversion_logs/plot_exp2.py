from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from attribution_engine import ROUTE_DISPLAY, ROUTE_META
from src.common import ensure_output_dirs, load_config, make_output_manifest, out_dir, save_run_metadata, write_csv


ARRIVAL_TV = "credit_allocation_tv_distance_vs_arrival_anchor"
ARRIVAL_OVERLAP = "top_k_decision_cell_overlap_vs_arrival_anchor"
ARRIVAL_MASS_DIFF = "top_k_credited_mass_difference_per_1000_events_vs_arrival_anchor"
ESTIMAND_BOUNDARY = (
    "observational logged credit-allocation and source-time decision-cell ranking sensitivity; "
    "not policy value, causal effect, ROI, or deployment evaluation"
)

BUCKET_LABELS = {
    "less_equal_1h": "≤1 h",
    "h1_to_h6": "1–6 h",
    "h6_to_h24": "6–24 h",
    "d1_to_d7": "1–7 d",
    "d7_to_d30": "7–30 d",
}
SHORT_LABELS = {
    "arrival_bin_anchor": "Arrival anchor",
    "first_click": "First click or touch",
    "last_click": "Last click or touch",
    "linear_attribution": "Linear attribution",
    "time_decay_soft": "Time-decay attribution",
    "soft_attribution_em": "EM",
}


def _read(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _paper_result(cfg: dict) -> bool:
    # Full-mode figures are provisional until semantic self-check completes and
    # finalize_exp2.py promotes their bundle metadata.
    return False


def _style(cfg: dict) -> None:
    plt.rcParams.update(
        {
            "font.size": cfg["plots"]["tick_font_size"],
            "axes.labelsize": cfg["plots"]["axis_label_font_size"],
            "axes.titlesize": cfg["plots"]["panel_label_font_size"],
            "legend.fontsize": cfg["plots"]["legend_font_size"],
            "lines.linewidth": cfg["plots"]["line_width"],
        }
    )


def _method_fields(route: str) -> dict:
    interface, role, diagnostic_only, deployable, _ = ROUTE_META[route]
    return {
        "method_id": route,
        "method_display_name": ROUTE_DISPLAY.get(route, route),
        "information_interface": interface,
        "reference_role": role or "none",
        "diagnostic_only": bool(diagnostic_only),
        "deployable": bool(deployable),
    }


def _base_row(cfg: dict, figure_id: str, panel_id: str, metric_id: str, cohort_id: str) -> dict:
    return {
        "figure_id": figure_id,
        "panel_id": panel_id,
        "experiment_id": cfg["experiment"]["experiment_id"],
        "subexperiment_id": "main" if figure_id == "fig_exp2_attribution_sensitivity" else "appendix_diagnostic",
        "setting_id": "source_time_day_cells_top_k_10_window_30d",
        "cohort_id": cohort_id,
        "metric_id": metric_id,
        "metric_formula_id": metric_id,
        "primary_metric": metric_id in {ARRIVAL_TV, ARRIVAL_OVERLAP},
        "primary_horizon": "not_applicable",
        "primary_outcome_id": "binary_credited_conversion_mass",
        "ci_level": float(cfg["statistics"]["uid_bootstrap"]["ci_level"]),
        "uncertainty_unit": "uid",
        "n_bootstrap": int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"]),
        "run_mode": cfg.get("runtime", {}).get("mode", "fast"),
        "paper_result": _paper_result(cfg),
        "estimand_boundary": ESTIMAND_BOUNDARY,
        "notes": "Logged source-time credit-allocation and ranking sensitivity.",
    }


def _write_bundle(
    fig,
    data: pd.DataFrame,
    cfg: dict,
    figure_id: str,
    size: tuple[float, float],
    input_files: list[str],
    metric_id: str,
    metric_formula_id: str | None = None,
    extra_metadata: dict | None = None,
) -> None:
    root = out_dir(cfg, "root")
    paths = {
        "pdf": root / "figures" / "pdf" / f"{figure_id}.pdf",
        "png": root / "figures" / "png" / f"{figure_id}.png",
        "data": root / "figures" / "data" / f"{figure_id}_data.csv",
        "metadata": root / "figures" / "metadata" / f"{figure_id}_metadata.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(paths["pdf"], bbox_inches="tight")
    fig.savefig(paths["png"], dpi=int(cfg["plots"]["dpi"]), bbox_inches="tight")
    write_csv(data, paths["data"])
    metadata = {
        "figure_id": figure_id,
        "figure_status": "generated",
        "paper_result": _paper_result(cfg),
        "run_mode": cfg.get("runtime", {}).get("mode", "fast"),
        "input_data_status": "complete",
        "estimand_boundary": ESTIMAND_BOUNDARY,
        "figure_size_in": list(size),
        "dpi": int(cfg["plots"]["dpi"]),
        "metric_id": metric_id,
        "metric_formula_id": metric_formula_id or metric_id,
        "uncertainty_unit": "uid",
        "ci_level": float(cfg["statistics"]["uid_bootstrap"]["ci_level"]),
        "n_bootstrap": int(cfg["statistics"]["uid_bootstrap"]["n_bootstrap"]),
        "input_files": input_files,
        "config_hash": cfg.get("_config_hash"),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    paths["metadata"].write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    plt.close(fig)


def _asymmetric_error(point: float, low: float, high: float) -> np.ndarray:
    return np.array([[max(point - low, 0.0)], [max(high - point, 0.0)]])


def _figure_routes(cfg: dict) -> list[str]:
    return list(map(str, cfg["reporting"]["main_figure_routes"]))


def main_figure(cfg: dict, summary: pd.DataFrame, delay: pd.DataFrame) -> None:
    _style(cfg)
    fig_id = "fig_exp2_attribution_sensitivity"
    cohort_id = str(cfg["subsets"]["main_cohort_id"])
    size = (float(cfg["plots"]["paper_figure_width_in"]), 2.70)
    fig, axes = plt.subplots(1, 2, figsize=size)

    ordered = ["less_equal_1h", "h1_to_h6", "h6_to_h24", "d1_to_d7", "d7_to_d30"]
    required_delay_columns = {"delay_bucket", "n_eligible_source_events", "source_event_share_percent"}
    missing_delay_columns = required_delay_columns.difference(delay.columns)
    if missing_delay_columns:
        raise RuntimeError(
            "Delay-profile contract failed: expected source-event fields "
            f"{sorted(required_delay_columns)}, missing={sorted(missing_delay_columns)}."
        )
    bucket_col = "delay_bucket"
    share_col = "source_event_share_percent"
    count_col = "n_eligible_source_events"
    profile = delay.set_index(bucket_col).reindex(ordered).fillna(0.0).reset_index().rename(columns={bucket_col: "delay_bucket"})
    axes[0].bar([BUCKET_LABELS[value] for value in ordered], profile[share_col])
    axes[0].set_xlabel("Source-to-conversion delay")
    axes[0].set_ylabel("Share of eligible source events (%)")
    panel_title_font_size = min(float(cfg["plots"]["panel_label_font_size"]), 9.0)
    panel_titles = {
        "panel_a": "(a) Delay composition",
        "panel_b": "(b) Allocation and ranking displacement",
    }
    axes[0].set_title(panel_titles["panel_a"], loc="left", fontweight="bold", fontsize=panel_title_font_size)
    axes[0].grid(axis="y", alpha=0.20)

    routes = _figure_routes(cfg)
    point = summary[summary["route"].isin(routes)].copy()
    point["route"] = pd.Categorical(point["route"], categories=routes, ordered=True)
    point = point.sort_values("route").reset_index(drop=True)
    missing = set(routes).difference(set(point["route"].astype(str)))
    if missing:
        raise RuntimeError(f"Main figure is missing configured routes: {sorted(missing)}")

    y_positions = np.arange(len(point), dtype=float)
    max_upper = 0.0
    row_plot_values: list[dict] = []
    for y_pos, (_, row) in zip(y_positions, point.iterrows()):
        x = float(row[ARRIVAL_TV])
        route = str(row["route"])
        if route == "arrival_bin_anchor":
            low = high = x
            axes[1].plot(
                x,
                y_pos,
                marker="o",
                markerfacecolor="white",
                markeredgecolor="black",
                linestyle="None",
                zorder=3,
            )
        else:
            low = float(row[f"{ARRIVAL_TV}_ci_lower"])
            high = float(row[f"{ARRIVAL_TV}_ci_upper"])
            axes[1].errorbar(
                x,
                y_pos,
                xerr=_asymmetric_error(x, low, high),
                marker="o",
                capsize=2,
                linestyle="None",
                zorder=3,
            )
        max_upper = max(max_upper, high)
        row_plot_values.append({"route": route, "x": x, "y": float(y_pos), "low": low, "high": high})
    x_axis_max = max(1.03, max_upper + 0.18)
    x_padding = 0.025
    x_right_margin = 0.012
    annotation_positions: list[dict] = []
    for item in row_plot_values:
        x_annotation = min(max(0.08, float(item["high"]) + x_padding), x_axis_max - x_right_margin)
        axes[1].annotate(
            f"Top-10 overlap: {float(point.loc[point['route'].astype(str).eq(item['route']), ARRIVAL_OVERLAP].iloc[0]):.2f}",
            (float(item["x"]), float(item["y"])),
            xytext=(x_annotation, float(item["y"])),
            textcoords="data",
            fontsize=6.3,
            ha="left",
            va="center",
        )
        annotation_positions.append(
            {
                "route": str(item["route"]),
                "x_marker": float(item["x"]),
                "x_ci_upper": float(item["high"]),
                "x_annotation": float(x_annotation),
                "x_axis_max": float(x_axis_max),
                "right_margin": float(x_right_margin),
                "padding": float(x_padding),
            }
        )
    axes[1].axvline(0.0, linestyle="--", linewidth=0.8, alpha=0.5)
    axes[1].set_xlabel("Credit-allocation TV distance from arrival-bin anchor")
    axes[1].set_ylabel("")
    axes[1].set_yticks(y_positions, [SHORT_LABELS.get(str(route), str(route)) for route in point["route"]])
    axes[1].invert_yaxis()
    axes[1].set_xlim(left=-0.03, right=x_axis_max)
    axes[1].set_title(panel_titles["panel_b"], loc="left", fontweight="bold", fontsize=panel_title_font_size)
    axes[1].grid(axis="x", alpha=0.20)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96), w_pad=1.35)
    fig.subplots_adjust(top=0.84)

    rows: list[dict] = []
    for _, row in profile.iterrows():
        record = _base_row(cfg, fig_id, "panel_a", "source_event_share_percent", cohort_id)
        record.update(
            {
                "x_id": "delay_bucket",
                "x_value": str(row["delay_bucket"]),
                "x_display_label": BUCKET_LABELS[str(row["delay_bucket"])],
                "y_value": float(row[share_col]),
                "ci_lower": np.nan,
                "ci_upper": np.nan,
                "n_events": int(row[count_col]),
                "n_users": np.nan,
                "filter_id": "all_conversion_candidates",
                "filter_description": "Eligible source-event rows in the decision-cell cohort; delay is conversion time minus source-event time.",
                **_method_fields("arrival_bin_anchor"),
            }
        )
        rows.append(record)
    for _, row in point.iterrows():
        route = str(row["route"])
        record = _base_row(cfg, fig_id, "panel_b", ARRIVAL_TV, cohort_id)
        record.update(
            {
                "x_id": ARRIVAL_TV,
                "x_value": float(row[ARRIVAL_TV]),
                "x_display_label": "allocation TV distance",
                "x_ci_lower": float(row[f"{ARRIVAL_TV}_ci_lower"]),
                "x_ci_upper": float(row[f"{ARRIVAL_TV}_ci_upper"]),
                "y_value": float(row[ARRIVAL_OVERLAP]),
                "ci_lower": float(row[f"{ARRIVAL_OVERLAP}_ci_lower"]),
                "ci_upper": float(row[f"{ARRIVAL_OVERLAP}_ci_upper"]),
                "n_events": int(row["n_eligible_conversion_events"]),
                "n_users": np.nan,
                "filter_id": "all_conversion_candidates",
                "filter_description": "Eligible campaign-source-day decision cells with a constructed arrival-bin diagnostic anchor.",
                "top_k_credited_mass_per_1000_events": float(row["top_k_credited_mass_per_1000_events"]),
                ARRIVAL_MASS_DIFF: float(row[ARRIVAL_MASS_DIFF]),
                **_method_fields(route),
            }
        )
        rows.append(record)
    _write_bundle(
        fig,
        pd.DataFrame(rows),
        cfg,
        fig_id,
        size,
        ["summaries/exp2_route_sensitivity_summary.csv", "summaries/exp2_source_event_delay_profile.csv"],
        f"{ARRIVAL_TV};{ARRIVAL_OVERLAP}",
        "tv_distance_between_normalized_route_credit_allocation_and_arrival_anchor;top10_set_overlap_between_route_and_arrival_anchor",
        {
            "metric_id": ARRIVAL_TV,
            "secondary_annotation": ARRIVAL_OVERLAP,
            "x_id": ARRIVAL_TV,
            "y_id": "method_display_name",
            "layout": "1_row_2_columns",
            "panel_titles": panel_titles,
            "panel_title_font_size": panel_title_font_size,
            "panel_title_overlap_check": "reserved_top_space_with_tight_layout_rect_and_subplots_adjust",
            "panel_b_annotation_positions": annotation_positions,
            "caption_template": (
                "Panel A reports the delay composition within the eligible decision-cell cohort under the 30-day "
                "candidate window, not the full Criteo-log delay distribution. Panel B reports logged "
                "credit-allocation TV distance and Top-10 decision-cell overlap relative to the constructed "
                "arrival-bin anchor."
            ),
            "panel_a_note": (
                "The distribution is computed over eligible source-event rows within the decision-cell cohort "
                "under the 30-day candidate window and is not the full Criteo-log delay distribution."
            ),
            "panel_a_metric_semantics": "source_event_share_percent over eligible source-event rows",
        },
    )


def pairwise_overlap_figure(cfg: dict, frame: pd.DataFrame) -> None:
    _style(cfg)
    fig_id = "fig_app_exp2_source_route_pairwise_overlap"
    cohort_id = str(cfg["subsets"]["main_cohort_id"])
    routes = list(map(str, cfg["reporting"]["core_source_routes"]))
    top_k = int(cfg["action"]["main_top_k"])
    size = (6.85, 2.65)
    fig, axes = plt.subplots(1, 2, figsize=size, squeeze=False)
    axes_flat = axes.ravel()
    data_rows: list[dict] = []
    panels = [
        ("panel_a", "pairwise_credit_allocation_tv_distance", "(a) Pairwise allocation TV distance", 0.0, 1.0),
        ("panel_b", "pairwise_top_k_overlap", "(b) Pairwise top-10 decision-cell overlap", 0.0, 1.0),
    ]
    for index, (panel_id, metric, title, vmin, vmax) in enumerate(panels):
        ax = axes_flat[index]
        current = frame[frame["top_k"].eq(top_k)].copy() if "top_k" in frame.columns else frame.copy()
        matrix = (
            current.pivot(index="route_left", columns="route_right", values=metric)
            .reindex(index=routes, columns=routes)
            .to_numpy(dtype=float)
        )
        if not np.isfinite(matrix).all():
            raise RuntimeError(f"Incomplete pairwise matrix for {metric}.")
        image = ax.imshow(matrix, vmin=vmin, vmax=vmax)
        labels = [SHORT_LABELS.get(route, route) for route in routes]
        ax.set_xticks(range(len(routes)), labels, rotation=45, ha="right")
        ax.set_yticks(range(len(routes)), labels)
        ax.set_title(title)
        for row_index in range(len(routes)):
            for col_index in range(len(routes)):
                ax.text(col_index, row_index, f"{matrix[row_index, col_index]:.2f}", ha="center", va="center", fontsize=5.8)
        for _, row in current.iterrows():
            left = str(row["route_left"])
            right = str(row["route_right"])
            record = _base_row(cfg, fig_id, panel_id, metric, cohort_id)
            record.update(
                {
                    "x_id": "route_right",
                    "x_value": right,
                    "x_display_label": SHORT_LABELS.get(right, right),
                    "y_value": float(row[metric]),
                    "ci_lower": np.nan,
                    "ci_upper": np.nan,
                    "n_events": int(row["n_eligible_conversion_events"]),
                    "n_users": np.nan,
                    "filter_id": "top_k_pairwise_overlap",
                    "filter_description": "Point-estimate source-route differences; not a route performance ranking.",
                    "comparison_method_id": right,
                    "comparison_method_display_name": ROUTE_DISPLAY.get(right, right),
                    "top_k": int(top_k),
                    **_method_fields(left),
                }
            )
            data_rows.append(record)
        cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.set_ylabel("Value", rotation=90)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.28, top=0.86, wspace=0.42)
    _write_bundle(
        fig,
        pd.DataFrame(data_rows),
        cfg,
        fig_id,
        size,
        ["summaries/exp2_source_route_pairwise_overlap.csv"],
        "pairwise_credit_allocation_tv_distance;pairwise_top_k_overlap",
        "pairwise_tv_distance_between_source_route_assignment_distributions;pairwise_top10_decision_cell_set_overlap",
        {"figure_role": "appendix_source_route_mechanism_diagnostic"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Experiment 2 source-time attribution-sensitivity figures.")
    parser.add_argument("--config", default="config_exp2.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    summaries = out_dir(cfg, "summaries")
    main_figure(
        cfg,
        _read(summaries / "exp2_route_sensitivity_summary.csv"),
        _read(summaries / "exp2_source_event_delay_profile.csv"),
    )
    pairwise_overlap_figure(cfg, _read(summaries / "exp2_source_route_pairwise_overlap.csv"))
    save_run_metadata(cfg, "plot_success")
    make_output_manifest(cfg)
    print("[plot] done", flush=True)


if __name__ == "__main__":
    main()
