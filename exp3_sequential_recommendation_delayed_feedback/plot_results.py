from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from figure_contract import retire_figure_bundle, write_figure_bundle
from recoverability import METHOD_META


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _display(method: str) -> str:
    return str(METHOD_META.get(method, {}).get("method_display_name", method))


def _display_short(method: str) -> str:
    """Compact plot labels; full display names remain in tables and metadata."""
    labels = {
        "source_aware_reference": "Reference\n(offline)",
        "arrival_time_naive": "Carrier",
        "source_labelled_empirical": "Source labels",
        "partial_source_label_q50": "Labels 50%",
        "partial_source_label_q30": "Labels 30%",
        "partial_source_label_q10": "Labels 10%",
        "history_mean_static": "History mean",
        "short_term_ridge_proxy": "ST ridge",
        "history_ewma_ridge_proxy": "Hist-EWMA ridge",
        "short_term_composite_surrogate": "ST composite",
    }
    return labels.get(method, _display(method))


def _common_figure_row(figure_id: str, panel_id: str, rec: dict[str, Any], metric_id: str, x_value: Any, y_value: Any, **extra: Any) -> dict[str, Any]:
    meta = METHOD_META.get(str(rec.get("method_id", "")), {})
    return {
        "figure_id": figure_id,
        "panel_id": panel_id,
        "experiment_id": "exp3_long_term_recoverability",
        "subexperiment_id": "kuairand_1k_semi_synthetic",
        "setting_id": rec.get("delay_condition", "not_applicable"),
        "method_id": rec.get("method_id", "not_applicable"),
        "method_display_name": meta.get("method_display_name", rec.get("method_id", "not_applicable")),
        "plot_label": _display_short(str(rec.get("method_id", ""))),
        "information_interface": meta.get("information_interface", "not_applicable"),
        "reference_role": meta.get("reference_role", "none"),
        "diagnostic_only": meta.get("diagnostic_only", False),
        "deployable": meta.get("deployable", False),
        "metric_id": metric_id,
        "metric_formula_id": metric_id,
        "x_id": extra.pop("x_id", "method_id"),
        "x_value": x_value,
        "x_display_label": extra.pop("x_display_label", str(x_value)),
        "y_value": y_value,
        "ci_lower": rec.get("ci_lower", np.nan),
        "ci_upper": rec.get("ci_upper", np.nan),
        "ci_level": rec.get("ci_level", 0.95),
        "uncertainty_unit": rec.get("uncertainty_unit", "user_cluster_bootstrap"),
        "n_seeds": rec.get("n_label_mask_trajectories", np.nan),
        "n_bootstrap": rec.get("n_bootstrap", np.nan),
        "n_events": rec.get("n_events", np.nan),
        "n_users": rec.get("n_users", np.nan),
        "filter_id": extra.pop("filter_id", "history_defined_action_vocabulary__main_support_restricted"),
        "filter_description": extra.pop("filter_description", "valid 6h standard-log source events; fixed history-defined actions; current-bin logged-support restriction"),
        "run_mode": extra.pop("run_mode", "unknown"),
        "paper_result": extra.pop("paper_result", False),
        "notes": extra.pop("notes", ""),
        **extra,
    }


def _static_effect_note(output_dir: Path, cfg: ExperimentConfig) -> tuple[str, dict[str, Any]]:
    effects = _load(output_dir / "summaries" / "paired_effect_vs_history_mean_static.csv")
    hit = effects[(effects.get("delay_condition", pd.Series(dtype=str)) == cfg.primary_delay_condition) & (effects.get("method_id", pd.Series(dtype=str)) == "short_term_ridge_proxy")]
    if hit.empty:
        return "Paired ST-ridge-versus-history-mean contrast is reported in the appendix table.", {}
    rec = hit.iloc[0].to_dict()
    note = (
        "Paired ST ridge − History mean: "
        f"Δ={float(rec['point_estimate']):.4f} "
        f"[{float(rec['ci_lower']):.4f}, {float(rec['ci_upper']):.4f}]; positive favors ST ridge."
    )
    return note, rec


def plot_main_recoverability(output_dir: Path, run_mode: str, paper_result: bool, cfg: ExperimentConfig = DEFAULT_CONFIG, input_data_status: str = "unknown") -> None:
    boot = _load(output_dir / "summaries" / "user_bootstrap_metric_summary.csv")
    calibration = _load(output_dir / "summaries" / "proxy_calibration_summary.csv")
    if boot.empty or calibration.empty:
        raise RuntimeError("Cannot render main Exp3 figure: bootstrap or calibration summaries are missing.")

    condition = cfg.primary_delay_condition
    boot = boot[boot["delay_condition"] == condition].copy()
    calibration = calibration[calibration["delay_condition"] == condition].copy()
    fig, axes = plt.subplots(1, 2, figsize=(6.85, 2.75), gridspec_kw={"width_ratios": [1.0, 1.10]})
    rows: list[dict[str, Any]] = []

    # Panel A: one prespecified proxy route, held out by calendar split.
    ax = axes[0]
    data = calibration[calibration["method_id"] == "short_term_ridge_proxy"].sort_values("decile")
    if data.empty:
        raise RuntimeError("Main calibration route short_term_ridge_proxy missing.")
    x = data["mean_predicted_long_value_log"].to_numpy(float)
    y = data["mean_observed_long_value_log"].to_numpy(float)
    low = data["ci_lower"].to_numpy(float)
    high = data["ci_upper"].to_numpy(float)
    ax.plot(x, y, marker="o", label="ST ridge", linewidth=1.15, markersize=3.5)
    ax.vlines(x, low, high, linewidth=0.8)
    finite = np.concatenate([x, y, low, high])
    finite = finite[np.isfinite(finite)]
    span = float(max(finite.max() - finite.min(), 0.1))
    lower, upper = float(finite.min() - 0.08 * span), float(finite.max() + 0.08 * span)
    ax.plot([lower, upper], [lower, upper], linestyle="--", linewidth=1.0, color="0.35", label="y = x")
    ax.set_xlim(lower, upper)
    ax.set_ylim(lower, upper)
    ax.set_xlabel("Predicted 6h target (log1p)", fontsize=8)
    ax.set_ylabel("Observed 6h target (log1p)", fontsize=8)
    ax.set_title("(a) Held-out calibration", loc="left", fontsize=9)
    ax.legend(fontsize=6.4, frameon=False, loc="upper left")
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.18)
    for rec in data.to_dict("records"):
        rows.append(_common_figure_row(
            "fig_exp3_long_term_recoverability",
            "panel_a",
            rec,
            "held_out_calibration",
            rec["mean_predicted_long_value_log"],
            rec["mean_observed_long_value_log"],
            x_id="mean_predicted_long_value_log",
            x_display_label="Predicted 6h target (log1p)",
            run_mode=run_mode,
            paper_result=paper_result,
            notes="ST ridge is fit on history-standard only and evaluated on main-standard. Points are prediction deciles; vertical bars are 95% user-bootstrap CIs.",
        ))

    # Panel B: daily decision-level metric with static-history control visible.
    ax = axes[1]
    baseline = boot[boot["method_id"] == "arrival_time_naive"]
    base_value = float(baseline["point_estimate"].iloc[0]) if not baseline.empty else np.nan
    if np.isfinite(base_value):
        ax.axvline(base_value, linestyle="--", linewidth=1.0, color="0.35", label="Carrier baseline")
    method_order = cfg.main_methods
    y_positions = np.arange(len(method_order))
    by_method = boot.set_index("method_id")
    for y_pos, method in zip(y_positions, method_order):
        if method not in by_method.index:
            continue
        rec = by_method.loc[method]
        point = float(rec["point_estimate"])
        low = float(rec["ci_lower"])
        high = float(rec["ci_upper"])
        style = {"marker": "o", "markersize": 3.8, "linewidth": 1.1, "capsize": 2.0}
        if method == "source_aware_reference":
            style.update({"markerfacecolor": "none", "color": "0.4"})
        ax.errorbar(point, y_pos, xerr=[[max(0.0, point - low)], [max(0.0, high - point)]], **style)
        rows.append(_common_figure_row(
            "fig_exp3_long_term_recoverability",
            "panel_b",
            rec.to_dict(),
            "ranking_regret_per_time_bin",
            method,
            point,
            x_id="method_id",
            x_display_label=_display_short(method),
            run_mode=run_mode,
            paper_result=paper_result,
            notes="Lower is better. Points are estimates; horizontal bars are 95% user-bootstrap CIs. Dashed line marks Carrier; Reference is offline only.",
        ))
    ax.set_yticks(y_positions, [_display_short(method) for method in method_order], fontsize=6.6)
    ax.invert_yaxis()
    ax.set_xlabel("6h target ranking regret (lower is better)", fontsize=8)
    ax.set_title("(b) Daily ranking regret", loc="left", fontsize=9)
    ax.tick_params(labelsize=7)
    ax.grid(axis="x", alpha=0.18)
    if np.isfinite(base_value):
        ax.legend(fontsize=6.2, frameon=False, loc="lower right")

    static_note, static_effect = _static_effect_note(output_dir, cfg)
    fig.text(
        0.012,
        0.012,
        "(a) Points = prediction deciles; vertical bars = 95% user-bootstrap CI. "
        "(b) Points = estimates; horizontal bars = 95% user-bootstrap CI; dashed line = Carrier. "
        + static_note,
        ha="left",
        va="bottom",
        fontsize=5.8,
    )
    fig.subplots_adjust(left=0.13, right=0.985, bottom=0.32, top=0.88, wspace=0.52)
    write_figure_bundle(fig, rows, output_dir, "fig_exp3_long_term_recoverability", {
        "metric_id": "ranking_regret_per_time_bin",
        "primary_horizon": "6h",
        "primary_outcome_id": "long_value_log",
        "uncertainty_unit": "user_cluster_resampling_of_empirical_update_routes_with_finite_event_level_label_mask_bank_and_fixed_history_fitted_proxy_scores",
        "interpretation_boundary": "Offline logged-support diagnostic over a history-defined category vocabulary and main-period support-restricted action cells. It is not OPE or online causal policy evaluation.",
        "training_evaluation_split": "History-standard fits ridge proxies and action vocabulary; main-standard supplies held-out scores and target evaluation.",
        "arrival_time_baseline_value": base_value,
        "paired_static_control_effect": static_effect,
        "caption_note": static_note,
        "plot_label_map_version": "v5_2_explanatory",
    }, run_mode, paper_result, input_data_status=input_data_status)


def plot_horizon_eligibility(output_dir: Path, run_mode: str, paper_result: bool, input_data_status: str = "unknown") -> None:
    table = _load(output_dir / "summaries" / "main_standard_horizon_target_summary.csv")
    if table.empty:
        return
    order = {"1h": 1, "6h": 2, "1d": 3, "3d": 4}
    table = table.assign(_order=table["horizon"].map(order)).sort_values("_order")
    positions = np.arange(len(table))
    rates = 100.0 * table["right_censoring_rate"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(6.85, 2.25))
    ax.plot(positions, rates, marker="o", linewidth=1.15, label="Right censoring")
    for position, rate in zip(positions, rates):
        ax.annotate(f"{rate:.1f}%", (position, rate), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=6.5)
    six_h = np.flatnonzero(table["horizon"].astype(str).to_numpy() == "6h")
    if len(six_h):
        ax.axvline(int(six_h[0]), linestyle="--", linewidth=0.9, color="0.35", label="Primary horizon: 6h")
    ax.set_xticks(positions, table["horizon"].astype(str).tolist())
    ax.set_xlabel("Future-engagement horizon", fontsize=8)
    ax.set_ylabel("Right-censoring rate (%)", fontsize=8)
    ax.set_title("Horizon eligibility", loc="left", fontsize=9)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.18)
    ax.legend(fontsize=6.4, frameon=False, loc="upper left")
    fig.text(
        0.012,
        0.012,
        "Eligible source events remain observed through the full target window. The 6h horizon is prespecified; this figure reports availability only.",
        ha="left",
        va="bottom",
        fontsize=6.0,
    )
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.28, top=0.87)
    rows = []
    for rec in table.to_dict("records"):
        row = dict(rec)
        row["method_id"] = "not_applicable"
        row["ci_level"] = np.nan
        row["n_bootstrap"] = np.nan
        rows.append(_common_figure_row(
            "fig_app_exp3_horizon_eligibility",
            "panel_a",
            row,
            "right_censoring_rate_percent",
            rec["horizon"],
            100.0 * float(rec["right_censoring_rate"]),
            x_id="horizon",
            x_display_label=str(rec["horizon"]),
            run_mode=run_mode,
            paper_result=paper_result,
            notes="Right-censoring rate is one minus the share of source events valid for the stated future window. 6h is prespecified.",
            n_valid_source_events=int(rec["n_valid_source_events"]),
            n_source_events=int(rec["n_source_events"]),
        ))
    write_figure_bundle(fig, rows, output_dir, "fig_app_exp3_horizon_eligibility", {
        "figure_role": "appendix eligibility diagnostic",
        "primary_horizon": "6h",
        "metric_id": "right_censoring_rate_percent",
        "eligibility_definition": "A source event is eligible when its user remains observed in the same standard-log split through the entire future target horizon.",
        "interpretation_boundary": "This figure does not establish target saturation or choose the horizon post hoc; it reports right-censoring availability for prespecified diagnostic horizons.",
        "plot_label_map_version": "v5_2_explanatory",
    }, run_mode, paper_result, input_data_status=input_data_status)


def plot_all(output_dir: Path, run_mode: str, paper_result: bool, cfg: ExperimentConfig = DEFAULT_CONFIG, input_data_status: str = "unknown") -> None:
    # Retire obsolete active figure interfaces. The underlying CSV audits remain
    # available in summaries/tables and are never discarded.
    for figure_id in [
        "fig_app_exp3_arrival_mechanism_contrast",
        "fig_app_exp3_source_label_coverage",
        "fig_app_exp3_horizon_saturation",
    ]:
        retire_figure_bundle(output_dir, figure_id, reason="v5_2_retired_interface")
    plot_main_recoverability(output_dir, run_mode, paper_result, cfg, input_data_status)
    plot_horizon_eligibility(output_dir, run_mode, paper_result, input_data_status)
