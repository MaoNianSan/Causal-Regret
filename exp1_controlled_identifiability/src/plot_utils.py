from __future__ import annotations

"""Registered figure bundles for revised EXP1.

Important design rule
---------------------
Methods from different information regimes must never be compared in the
same panel.  Every method-level figure is therefore faceted by ``regime``:

* labelled: full source labels are available;
* mixture_labelled: only a fraction of source labels is available;
* unlabelled: no source labels are available.

This keeps method comparisons conditional on the same information set.
"""

from datetime import datetime, timezone
from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METHOD_LABELS = {
    "oracle": "Context oracle",
    "naive": "Arrival-time",
    "delayed_ucb": "Delayed-UCB",
    "delayed_exp3": "Delayed-EXP3",
    "causal_labeled": "Source-labelled",
    "causal_em": "Gaussian-integrated EM",
    "causal_em_misspecified": "Stationary-geometric EM",
    "proxy": "Filtered state proxy",
}

REGIME_LABELS = {
    "labelled": "Full source labels",
    "mixture_labelled": "Partial source labels",
    "unlabelled": "No source labels",
}

REGIME_ORDER = ["labelled", "mixture_labelled", "unlabelled"]

# Only methods that are meaningful under each information regime are plotted
# together.  The actual frame is further intersected with methods available in
# the result file, so this remains robust to intentionally omitted ablations.
REGIME_METHODS = {
    "labelled": [
        "oracle",
        "naive",
        "delayed_ucb",
        "delayed_exp3",
        "causal_labeled",
    ],
    "mixture_labelled": [
        "oracle",
        "naive",
        "delayed_ucb",
        "delayed_exp3",
        "causal_em",
        "causal_em_misspecified",
        "proxy",
    ],
    "unlabelled": [
        "oracle",
        "naive",
        "delayed_ucb",
        "delayed_exp3",
        "causal_em",
        "causal_em_misspecified",
        "proxy",
    ],
}


def _require_columns(frame: pd.DataFrame, required: set[str], context: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{context} is missing required columns: {missing}")


def _ordered_present(values: pd.Series, order: list[str]) -> list[str]:
    present = set(values.dropna().astype(str))
    return [value for value in order if value in present]


def _summary(frame: pd.DataFrame, group_cols: list[str], value: str) -> pd.DataFrame:
    """Mean, standard error, and normal-approximation 95% interval."""
    if frame.empty:
        return pd.DataFrame(columns=[*group_cols, "n", "mean", "se", "ci_low", "ci_high"])

    rows: list[dict[str, object]] = []
    for keys, sub in frame.groupby(group_cols, dropna=False, sort=False):
        values = pd.to_numeric(sub[value], errors="coerce").dropna().to_numpy(float)
        n = len(values)
        mean = float(values.mean()) if n else float("nan")
        se = float(values.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        key_values = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_cols, key_values))
        row.update(
            {
                "n": n,
                "mean": mean,
                "se": se,
                "ci_low": mean - 1.96 * se,
                "ci_high": mean + 1.96 * se,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _save(fig: plt.Figure, root: Path, name: str) -> None:
    pdf_dir = root / "figures" / "pdf"
    png_dir = root / "figures" / "png"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(pdf_dir / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(png_dir / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _write_metadata(root: Path, name: str, data: pd.DataFrame, description: str) -> None:
    data_dir = root / "figures" / "data"
    metadata_dir = root / "figures" / "metadata"
    data_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    data_path = data_dir / f"{name}_data.csv"
    data.to_csv(data_path, index=False)

    payload = {
        "figure_id": name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "data_csv": str(data_path.relative_to(root)),
        "paper_result": False,
        "comparison_rule": (
            "Method comparisons are made only within the same information regime. "
            "No panel mixes labelled, mixture_labelled, and unlabelled methods."
        ),
    }
    (metadata_dir / f"{name}_metadata.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _empty_panel(ax: plt.Axes, title: str) -> None:
    ax.set_title(title)
    ax.text(0.5, 0.5, "No eligible data", ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()


def _barplot_by_regime(
    summary: pd.DataFrame,
    x_col: str,
    title: str,
    ylabel: str,
    root: Path,
    name: str,
) -> None:
    """Grouped bars with one panel per information regime."""
    regimes = _ordered_present(summary["regime"], REGIME_ORDER)
    if not regimes:
        raise ValueError(f"{name}: no regimes available after filtering.")

    fig, axes = plt.subplots(
        1,
        len(regimes),
        figsize=(max(7.0, 5.2 * len(regimes)), 4.7),
        sharey=True,
        squeeze=False,
    )
    axes_flat = axes.ravel()

    for ax, regime in zip(axes_flat, regimes):
        regime_summary = summary[summary["regime"].eq(regime)].copy()
        methods = [
            method
            for method in REGIME_METHODS.get(regime, [])
            if method in set(regime_summary["method"])
        ]
        labels = list(regime_summary[x_col].drop_duplicates())
        if regime_summary.empty or not methods or not labels:
            _empty_panel(ax, REGIME_LABELS.get(regime, regime))
            continue

        x = np.arange(len(labels))
        width = 0.78 / len(methods)
        for j, method in enumerate(methods):
            sub = regime_summary[regime_summary["method"].eq(method)].set_index(x_col).reindex(labels)
            values = pd.to_numeric(sub["mean"], errors="coerce").to_numpy(float)
            ci95 = (
                pd.to_numeric(sub["se"], errors="coerce")
                .fillna(0.0)
                .to_numpy(float)
                * 1.96
            )
            offset = (j - (len(methods) - 1) / 2.0) * width
            ax.bar(
                x + offset,
                values,
                width,
                yerr=ci95,
                capsize=2,
                label=METHOD_LABELS.get(method, method),
            )

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=18, ha="right")
        ax.set_title(REGIME_LABELS.get(regime, regime))
        ax.set_xlabel("Delay mechanism")
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=7, loc="best")

    axes_flat[0].set_ylabel(ylabel)
    fig.suptitle(title, y=1.02)
    fig.tight_layout()
    _save(fig, root, name)


def _matched_delay_summary(seed: pd.DataFrame) -> pd.DataFrame:
    """Summarise matched-delay mechanisms separately within each regime."""
    matched_settings = [
        "geometric_matched_15",
        "mixture_matched_15",
        "state_structural_matched_15",
    ]
    matched = seed[seed["delay_setting"].isin(matched_settings)].copy()
    rows: list[dict[str, object]] = []

    for (regime, setting, method), sub in matched.groupby(
        ["regime", "delay_setting", "method"],
        sort=False,
    ):
        if method not in REGIME_METHODS.get(regime, []):
            continue
        regret = pd.to_numeric(sub["final_Rc"], errors="coerce") / pd.to_numeric(sub["T"], errors="coerce")
        regret = regret.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(float)
        delay = pd.to_numeric(sub["mean_delay"], errors="coerce").dropna().to_numpy(float)
        n = len(regret)
        if n == 0:
            continue
        rows.append(
            {
                "regime": regime,
                "delay_setting": setting,
                "method": method,
                "n": n,
                "mean_delay": float(delay.mean()) if len(delay) else float("nan"),
                "se_delay": float(delay.std(ddof=1) / np.sqrt(len(delay))) if len(delay) > 1 else 0.0,
                "mean_regret_per_round": float(regret.mean()),
                "se_regret_per_round": float(regret.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0,
                "policy_dependent_delay": False,
            }
        )
    return pd.DataFrame(rows)


def _plot_same_mean_delay(fig2: pd.DataFrame, root: Path) -> None:
    regimes = _ordered_present(fig2["regime"], REGIME_ORDER)
    if not regimes:
        raise ValueError("fig_exp1_same_mean_delay: no data available.")

    fig, axes = plt.subplots(
        1,
        len(regimes),
        figsize=(max(7.0, 5.2 * len(regimes)), 4.7),
        sharey=True,
        squeeze=False,
    )
    axes_flat = axes.ravel()

    for ax, regime in zip(axes_flat, regimes):
        sub_regime = fig2[fig2["regime"].eq(regime)].copy()
        methods = [
            method
            for method in REGIME_METHODS.get(regime, [])
            if method in set(sub_regime["method"])
        ]
        if sub_regime.empty or not methods:
            _empty_panel(ax, REGIME_LABELS.get(regime, regime))
            continue

        for method in methods:
            sub = sub_regime[sub_regime["method"].eq(method)]
            if sub.empty:
                continue
            ax.errorbar(
                sub["mean_delay"],
                sub["mean_regret_per_round"],
                xerr=1.96 * sub["se_delay"],
                yerr=1.96 * sub["se_regret_per_round"],
                fmt="o",
                capsize=3,
                label=METHOD_LABELS.get(method, method),
            )
            for _, row in sub.iterrows():
                annotation = str(row["delay_setting"]).replace("_matched_15", "")
                ax.annotate(
                    annotation,
                    (row["mean_delay"], row["mean_regret_per_round"]),
                    fontsize=7,
                    xytext=(3, 3),
                    textcoords="offset points",
                )

        ax.axvline(15.0, linewidth=0.8, linestyle="--")
        ax.set_title(REGIME_LABELS.get(regime, regime))
        ax.set_xlabel("Realised observed mean delay")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7, loc="best")

    axes_flat[0].set_ylabel("Excess conditional risk per round")
    fig.suptitle("Same observed mean delay, different mechanisms", y=1.02)
    fig.tight_layout()
    _save(fig, root, "fig_exp1_same_mean_delay")


def _plot_attribution_diagnostics(fig3: pd.DataFrame, root: Path) -> None:
    """Attribute diagnostics are also faceted by regime."""
    regimes = _ordered_present(fig3["regime"], ["mixture_labelled", "unlabelled"])
    metrics = [
        ("soft_attribution_true_mass", "Posterior mass on true source"),
        ("soft_attribution_top1_accuracy", "Top-1 source recovery"),
    ]

    if not regimes:
        raise ValueError("fig_exp1_attribution_diagnostics: no data available.")

    fig, axes = plt.subplots(
        len(regimes),
        len(metrics),
        figsize=(10.8, 3.7 * len(regimes)),
        sharey="col",
        squeeze=False,
    )

    for row_index, regime in enumerate(regimes):
        for col_index, (metric, metric_title) in enumerate(metrics):
            ax = axes[row_index, col_index]
            subset = fig3[
                fig3["regime"].eq(regime) & fig3["metric"].eq(metric)
            ].copy()
            methods = [
                method
                for method in REGIME_METHODS.get(regime, [])
                if method in set(subset["method"])
            ]
            if subset.empty or not methods:
                _empty_panel(ax, f"{REGIME_LABELS.get(regime, regime)}: {metric_title}")
                continue

            settings = list(subset["delay_setting"].drop_duplicates())
            for method in methods:
                sub = (
                    subset[subset["method"].eq(method)]
                    .set_index("delay_setting")
                    .reindex(settings)
                )
                ax.errorbar(
                    np.arange(len(settings)),
                    sub["mean"],
                    yerr=1.96 * sub["se"].fillna(0.0),
                    marker="o",
                    capsize=2,
                    label=METHOD_LABELS.get(method, method),
                )
            ax.set_xticks(np.arange(len(settings)))
            ax.set_xticklabels(settings, rotation=25, ha="right")
            ax.set_ylim(-0.02, 1.02)
            ax.set_ylabel("Accuracy")
            ax.set_title(f"{REGIME_LABELS.get(regime, regime)}: {metric_title}")
            ax.grid(axis="y", alpha=0.2)
            ax.legend(fontsize=7, loc="best")

    fig.tight_layout()
    _save(fig, root, "fig_exp1_attribution_diagnostics")


def _proxy_summary(seed: pd.DataFrame) -> pd.DataFrame:
    proxy = seed[
        (seed["method"].eq("proxy"))
        & (seed["regime"].eq("unlabelled"))
        & (
            seed["delay_setting"].isin(
                ["proxy_good_matched_15", "proxy_bad_matched_15"]
            )
        )
    ].copy()

    if proxy.empty:
        return pd.DataFrame(
            columns=[
                "delay_setting",
                "n",
                "proxy_state_error_mean",
                "proxy_state_error_se",
                "regret_per_round",
                "regret_per_round_se",
                "mean_delay",
                "mean_delay_se",
                "regime",
            ]
        )

    rows: list[dict[str, object]] = []
    for setting, sub in proxy.groupby("delay_setting", sort=False):
        error = pd.to_numeric(sub["proxy_state_error_mean"], errors="coerce").dropna().to_numpy(float)
        regret = (
            pd.to_numeric(sub["final_Rc"], errors="coerce")
            / pd.to_numeric(sub["T"], errors="coerce")
        ).replace([np.inf, -np.inf], np.nan).dropna().to_numpy(float)
        delay = pd.to_numeric(sub["mean_delay"], errors="coerce").dropna().to_numpy(float)
        rows.append(
            {
                "delay_setting": setting,
                "regime": "unlabelled",
                "n": len(sub),
                "proxy_state_error_mean": float(error.mean()) if len(error) else float("nan"),
                "proxy_state_error_se": float(error.std(ddof=1) / np.sqrt(len(error))) if len(error) > 1 else 0.0,
                "regret_per_round": float(regret.mean()) if len(regret) else float("nan"),
                "regret_per_round_se": float(regret.std(ddof=1) / np.sqrt(len(regret))) if len(regret) > 1 else 0.0,
                "mean_delay": float(delay.mean()) if len(delay) else float("nan"),
                "mean_delay_se": float(delay.std(ddof=1) / np.sqrt(len(delay))) if len(delay) > 1 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot_proxy_quality(fig4: pd.DataFrame, root: Path) -> None:
    if fig4.empty:
        raise ValueError("fig_exp1_proxy_quality: no eligible proxy-quality results.")

    fig, ax = plt.subplots(figsize=(6.8, 4.5))
    ax.errorbar(
        fig4["proxy_state_error_mean"],
        fig4["regret_per_round"],
        xerr=1.96 * fig4["proxy_state_error_se"],
        yerr=1.96 * fig4["regret_per_round_se"],
        fmt="o",
        capsize=3,
    )
    for _, row in fig4.iterrows():
        ax.annotate(
            str(row["delay_setting"]),
            (row["proxy_state_error_mean"], row["regret_per_round"]),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_xlabel(r"Time-averaged $|\hat{S}_t-S_t|$")
    ax.set_ylabel("Excess conditional risk per round")
    ax.set_title("Proxy quality and regret (no source labels)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    _save(fig, root, "fig_exp1_proxy_quality")


def plot_exp1_bundles(seed: pd.DataFrame, root: Path) -> None:
    """Generate registered, regime-stratified EXP1 figure bundles."""
    root = Path(root)
    _require_columns(
        seed,
        {
            "delay_setting",
            "regime",
            "method",
            "final_Rc",
            "T",
            "mean_delay",
            "soft_attribution_true_mass",
            "soft_attribution_top1_accuracy",
            "assignment_entropy",
            "proxy_state_error_mean",
        },
        "plot_exp1_bundles",
    )

    # Figure 1: core mechanism evidence, stratified by information regime.
    primary_settings = [
        "zero_static",
        "aligned_static_delay_15",
        "geometric_matched_15",
        "mixture_matched_15",
        "state_structural_matched_15",
    ]
    primary = seed[seed["delay_setting"].isin(primary_settings)].copy()
    primary = primary[primary["regime"].isin(REGIME_ORDER)].copy()
    primary = primary[
        primary.apply(
            lambda row: row["method"] in REGIME_METHODS.get(str(row["regime"]), []),
            axis=1,
        )
    ].copy()
    primary["regret_per_round"] = (
        pd.to_numeric(primary["final_Rc"], errors="coerce")
        / pd.to_numeric(primary["T"], errors="coerce")
    )
    fig1 = _summary(
        primary,
        ["regime", "delay_setting", "method"],
        "regret_per_round",
    )
    _write_metadata(
        root,
        "fig_exp1_validity_boundary",
        fig1,
        (
            "Context-information regret under aligned and source-binding-disrupted "
            "delay mechanisms. Every panel contains a single information regime."
        ),
    )
    _barplot_by_regime(
        fig1,
        "delay_setting",
        "EXP1: contextual causal regret",
        "Excess conditional risk per round",
        root,
        "fig_exp1_validity_boundary",
    )

    # Figure 2: matched observed mean delay, again stratified by information regime.
    fig2 = _matched_delay_summary(seed)
    _write_metadata(
        root,
        "fig_exp1_same_mean_delay",
        fig2,
        (
            "Primary mechanisms calibrated to the realised observed finite-horizon "
            "mean delay. Method comparisons are made only within each regime."
        ),
    )
    _plot_same_mean_delay(fig2, root)

    # Figure 3: genuine posterior attribution diagnostics, stratified by regime.
    attr = seed[
        seed["method"].isin(["causal_em", "causal_em_misspecified", "proxy"])
        & seed["regime"].isin(["mixture_labelled", "unlabelled"])
    ].copy()

    attr_rows: list[dict[str, object]] = []
    for keys, sub in attr.groupby(["delay_setting", "regime", "method"], sort=False):
        for metric in (
            "soft_attribution_true_mass",
            "soft_attribution_top1_accuracy",
            "assignment_entropy",
        ):
            values = pd.to_numeric(sub[metric], errors="coerce").dropna().to_numpy(float)
            attr_rows.append(
                {
                    "delay_setting": keys[0],
                    "regime": keys[1],
                    "method": keys[2],
                    "metric": metric,
                    "mean": float(values.mean()) if len(values) else float("nan"),
                    "se": float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0,
                    "n": len(values),
                }
            )
    fig3 = pd.DataFrame(attr_rows)
    _write_metadata(
        root,
        "fig_exp1_attribution_diagnostics",
        fig3,
        (
            "Soft posterior mass and top-1 source recovery accumulated over all "
            "unlabelled arrivals, with separate panels for each information regime."
        ),
    )
    _plot_attribution_diagnostics(fig3, root)

    # Figure 4: proxy-quality sweep is already a same-regime comparison, but now
    # includes uncertainty intervals.
    fig4 = _proxy_summary(seed)
    _write_metadata(
        root,
        "fig_exp1_proxy_quality",
        fig4,
        (
            "Proxy-quality sweep within the unlabelled regime: time-averaged Kalman "
            "state error versus contextual causal regret. The two settings share "
            "state, context, and delay paths; only proxy observation noise differs."
        ),
    )
    _plot_proxy_quality(fig4, root)


# Compatibility shim used by older modules.
def plot_validity_boundary(seed: pd.DataFrame, outputs: Path) -> None:
    plot_exp1_bundles(seed, outputs)
