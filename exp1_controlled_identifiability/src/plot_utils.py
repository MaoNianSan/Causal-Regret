from __future__ import annotations

"""Traceable, regime-consistent figure bundles for EXP1.

Primary figures compare methods only when they share an information interface.
The manuscript-facing source-binding figure therefore uses the labelled regime,
where Arrival time, Delayed EXP3, Source labelled, and the oracle reference are
all evaluated under the same visible source-label information.  Partial-label,
unlabelled attribution, proxy, and mechanism diagnostics are separate figures.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CI_LEVEL, N_BOOTSTRAP
from src.experiment_contract import (
    INPUT_DATA_STATUS,
    PRIMARY_METRIC,
    PRIMARY_METRIC_FORMULA,
)

PAPER_FIGURE_WIDTH_IN = 6.85
PAPER_DPI = 600

METHOD_LABELS = {
    "oracle": "Context oracle reference",
    "naive": "Arrival time",
    "naive_ewma": "Arrival time with EWMA",
    "delayed_ucb": "Delayed UCB",
    "delayed_exp3": "Delayed EXP3",
    "sliding_window_W250": "Arrival time sliding window",
    "anonymous_delayed": "Anonymous delayed",
    "causal_labeled": "Source labelled",
    "causal_em": "Soft attribution EM",
    "causal_em_misspecified": "Stationary geometric EM ablation",
    "proxy": "Filtered state proxy",
}

SETTING_LABELS = {
    "zero_static": "Zero",
    "aligned_static_delay_15": "Aligned static 15",
    "geometric_matched_15": "Geometric",
    "mixture_matched_15": "Mixture",
    "state_structural_matched_15": "State structural",
    "proxy_good_matched_15": "Good proxy",
    "proxy_bad_matched_15": "Bad proxy",
    "action_structural_stress": "Action structural stress",
}

CORE_SETTINGS = [
    "zero_static",
    "aligned_static_delay_15",
    "geometric_matched_15",
    "mixture_matched_15",
    "state_structural_matched_15",
]
MATCHED_SETTINGS = [
    "geometric_matched_15",
    "mixture_matched_15",
    "state_structural_matched_15",
]
CORE_LABELLED_METHODS = ["oracle", "naive", "delayed_exp3", "causal_labeled"]
FIGURE_DATA_COLUMNS = [
    "figure_id",
    "panel_id",
    "experiment_id",
    "subexperiment_id",
    "setting_id",
    "method_id",
    "method_display_name",
    "information_interface",
    "reference_role",
    "diagnostic_only",
    "deployable",
    "metric_id",
    "metric_formula_id",
    "x_id",
    "x_value",
    "x_display_label",
    "y_value",
    "ci_lower",
    "ci_upper",
    "ci_level",
    "uncertainty_unit",
    "n_seeds",
    "n_bootstrap",
    "n_events",
    "n_users",
    "filter_id",
    "filter_description",
    "run_mode",
    "paper_result",
    "notes",
]


def _stable_int(*parts: object) -> int:
    text = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "little") % (2**31 - 1)


def _bootstrap(
    values: Iterable[float], key: tuple[object, ...]
) -> tuple[int, float, float, float]:
    vals = np.asarray(list(values), dtype=float)
    vals = vals[np.isfinite(vals)]
    n = int(vals.size)
    if n == 0:
        return 0, float("nan"), float("nan"), float("nan")
    mean = float(vals.mean())
    if n == 1:
        return n, mean, mean, mean
    rng = np.random.default_rng(_stable_int("figure_bootstrap", *key, N_BOOTSTRAP))
    draws = vals[rng.integers(0, n, size=(N_BOOTSTRAP, n))].mean(axis=1)
    alpha = (1.0 - CI_LEVEL) / 2.0
    low, high = np.quantile(draws, [alpha, 1.0 - alpha])
    return n, mean, float(low), float(high)


def _safe_columns(seed: pd.DataFrame) -> None:
    required = {
        "experiment_id",
        "subexperiment_id",
        "setting_id",
        "delay_setting",
        "method",
        "method_id",
        "method_display_name",
        "information_interface",
        "reference_role",
        "diagnostic_only",
        "deployable",
        "regime",
        "final_Rc",
        "T",
        "run_mode",
        "paper_result",
        "input_data_status",
    }
    missing = sorted(required.difference(seed.columns))
    if missing:
        raise ValueError(f"EXP1 figure generation requires missing columns: {missing}")


def _regret(frame: pd.DataFrame) -> pd.Series:
    value = pd.to_numeric(frame["final_Rc"], errors="coerce") / pd.to_numeric(
        frame["T"], errors="coerce"
    )
    return value.replace([np.inf, -np.inf], np.nan)


def _record_from_group(
    group: pd.DataFrame,
    *,
    figure_id: str,
    panel_id: str,
    metric_id: str,
    metric_formula_id: str,
    x_id: str,
    x_value: float | str,
    x_display_label: str,
    values: Iterable[float],
    filter_id: str,
    filter_description: str,
    notes: str = "",
) -> dict[str, object]:
    n, mean, low, high = _bootstrap(
        values,
        (
            figure_id,
            panel_id,
            metric_id,
            x_value,
            group["method"].iloc[0],
            group["regime"].iloc[0],
        ),
    )
    first = group.iloc[0]
    return {
        "figure_id": figure_id,
        "panel_id": panel_id,
        "experiment_id": first["experiment_id"],
        "subexperiment_id": first["subexperiment_id"],
        "setting_id": first["setting_id"],
        "method_id": first["method_id"],
        "method_display_name": first["method_display_name"],
        "information_interface": first["information_interface"],
        "reference_role": first["reference_role"],
        "diagnostic_only": bool(first["diagnostic_only"]),
        "deployable": bool(first["deployable"]),
        "metric_id": metric_id,
        "metric_formula_id": metric_formula_id,
        "x_id": x_id,
        "x_value": x_value,
        "x_display_label": x_display_label,
        "y_value": mean,
        "ci_lower": low,
        "ci_upper": high,
        "ci_level": CI_LEVEL,
        "uncertainty_unit": "shared_simulation_seed",
        "n_seeds": n,
        "n_bootstrap": N_BOOTSTRAP,
        "n_events": (
            int(
                pd.to_numeric(group.get("n_observed_arrivals", 0), errors="coerce")
                .fillna(0)
                .sum()
            )
            if "n_observed_arrivals" in group
            else 0
        ),
        "n_users": 0,
        "filter_id": filter_id,
        "filter_description": filter_description,
        "run_mode": first["run_mode"],
        "paper_result": bool(first["paper_result"]),
        "notes": notes,
    }


def _write_bundle(
    root: Path,
    figure_id: str,
    data: pd.DataFrame,
    fig: plt.Figure,
    *,
    description: str,
    metric_id: str,
    figure_size_in: tuple[float, float],
    figure_status: str = "registered",
) -> None:
    root = Path(root)
    for rel in ("figures/data", "figures/metadata", "figures/pdf", "figures/png"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for col in FIGURE_DATA_COLUMNS:
        if col not in data.columns:
            data[col] = np.nan
    data = data.loc[:, FIGURE_DATA_COLUMNS]
    data_path = root / "figures" / "data" / f"{figure_id}_data.csv"
    data.to_csv(data_path, index=False)
    fig.savefig(root / "figures" / "pdf" / f"{figure_id}.pdf", bbox_inches="tight")
    fig.savefig(
        root / "figures" / "png" / f"{figure_id}.png",
        dpi=PAPER_DPI,
        bbox_inches="tight",
    )
    plt.close(fig)
    payload = {
        "figure_id": figure_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "data_csv": str(data_path.relative_to(root)),
        "figure_size_in": list(figure_size_in),
        "dpi": PAPER_DPI,
        "metric_id": metric_id,
        "metric_formula_id": (
            PRIMARY_METRIC_FORMULA if metric_id == PRIMARY_METRIC else metric_id
        ),
        "uncertainty_unit": "shared_simulation_seed",
        "ci_level": CI_LEVEL,
        "n_bootstrap": N_BOOTSTRAP,
        "input_data_status": INPUT_DATA_STATUS,
        "paper_result": (
            bool(data["paper_result"].fillna(False).astype(bool).all())
            if len(data)
            else False
        ),
        "figure_status": figure_status,
        "comparison_rule": "Methods are compared only within the same information regime and declared interface.",
    }
    (root / "figures" / "metadata" / f"{figure_id}_metadata.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _point_range(
    ax: plt.Axes,
    data: pd.DataFrame,
    settings: list[str],
    methods: list[str],
    *,
    ylabel: str,
) -> None:
    x = np.arange(len(settings), dtype=float)
    width = 0.70 / max(1, len(methods))
    for index, method in enumerate(methods):
        sub = (
            data[data["method_id"].eq(method)].set_index("setting_id").reindex(settings)
        )
        if sub.empty:
            continue
        offset = (index - (len(methods) - 1) / 2.0) * width
        y = pd.to_numeric(sub["y_value"], errors="coerce").to_numpy(float)
        low = pd.to_numeric(sub["ci_lower"], errors="coerce").to_numpy(float)
        high = pd.to_numeric(sub["ci_upper"], errors="coerce").to_numpy(float)
        yerr = np.vstack([np.maximum(0.0, y - low), np.maximum(0.0, high - y)])
        line_style = (
            "--"
            if (sub["reference_role"].astype(str) == "oracle_reference").all()
            else "none"
        )
        ax.errorbar(
            x + offset,
            y,
            yerr=yerr,
            fmt="o",
            capsize=2.5,
            linestyle=line_style,
            label=sub["method_display_name"].iloc[0],
        )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [SETTING_LABELS.get(setting, setting) for setting in settings],
        rotation=20,
        ha="right",
    )
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(fontsize=6.5, loc="best")


def _core_labelled_data(
    seed: pd.DataFrame, figure_id: str, panel_id: str, settings: list[str]
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    subset = seed[
        (seed["regime"].eq("labelled"))
        & (seed["delay_setting"].isin(settings))
        & (seed["method"].isin(CORE_LABELLED_METHODS))
    ].copy()
    subset["regret_per_round"] = _regret(subset)
    for (setting, method), group in subset.groupby(
        ["delay_setting", "method"], sort=False
    ):
        rows.append(
            _record_from_group(
                group,
                figure_id=figure_id,
                panel_id=panel_id,
                metric_id=PRIMARY_METRIC,
                metric_formula_id=PRIMARY_METRIC_FORMULA,
                x_id="delay_setting",
                x_value=float(settings.index(setting)),
                x_display_label=SETTING_LABELS.get(setting, setting),
                values=group["regret_per_round"],
                filter_id="labelled_core_methods",
                filter_description="Full source-label regime; no cross-regime method comparison.",
            )
        )
    return pd.DataFrame(rows)


def _plot_validity_boundary(seed: pd.DataFrame, root: Path) -> None:
    panel_a = _core_labelled_data(
        seed, "fig_exp1_validity_boundary", "panel_a", CORE_SETTINGS
    )
    panel_b = _core_labelled_data(
        seed, "fig_exp1_validity_boundary", "panel_b", MATCHED_SETTINGS
    )
    data = pd.concat([panel_a, panel_b], ignore_index=True)
    fig, axes = plt.subplots(1, 2, figsize=(PAPER_FIGURE_WIDTH_IN, 2.70), sharey=True)
    _point_range(
        axes[0],
        panel_a,
        CORE_SETTINGS,
        ["oracle_reference", "arrival_time_naive", "delayed_exp3", "source_labelled"],
        ylabel="Causal regret per round",
    )
    axes[0].set_title("(a) Validity boundary", fontsize=9)
    _point_range(
        axes[1],
        panel_b,
        MATCHED_SETTINGS,
        ["oracle_reference", "arrival_time_naive", "delayed_exp3", "source_labelled"],
        ylabel="",
    )
    axes[1].set_title("(b) Matched observed mean delay", fontsize=9)
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_exp1_validity_boundary",
        data,
        fig,
        description="Primary controlled source-binding validity figure. Both panels use only the labelled regime.",
        metric_id=PRIMARY_METRIC,
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 2.70),
    )


def _plot_same_mean_delay(seed: pd.DataFrame, root: Path) -> None:
    rows: list[dict[str, object]] = []
    subset = seed[
        (seed["regime"].eq("labelled"))
        & (seed["delay_setting"].isin(MATCHED_SETTINGS))
        & (seed["method"].isin(CORE_LABELLED_METHODS))
    ].copy()
    subset["regret_per_round"] = _regret(subset)
    for (setting, method), group in subset.groupby(
        ["delay_setting", "method"], sort=False
    ):
        record = _record_from_group(
            group,
            figure_id="fig_exp1_same_mean_delay",
            panel_id="panel_a",
            metric_id=PRIMARY_METRIC,
            metric_formula_id=PRIMARY_METRIC_FORMULA,
            x_id="realised_observed_mean_delay",
            x_value=float(pd.to_numeric(group["mean_delay"], errors="coerce").mean()),
            x_display_label=SETTING_LABELS.get(setting, setting),
            values=group["regret_per_round"],
            filter_id="labelled_matched_delay",
            filter_description="Full source-label regime; matched-delay audit.",
        )
        record["setting_id"] = setting
        rows.append(record)
    data = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(PAPER_FIGURE_WIDTH_IN, 2.70))
    for method_id, sub in data.groupby("method_id", sort=False):
        y = pd.to_numeric(sub["y_value"], errors="coerce").to_numpy(float)
        low = pd.to_numeric(sub["ci_lower"], errors="coerce").to_numpy(float)
        high = pd.to_numeric(sub["ci_upper"], errors="coerce").to_numpy(float)
        x = pd.to_numeric(sub["x_value"], errors="coerce").to_numpy(float)
        ax.errorbar(
            x,
            y,
            yerr=np.vstack([y - low, high - y]),
            fmt="o",
            capsize=2.5,
            label=sub["method_display_name"].iloc[0],
        )
        for _, row in sub.iterrows():
            ax.annotate(
                str(row["x_display_label"]),
                (float(row["x_value"]), float(row["y_value"])),
                fontsize=6.5,
                xytext=(3, 2),
                textcoords="offset points",
            )
    ax.axvline(15.0, linewidth=0.8, linestyle="--")
    ax.set_xlabel("Realised observed mean delay")
    ax.set_ylabel("Causal regret per round")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=6.5, loc="best")
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_exp1_same_mean_delay",
        data,
        fig,
        description="Matched observed-delay audit in the labelled regime.",
        metric_id=PRIMARY_METRIC,
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 2.70),
        figure_status="appendix_diagnostic",
    )


def _posterior_diagnostic_data(seed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    subset = seed[
        (seed["regime"].isin(["mixture_labelled", "unlabelled"]))
        & (seed["method"].isin(["causal_em", "causal_em_misspecified", "proxy"]))
    ].copy()
    for metric in ("soft_attribution_true_mass", "soft_attribution_top1_accuracy"):
        for (regime, setting, method), group in subset.groupby(
            ["regime", "delay_setting", "method"], sort=False
        ):
            rows.append(
                _record_from_group(
                    group,
                    figure_id="fig_exp1_attribution_diagnostics",
                    panel_id=f"{regime}_{metric}",
                    metric_id=metric,
                    metric_formula_id=metric,
                    x_id="delay_setting",
                    x_value=float(list(SETTING_LABELS).index(setting)),
                    x_display_label=SETTING_LABELS.get(setting, setting),
                    values=pd.to_numeric(group[metric], errors="coerce"),
                    filter_id=f"{regime}_posterior_diagnostics",
                    filter_description="Posterior attribution diagnostics; methods remain within the same information regime.",
                )
            )
    return pd.DataFrame(rows)


def _plot_attribution_diagnostics(seed: pd.DataFrame, root: Path) -> None:
    data = _posterior_diagnostic_data(seed)
    metrics = ["soft_attribution_true_mass", "soft_attribution_top1_accuracy"]
    regimes = ["mixture_labelled", "unlabelled"]
    fig, axes = plt.subplots(2, 2, figsize=(PAPER_FIGURE_WIDTH_IN, 5.3), sharey="col")
    for r, regime in enumerate(regimes):
        for c, metric in enumerate(metrics):
            ax = axes[r, c]
            sub = data[(data["panel_id"].eq(f"{regime}_{metric}"))].copy()
            if sub.empty:
                ax.axis("off")
                continue
            settings = [
                setting
                for setting in SETTING_LABELS
                if setting in set(sub["setting_id"])
            ]
            for method_id, method_rows in sub.groupby("method_id", sort=False):
                indexed = method_rows.set_index("setting_id").reindex(settings)
                y = pd.to_numeric(indexed["y_value"], errors="coerce").to_numpy(float)
                low = pd.to_numeric(indexed["ci_lower"], errors="coerce").to_numpy(
                    float
                )
                high = pd.to_numeric(indexed["ci_upper"], errors="coerce").to_numpy(
                    float
                )
                ax.errorbar(
                    np.arange(len(settings)),
                    y,
                    yerr=np.vstack([np.maximum(0, y - low), np.maximum(0, high - y)]),
                    fmt="o-",
                    capsize=2,
                    label=indexed["method_display_name"].dropna().iloc[0],
                )
            ax.set_xticks(np.arange(len(settings)))
            ax.set_xticklabels(
                [SETTING_LABELS[x] for x in settings],
                rotation=25,
                ha="right",
                fontsize=6.5,
            )
            ax.set_ylim(-0.02, 1.02)
            ax.set_title(f"{regime}: {metric.replace('_', ' ')}", fontsize=8)
            ax.grid(alpha=0.2)
            ax.legend(fontsize=5.8, loc="best")
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_exp1_attribution_diagnostics",
        data,
        fig,
        description="Posterior attribution diagnostics, stratified by information regime.",
        metric_id="posterior_attribution_diagnostic",
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 5.30),
        figure_status="appendix_diagnostic",
    )


def _plot_proxy_quality(seed: pd.DataFrame, root: Path) -> None:
    subset = seed[
        (seed["method"].eq("proxy"))
        & (seed["regime"].eq("unlabelled"))
        & (
            seed["delay_setting"].isin(
                ["proxy_good_matched_15", "proxy_bad_matched_15"]
            )
        )
    ].copy()
    subset["regret_per_round"] = _regret(subset)
    rows: list[dict[str, object]] = []
    for setting, group in subset.groupby("delay_setting", sort=False):
        rec = _record_from_group(
            group,
            figure_id="fig_exp1_proxy_quality",
            panel_id="panel_a",
            metric_id=PRIMARY_METRIC,
            metric_formula_id=PRIMARY_METRIC_FORMULA,
            x_id="proxy_state_error_per_round",
            x_value=float(
                pd.to_numeric(group["proxy_state_error_mean"], errors="coerce").mean()
            ),
            x_display_label=SETTING_LABELS.get(setting, setting),
            values=group["regret_per_round"],
            filter_id="unlabelled_proxy_quality",
            filter_description="Same state/context/delay path; only proxy observation noise differs.",
        )
        rec["setting_id"] = setting
        rows.append(rec)
    data = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(PAPER_FIGURE_WIDTH_IN, 2.70))
    x = pd.to_numeric(data["x_value"], errors="coerce").to_numpy(float)
    y = pd.to_numeric(data["y_value"], errors="coerce").to_numpy(float)
    low = pd.to_numeric(data["ci_lower"], errors="coerce").to_numpy(float)
    high = pd.to_numeric(data["ci_upper"], errors="coerce").to_numpy(float)
    ax.errorbar(x, y, yerr=np.vstack([y - low, high - y]), fmt="o", capsize=3)
    for _, row in data.iterrows():
        ax.annotate(
            str(row["x_display_label"]),
            (float(row["x_value"]), float(row["y_value"])),
            fontsize=7,
            xytext=(3, 2),
            textcoords="offset points",
        )
    ax.set_xlabel(r"Time-averaged $|\hat{S}_t-S_t|$")
    ax.set_ylabel("Causal regret per round")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_exp1_proxy_quality",
        data,
        fig,
        description="Unlabelled proxy-quality sweep under a matched path.",
        metric_id=PRIMARY_METRIC,
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 2.70),
        figure_status="appendix_diagnostic",
    )


def _plot_mismatch_diagnostics(seed: pd.DataFrame, root: Path) -> None:
    subset = seed[
        (seed["regime"].eq("labelled"))
        & (seed["method"].eq("naive"))
        & (seed["delay_setting"].isin(CORE_SETTINGS))
    ].copy()
    rows: list[dict[str, object]] = []
    for setting, group in subset.groupby("delay_setting", sort=False):
        for metric, panel in (
            ("abs_delta_attr_event_per_arrival", "panel_a"),
            ("loss_map_mismatch_rate", "panel_b"),
        ):
            rows.append(
                _record_from_group(
                    group,
                    figure_id="fig_app_exp1_mismatch_diagnostics",
                    panel_id=panel,
                    metric_id=metric,
                    metric_formula_id=metric,
                    x_id="delay_setting",
                    x_value=float(CORE_SETTINGS.index(setting)),
                    x_display_label=SETTING_LABELS[setting],
                    values=pd.to_numeric(group[metric], errors="coerce"),
                    filter_id="labelled_arrival_time_diagnostic",
                    filter_description="Arrival-time diagnostic under full source labels.",
                    notes="Diagnostic only; not a deployable-method ranking.",
                )
            )
    data = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(PAPER_FIGURE_WIDTH_IN, 2.55))
    for ax, panel, ylabel in zip(
        axes,
        ["panel_a", "panel_b"],
        ["Absolute attribution distortion per arrival", "Loss-map mismatch rate"],
    ):
        sub = data[data["panel_id"].eq(panel)].sort_values("x_value")
        x = pd.to_numeric(sub["x_value"], errors="coerce").to_numpy(float)
        y = pd.to_numeric(sub["y_value"], errors="coerce").to_numpy(float)
        low = pd.to_numeric(sub["ci_lower"], errors="coerce").to_numpy(float)
        high = pd.to_numeric(sub["ci_upper"], errors="coerce").to_numpy(float)
        ax.errorbar(
            x,
            y,
            yerr=np.vstack([np.maximum(0, y - low), np.maximum(0, high - y)]),
            fmt="o",
            capsize=2.5,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(
            sub["x_display_label"], rotation=20, ha="right", fontsize=6.5
        )
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.2)
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_app_exp1_mismatch_diagnostics",
        data,
        fig,
        description="Mechanism diagnostics for the arrival-time route in the labelled regime.",
        metric_id="source_binding_mismatch_diagnostic",
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 2.55),
        figure_status="appendix",
    )


def _plot_selected_trajectories(seed: pd.DataFrame, root: Path) -> None:
    path = Path(root) / "processed" / "selected_trajectory_points.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing selected trajectory data: {path}")
    trace = pd.read_csv(path)
    rows: list[dict[str, object]] = []
    for (setting, method, t), group in trace.groupby(
        ["delay_setting", "method", "t"], sort=False
    ):
        match = seed[
            (seed["delay_setting"].eq(setting))
            & (seed["regime"].eq("labelled"))
            & (seed["method"].eq(method))
        ]
        if match.empty:
            continue
        first = match.iloc[0]
        n, mean, low, high = _bootstrap(
            group["cumulative_contextual_regret"],
            ("trajectory", setting, method, int(t)),
        )
        rows.append(
            {
                "figure_id": "fig_app_exp1_selected_trajectories",
                "panel_id": setting,
                "experiment_id": first["experiment_id"],
                "subexperiment_id": first["subexperiment_id"],
                "setting_id": setting,
                "method_id": first["method_id"],
                "method_display_name": first["method_display_name"],
                "information_interface": first["information_interface"],
                "reference_role": first["reference_role"],
                "diagnostic_only": bool(first["diagnostic_only"]),
                "deployable": bool(first["deployable"]),
                "metric_id": "cumulative_causal_regret",
                "metric_formula_id": "R_t^c",
                "x_id": "time_step",
                "x_value": int(t),
                "x_display_label": str(t),
                "y_value": mean,
                "ci_lower": low,
                "ci_upper": high,
                "ci_level": CI_LEVEL,
                "uncertainty_unit": "shared_simulation_seed",
                "n_seeds": n,
                "n_bootstrap": N_BOOTSTRAP,
                "n_events": 0,
                "n_users": 0,
                "filter_id": "selected_labelled_trajectories",
                "filter_description": "Selected labelled-regime trajectories at regular time intervals.",
                "run_mode": first["run_mode"],
                "paper_result": bool(first["paper_result"]),
                "notes": "Appendix trajectory diagnostic.",
            }
        )
    data = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 3, figsize=(PAPER_FIGURE_WIDTH_IN, 2.65), sharey=True)
    for ax, setting in zip(
        axes, ["zero_static", "aligned_static_delay_15", "state_structural_matched_15"]
    ):
        sub_setting = data[data["setting_id"].eq(setting)]
        for _, group in sub_setting.groupby("method_id", sort=False):
            group = group.sort_values("x_value")
            ax.plot(
                group["x_value"],
                group["y_value"],
                label=group["method_display_name"].iloc[0],
            )
            ax.fill_between(
                group["x_value"], group["ci_lower"], group["ci_upper"], alpha=0.15
            )
        ax.set_title(SETTING_LABELS[setting], fontsize=8)
        ax.set_xlabel("Structural time")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Cumulative causal regret")
    axes[-1].legend(fontsize=5.5, loc="best")
    fig.tight_layout()
    _write_bundle(
        root,
        "fig_app_exp1_selected_trajectories",
        data,
        fig,
        description="Selected seed-bootstrap cumulative regret trajectories in the labelled regime.",
        metric_id="cumulative_causal_regret",
        figure_size_in=(PAPER_FIGURE_WIDTH_IN, 2.65),
        figure_status="appendix",
    )


def plot_exp1_bundles(seed: pd.DataFrame, root: Path) -> None:
    _safe_columns(seed)
    _plot_validity_boundary(seed, root)
    _plot_same_mean_delay(seed, root)
    _plot_attribution_diagnostics(seed, root)
    _plot_proxy_quality(seed, root)
    _plot_mismatch_diagnostics(seed, root)
    _plot_selected_trajectories(seed, root)


# Backward-compatible name retained for existing rebuild commands.
def plot_validity_boundary(seed: pd.DataFrame, outputs: Path) -> None:
    plot_exp1_bundles(seed, outputs)
