"""Appendix-table builders for Exp3 evidence-boundary diagnostics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from recoverability import METHOD_META


PLOT_LABELS = {
    "arrival_time_naive": "Carrier",
    "source_labelled_empirical": "Source labels",
    "partial_source_label_q10": "Labels 10%",
    "partial_source_label_q30": "Labels 30%",
    "partial_source_label_q50": "Labels 50%",
    "history_mean_static": "History mean",
    "short_term_ridge_proxy": "ST ridge",
    "history_ewma_ridge_proxy": "Hist-EWMA ridge",
    "short_term_composite_surrogate": "ST composite",
    "source_aware_reference": "Reference (offline)",
}


def _metric_row(summary: pd.DataFrame, condition: str, method: str) -> pd.Series | None:
    hit = summary[(summary["delay_condition"] == condition) & (summary["method_id"] == method)]
    return None if hit.empty else hit.iloc[0]


def _effect_row(effects: pd.DataFrame, condition: str, method: str) -> pd.Series | None:
    hit = effects[(effects["delay_condition"] == condition) & (effects["method_id"] == method)]
    return None if hit.empty else hit.iloc[0]


def build_partial_label_sensitivity_table(
    metric_summary: pd.DataFrame,
    arrival_summary: pd.DataFrame,
    arrival_effects: pd.DataFrame,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Report partial-label sensitivity without implying monotonicity or sparsity."""
    route_map = [
        (0.00, "arrival_time_naive", "carrier_endpoint"),
        (0.10, "partial_source_label_q10", "partial_label_route"),
        (0.30, "partial_source_label_q30", "partial_label_route"),
        (0.50, "partial_source_label_q50", "partial_label_route"),
        (1.00, "source_labelled_empirical", "source_label_endpoint"),
    ]
    rows: list[dict[str, object]] = []
    for condition in cfg.delay_conditions:
        arrival = arrival_summary[arrival_summary["delay_condition"] == condition]
        n_valid = int(arrival["n_arrival_messages"].iloc[0]) if not arrival.empty else 0
        for q, method, route_role in route_map:
            metric = _metric_row(metric_summary, condition, method)
            if metric is None:
                continue
            effect = _effect_row(arrival_effects, condition, method)
            meta = METHOD_META.get(method, {})
            if method == "arrival_time_naive":
                reduction, effect_lo, effect_hi = 0.0, 0.0, 0.0
            elif effect is None:
                reduction, effect_lo, effect_hi = np.nan, np.nan, np.nan
            else:
                reduction = float(effect["point_estimate"])
                effect_lo = float(effect["ci_lower"])
                effect_hi = float(effect["ci_upper"])
            rows.append({
                "experiment_id": "exp3_long_term_recoverability",
                "delay_condition": condition,
                "source_label_rate_q": q,
                "method_id": method,
                "method_display_name": meta.get("method_display_name", method),
                "plot_label": PLOT_LABELS.get(method, method),
                "route_role": route_role,
                "n_valid_source_outcomes": n_valid,
                "expected_source_labelled_outcomes": int(round(q * n_valid)),
                "expected_source_labelled_share": q,
                "ranking_regret_per_time_bin": float(metric["point_estimate"]),
                "ranking_regret_ci_lower": float(metric["ci_lower"]),
                "ranking_regret_ci_upper": float(metric["ci_upper"]),
                "regret_reduction_vs_carrier": reduction,
                "reduction_ci_lower": effect_lo,
                "reduction_ci_upper": effect_hi,
                "ci_level": float(metric["ci_level"]),
                "n_bootstrap": int(metric["n_bootstrap"]),
                "interpretation_note": (
                    "Positive reduction means lower regret than Carrier. This is a high-volume sensitivity table; "
                    "it makes no monotonicity or sparse-label-sufficiency claim."
                ),
            })
    return pd.DataFrame(rows)


def build_proxy_static_control_table(
    metric_summary: pd.DataFrame,
    static_effects: pd.DataFrame,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Compare fixed proxy routes with the history-only static control."""
    methods = [
        "history_mean_static",
        "short_term_ridge_proxy",
        "history_ewma_ridge_proxy",
        "short_term_composite_surrogate",
    ]
    condition = cfg.primary_delay_condition
    rows: list[dict[str, object]] = []
    for method in methods:
        metric = _metric_row(metric_summary, condition, method)
        if metric is None:
            continue
        meta = METHOD_META.get(method, {})
        effect = _effect_row(static_effects, condition, method)
        if method == "history_mean_static":
            delta, lo, hi = 0.0, 0.0, 0.0
        elif effect is None:
            delta, lo, hi = np.nan, np.nan, np.nan
        else:
            delta, lo, hi = float(effect["point_estimate"]), float(effect["ci_lower"]), float(effect["ci_upper"])
        rows.append({
            "experiment_id": "exp3_long_term_recoverability",
            "delay_condition": condition,
            "method_id": method,
            "method_display_name": meta.get("method_display_name", method),
            "plot_label": PLOT_LABELS.get(method, method),
            "comparator_method_id": "history_mean_static",
            "ranking_regret_per_time_bin": float(metric["point_estimate"]),
            "ranking_regret_ci_lower": float(metric["ci_lower"]),
            "ranking_regret_ci_upper": float(metric["ci_upper"]),
            "paired_regret_reduction_vs_history_mean": delta,
            "paired_reduction_ci_lower": lo,
            "paired_reduction_ci_upper": hi,
            "ci_level": float(metric["ci_level"]),
            "n_bootstrap": int(metric["n_bootstrap"]),
            "interpretation_note": (
                "Positive paired reduction favors the named route over the history-only static control. "
                "A confidence interval spanning zero does not establish incremental dynamic proxy value."
            ),
        })
    return pd.DataFrame(rows)
