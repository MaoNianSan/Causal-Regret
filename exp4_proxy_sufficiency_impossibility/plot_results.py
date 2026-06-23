"""Paper-facing Exp4 figures with compact diagnostic and recovery evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config


BASE_FIGURE_COLUMNS = [
    "figure_id", "panel_id", "experiment_id", "subexperiment_id", "setting_id", "method_id",
    "method_display_name", "information_interface", "reference_role", "diagnostic_only", "deployable",
    "metric_id", "metric_formula_id", "x_id", "x_value", "x_display_label", "y_value", "ci_lower",
    "ci_upper", "ci_level", "uncertainty_unit", "n_seeds", "n_bootstrap", "n_events", "n_users",
    "filter_id", "filter_description", "run_mode", "paper_result", "notes",
]


def _method_fields(method_id: str) -> dict[str, Any]:
    spec = config.method_spec(method_id)
    return {
        "method_display_name": spec["display"], "information_interface": spec["information_interface"],
        "reference_role": spec["reference_role"], "diagnostic_only": bool(spec["diagnostic_only"]),
        "deployable": bool(spec["deployable"]),
    }


def _errorbar(
    ax: plt.Axes,
    x: np.ndarray,
    mean: np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
    *,
    marker: str = "o",
    linestyle: str = "-",
    markersize: float | None = None,
    capsize: float = 2.0,
    linewidth: float | None = None,
    zorder: float | None = None,
    **kwargs: Any,
) -> None:
    valid_ci = np.isfinite(low).all() and np.isfinite(high).all()
    plot_markersize = config.MARKER_SIZE if markersize is None else markersize
    plot_linewidth = config.LINE_WIDTH if linewidth is None else linewidth
    if valid_ci:
        yerr = np.vstack([mean - low, high - mean])
        ax.errorbar(
            x, mean, yerr=yerr, marker=marker, markersize=plot_markersize, linestyle=linestyle,
            linewidth=plot_linewidth, capsize=capsize, elinewidth=max(plot_linewidth, 1.05),
            capthick=max(plot_linewidth, 1.05), zorder=zorder, **kwargs,
        )
    else:
        ax.plot(x, mean, marker=marker, markersize=plot_markersize, linestyle=linestyle, linewidth=plot_linewidth, zorder=zorder, **kwargs)


def _save(fig: plt.Figure, run_dir: Path, stem: str, data: pd.DataFrame, metadata: dict[str, Any]) -> None:
    protected_hashes_before = _protected_csv_hashes(run_dir)
    for ext in ["pdf", "png"]:
        fig.savefig(run_dir / "figures" / ext / f"{stem}.{ext}", dpi=config.PAPER_DPI, bbox_inches="tight")
    for col in BASE_FIGURE_COLUMNS:
        if col not in data:
            data[col] = np.nan
    data_path = run_dir / "figures" / "data" / f"{stem}_data.csv"
    if not data_path.exists():
        data[BASE_FIGURE_COLUMNS + [c for c in data.columns if c not in BASE_FIGURE_COLUMNS]].to_csv(data_path, index=False)
    protected_hashes_after = _protected_csv_hashes(run_dir)
    metadata["protected_csv_sha256_before_redraw"] = protected_hashes_before
    metadata["protected_csv_sha256_after_redraw"] = protected_hashes_after
    metadata["protected_csv_sha256_unchanged"] = protected_hashes_before == protected_hashes_after
    (run_dir / "figures" / "metadata" / f"{stem}_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    plt.close(fig)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _protected_csv_hashes(run_dir: Path) -> dict[str, str]:
    protected_dirs = [run_dir / "raw", run_dir / "summaries", run_dir / "figures" / "data"]
    hashes: dict[str, str] = {}
    for protected_dir in protected_dirs:
        if not protected_dir.exists():
            continue
        for path in sorted(protected_dir.glob("*.csv")):
            hashes[str(path.relative_to(run_dir)).replace("\\", "/")] = _sha256(path)
    return hashes


def _figure_row(*, figure_id: str, panel_id: str, run_config: dict[str, Any], subexperiment_id: str, setting_id: str,
                method_id: str, metric_id: str, metric_formula_id: str, x_id: str, x_value: float,
                x_display_label: str, y_value: float, ci_lower: float, ci_upper: float, n_seeds: int,
                n_bootstrap: int, uncertainty_unit: str, notes: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "figure_id": figure_id, "panel_id": panel_id, "experiment_id": config.EXPERIMENT_ID,
        "subexperiment_id": subexperiment_id, "setting_id": setting_id, "method_id": method_id,
        **_method_fields(method_id), "metric_id": metric_id, "metric_formula_id": metric_formula_id,
        "x_id": x_id, "x_value": float(x_value), "x_display_label": x_display_label, "y_value": float(y_value),
        "ci_lower": float(ci_lower) if np.isfinite(ci_lower) else np.nan,
        "ci_upper": float(ci_upper) if np.isfinite(ci_upper) else np.nan,
        "ci_level": run_config["ci_level"] if run_config["mode"] == "full" else np.nan,
        "uncertainty_unit": uncertainty_unit, "n_seeds": int(n_seeds), "n_bootstrap": int(n_bootstrap),
        "n_events": np.nan, "n_users": np.nan,
        "filter_id": "primary_setting_beta_200" if panel_id in {"a", "b", "c"} else "appendix_beta_sweep",
        "filter_description": "controlled structural_high setting with beta=2.00" if panel_id in {"a", "b", "c"} else "matched mean-delay coupling diagnostic",
        "run_mode": run_config["mode"], "paper_result": bool(run_config.get("paper_result", False)), "notes": notes,
    }
    if extra:
        row.update(extra)
    return row


def _summary_row(df: pd.DataFrame, method_id: str, q: float | None = None) -> pd.Series:
    sub = df[df["method_id"].eq(method_id)]
    if q is not None:
        sub = sub[np.isclose(sub["source_label_rate_q"], q)]
    return sub.iloc[0]


def run(run_dir: Path) -> None:
    summaries = run_dir / "summaries"
    run_config = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    mode = run_config["mode"]
    proxy = pd.read_csv(summaries / "proxy_distortion_diagnostic_summary.csv")
    source = pd.read_csv(summaries / "source_label_sweep_summary.csv")
    phase = pd.read_csv(summaries / "recoverability_phase_map_summary.csv")
    coupling = pd.read_csv(summaries / "delay_state_coupling_summary.csv")
    advantage = pd.read_csv(summaries / "source_binding_advantage_summary.csv")

    fig, axes = plt.subplots(1, 3, figsize=(config.PAPER_FIGURE_WIDTH_IN, 2.65), constrained_layout=True)
    figure_rows: list[dict[str, Any]] = []

    # (a) Diagnostic: no fitted functional curve is implied.
    p = proxy.sort_values("proxy_noise_sigma")
    x = p["proxy_state_error_per_round_mean"].to_numpy(float)
    y = p["absolute_proxy_distortion_per_round_mean"].to_numpy(float)
    x_low = p["proxy_state_error_per_round_ci_low"].to_numpy(float)
    x_high = p["proxy_state_error_per_round_ci_high"].to_numpy(float)
    y_low = p["absolute_proxy_distortion_per_round_ci_low"].to_numpy(float)
    y_high = p["absolute_proxy_distortion_per_round_ci_high"].to_numpy(float)
    if np.isfinite(x_low).all() and np.isfinite(x_high).all() and np.isfinite(y_low).all() and np.isfinite(y_high).all():
        axes[0].errorbar(x, y, xerr=np.vstack([x - x_low, x_high - x]), yerr=np.vstack([y - y_low, y_high - y]), marker="o", linestyle="None", capsize=1.8, markersize=config.MARKER_SIZE)
    else:
        axes[0].scatter(x, y, s=18)
    for xi, yi, sigma in zip(x, y, p["proxy_noise_sigma"], strict=True):
        axes[0].annotate(f"σ = {float(sigma):.2f}", (xi, yi), xytext=(3, 3), textcoords="offset points", fontsize=6.5)
    axes[0].margins(x=0.08, y=0.12)
    axes[0].set_xlabel("Proxy-state error", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[0].set_ylabel("Loss-map distortion (diagnostic)", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[0].text(0.0, 1.03, "(a)", transform=axes[0].transAxes, fontsize=config.PANEL_LABEL_FONT_SIZE, fontweight="bold")
    for _, row in p.iterrows():
        figure_rows.append(_figure_row(
            figure_id="fig_exp4_recoverability_boundary", panel_id="a", run_config=run_config,
            subexperiment_id="proxy_distortion_diagnostic", setting_id=f"sigma_{row.proxy_noise_sigma:.2f}",
            method_id="proxy_noisy_oracle_diagnostic", metric_id="absolute_proxy_distortion_per_round",
            metric_formula_id="mean_absolute_loss_map_difference", x_id="proxy_state_error_per_round",
            x_value=row.proxy_state_error_per_round_mean, x_display_label="Proxy-state error",
            y_value=row.absolute_proxy_distortion_per_round_mean, ci_lower=row.absolute_proxy_distortion_per_round_ci_low,
            ci_upper=row.absolute_proxy_distortion_per_round_ci_high, n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap,
            uncertainty_unit=row.uncertainty_unit, notes="Diagnostic control; point label gives proxy noise sigma.",
            extra={"x_ci_lower": row.proxy_state_error_per_round_ci_low, "x_ci_upper": row.proxy_state_error_per_round_ci_high, "proxy_noise_sigma": row.proxy_noise_sigma},
        ))

    # (b) Only recovery varies with q. The other two methods are deliberately rendered as horizontal references.
    source = source[np.isclose(source["proxy_noise_sigma"], config.DEFAULT_PROXY_SIGMA)].copy()
    recovery = source[source["method_id"].eq("proxy_label_recovery")].sort_values("source_label_rate_q")
    arrival = _summary_row(source, "arrival_time_naive", q=0.0)
    history = _summary_row(source, "observable_history_surrogate", q=0.0)
    reference = _summary_row(source, "source_labelled_reference", q=1.0)
    q_min, q_max = min(config.Q_GRID), max(config.Q_GRID)
    axes[1].axhline(arrival.causal_regret_per_round_mean, linestyle="--", linewidth=config.LINE_WIDTH)
    axes[1].axhline(history.causal_regret_per_round_mean, linestyle=":", linewidth=config.LINE_WIDTH)
    _errorbar(axes[1], recovery["source_label_rate_q"].to_numpy(float), recovery["causal_regret_per_round_mean"].to_numpy(float),
              recovery["causal_regret_per_round_ci_low"].to_numpy(float), recovery["causal_regret_per_round_ci_high"].to_numpy(float),
              marker="o", linestyle="-", markersize=2.7, capsize=4.0, linewidth=0.95, zorder=5)
    if np.isfinite(reference.causal_regret_per_round_ci_low) and np.isfinite(reference.causal_regret_per_round_ci_high):
        axes[1].errorbar([1.0], [reference.causal_regret_per_round_mean],
                         yerr=[[reference.causal_regret_per_round_mean - reference.causal_regret_per_round_ci_low], [reference.causal_regret_per_round_ci_high - reference.causal_regret_per_round_mean]],
                         marker="D", linestyle="None", capsize=4.0, markersize=config.MARKER_SIZE + 0.8,
                         markerfacecolor="none", markeredgewidth=1.0, elinewidth=1.1, capthick=1.1, zorder=6)
    else:
        axes[1].plot([1.0], [reference.causal_regret_per_round_mean], marker="D", linestyle="None", markersize=config.MARKER_SIZE + 0.8, markerfacecolor="none", markeredgewidth=1.0, zorder=6)
    axes[1].annotate("Arrival time", (q_max, arrival.causal_regret_per_round_mean), xytext=(-62, -10), textcoords="offset points", fontsize=6.3)
    axes[1].annotate("History surrogate", (q_max, history.causal_regret_per_round_mean), xytext=(-74, -11), textcoords="offset points", fontsize=6.3)
    anchor = recovery[np.isclose(recovery["source_label_rate_q"], 0.30)].iloc[0]
    axes[1].annotate("Proxy-label recovery", (anchor.source_label_rate_q, anchor.causal_regret_per_round_mean), xytext=(3, 7), textcoords="offset points", fontsize=6.3)
    axes[1].annotate(
        "Source-labelled\nreference at q = 1",
        (1.0, reference.causal_regret_per_round_mean),
        xytext=(0.42, reference.causal_regret_per_round_mean + 0.015),
        textcoords="data",
        fontsize=6.1,
        arrowprops={"arrowstyle": "-", "linewidth": 0.55, "shrinkA": 1.5, "shrinkB": 1.5},
    )
    axes[1].set_xlim(q_min - 0.03, q_max + 0.04)
    axes[1].set_xlabel("Source-ID retention q", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[1].set_ylabel("Causal regret per round", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[1].set_xticks(config.Q_GRID)
    axes[1].set_xticklabels(["0", ".1", ".3", ".5", ".7", "1"])
    axes[1].text(0.0, 1.03, "(b)", transform=axes[1].transAxes, fontsize=config.PANEL_LABEL_FONT_SIZE, fontweight="bold")
    for row, label, note in [
        (arrival, "arrival_time_naive", "Horizontal reference; invariant in q."),
        (history, "observable_history_surrogate", "Horizontal reference; invariant in q."),
        (reference, "source_labelled_reference", "Reference point at q=1; same action trace as proxy-label recovery at q=1."),
    ]:
        figure_rows.append(_figure_row(
            figure_id="fig_exp4_recoverability_boundary", panel_id="b", run_config=run_config,
            subexperiment_id="source_label_sweep", setting_id=f"q_{float(row.source_label_rate_q):.2f}_sigma_{config.DEFAULT_PROXY_SIGMA:.2f}",
            method_id=label, metric_id="causal_regret_per_round", metric_formula_id="post_warmup_structural_regret",
            x_id="source_label_rate_q", x_value=float(row.source_label_rate_q), x_display_label="Source-ID retention q",
            y_value=row.causal_regret_per_round_mean, ci_lower=row.causal_regret_per_round_ci_low, ci_upper=row.causal_regret_per_round_ci_high,
            n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap, uncertainty_unit=row.uncertainty_unit, notes=note,
        ))
    for _, row in recovery.iterrows():
        figure_rows.append(_figure_row(
            figure_id="fig_exp4_recoverability_boundary", panel_id="b", run_config=run_config,
            subexperiment_id="source_label_sweep", setting_id=f"q_{row.source_label_rate_q:.2f}_sigma_{config.DEFAULT_PROXY_SIGMA:.2f}",
            method_id="proxy_label_recovery", metric_id="causal_regret_per_round", metric_formula_id="post_warmup_structural_regret",
            x_id="source_label_rate_q", x_value=row.source_label_rate_q, x_display_label="Source-ID retention q",
            y_value=row.causal_regret_per_round_mean, ci_lower=row.causal_regret_per_round_ci_low, ci_upper=row.causal_regret_per_round_ci_high,
            n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap, uncertainty_unit=row.uncertainty_unit,
            notes=f"Fixed proxy noise sigma={config.DEFAULT_PROXY_SIGMA:.2f}.",
        ))

    # (c) The raw value is retained. vmin/vmax standardise display semantics only.
    q_values = sorted(phase["source_label_rate_q"].unique())
    sigma_values = sorted(phase["proxy_noise_sigma"].unique())
    matrix = phase.pivot(index="proxy_noise_sigma", columns="source_label_rate_q", values="oracle_normalized_recovery_mean").reindex(index=sigma_values, columns=q_values)
    image = axes[2].imshow(matrix.to_numpy(float), origin="lower", aspect="auto", vmin=0.0, vmax=1.0)
    axes[2].set_xticks(np.arange(len(q_values)), [f"{q:g}" for q in q_values])
    axes[2].set_yticks(np.arange(len(sigma_values)), [f"{sigma:g}" for sigma in sigma_values])
    axes[2].set_xlabel("Source-ID retention q", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[2].set_ylabel("Attribution-proxy noise σ", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes[2].text(0.0, 1.03, "(c)", transform=axes[2].transAxes, fontsize=config.PANEL_LABEL_FONT_SIZE, fontweight="bold")
    cbar = fig.colorbar(image, ax=axes[2], fraction=0.046, pad=0.04, ticks=[0.0, 0.5, 1.0])
    cbar.set_label("Arrival–oracle recovery", fontsize=6.6)
    for i, sigma in enumerate(sigma_values):
        for j, q in enumerate(q_values):
            current = float(matrix.loc[sigma, q])
            rgba = image.cmap(image.norm(current))
            luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
            axes[2].text(j, i, f"{current:.2f}", ha="center", va="center", fontsize=5.8,
                         color="white" if luminance < 0.45 else "black")
    for _, row in phase.iterrows():
        figure_rows.append(_figure_row(
            figure_id="fig_exp4_recoverability_boundary", panel_id="c", run_config=run_config,
            subexperiment_id="recoverability_phase_map", setting_id=f"q_{row.source_label_rate_q:.2f}_sigma_{row.proxy_noise_sigma:.2f}",
            method_id="proxy_label_recovery", metric_id="oracle_normalized_recovery", metric_formula_id="arrival_oracle_normalized_recovery",
            x_id="source_label_rate_q", x_value=row.source_label_rate_q, x_display_label="Source-label retention q",
            y_value=row.proxy_noise_sigma, ci_lower=row.oracle_normalized_recovery_ci_low, ci_upper=row.oracle_normalized_recovery_ci_high,
            n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap, uncertainty_unit=row.uncertainty_unit,
            notes="Heatmap raw metric is retained; vmin/vmax only standardise colour display. In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25. A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.",
            extra={"proxy_noise_sigma": row.proxy_noise_sigma, "heatmap_value": row.oracle_normalized_recovery_mean,
                   "source_labelled_normalized_recovery_value": row.source_labelled_normalized_recovery_mean},
        ))

    for axis in axes:
        axis.tick_params(labelsize=config.TICK_FONT_SIZE)
    _save(fig, run_dir, "fig_exp4_recoverability_boundary", pd.DataFrame(figure_rows), {
        "figure_id": "fig_exp4_recoverability_boundary", "figure_size_in": [config.PAPER_FIGURE_WIDTH_IN, 2.65], "dpi": config.PAPER_DPI,
        "mode": mode, "paper_result": bool(run_config.get("paper_result", False)), "figure_status": "fast_preview" if mode == "fast" else "paper_result",
        "panels": ["proxy distortion diagnostic", "source-label sweep", "recoverability phase map"],
        "primary_metric": "causal_regret_per_round", "uncertainty_unit": "shared_simulation_seed_percentile_bootstrap" if mode == "full" else "fast_preview_point_estimate_only",
        "ci_level": config.CI_LEVEL if mode == "full" else None, "n_bootstrap": config.BOOTSTRAP_N if mode == "full" else 0,
        "input_data_status": "complete_simulator", "uses_latent_oracle_as_plotted_method": False,
        "uses_latent_oracle_normalization": True, "phase_map_metric_raw_not_clipped": True,
        "phase_map_display_vmin": 0.0, "phase_map_display_vmax": 1.0,
        "caption_note": "Panels (b) and (c) use the structural_high setting with beta=2.00. Partial source labels provide the dominant recovery channel in this controlled setting. Attribution-proxy precision changes recovery modestly but does not substitute for source-linked feedback. In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25. A value of one corresponds to the latent action oracle, not to the source-labelled online reference. The phase map evaluates the specified fixed proxy-recovery route, not every proxy-only algorithm.",
    })

    # Appendix: mechanism support only. Panel (b) reduces to the source-binding advantage, not four redundant trajectories.
    fig2, axes2 = plt.subplots(1, 2, figsize=(config.PAPER_FIGURE_WIDTH_IN, 2.55), constrained_layout=True)
    mechanism = coupling[coupling["method_id"].eq("arrival_time_naive")].sort_values("delay_state_coupling_beta")
    _errorbar(axes2[0], mechanism["delay_state_coupling_beta"].to_numpy(float), mechanism["ranking_reversal_rate_mean"].to_numpy(float),
              mechanism["ranking_reversal_rate_ci_low"].to_numpy(float), mechanism["ranking_reversal_rate_ci_high"].to_numpy(float), marker="o", linestyle="-")
    axes2[0].set_xlabel("Delay-state coupling β", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes2[0].set_ylabel("Source-arrival ranking reversal", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes2[0].text(0.0, 1.03, "(a)", transform=axes2[0].transAxes, fontsize=config.PANEL_LABEL_FONT_SIZE, fontweight="bold")
    appendix_rows: list[dict[str, Any]] = []
    for _, row in mechanism.iterrows():
        appendix_rows.append(_figure_row(
            figure_id="fig_app_exp4_delay_state_coupling", panel_id="a", run_config=run_config,
            subexperiment_id="delay_state_coupling_diagnostic", setting_id=f"beta_{row.delay_state_coupling_beta:.2f}", method_id="arrival_time_naive",
            metric_id="ranking_reversal_rate", metric_formula_id="source_arrival_ranking_reversal", x_id="delay_state_coupling_beta",
            x_value=row.delay_state_coupling_beta, x_display_label="Delay-state coupling beta", y_value=row.ranking_reversal_rate_mean,
            ci_lower=row.ranking_reversal_rate_ci_low, ci_upper=row.ranking_reversal_rate_ci_high,
            n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap, uncertainty_unit=row.uncertainty_unit,
        ))
    adv = advantage.sort_values("delay_state_coupling_beta")
    _errorbar(axes2[1], adv["delay_state_coupling_beta"].to_numpy(float), adv["source_binding_advantage_mean"].to_numpy(float),
              adv["source_binding_advantage_ci_low"].to_numpy(float), adv["source_binding_advantage_ci_high"].to_numpy(float), marker="o", linestyle="-")
    axes2[1].axhline(0.0, linestyle="--", linewidth=0.8)
    axes2[1].set_xlabel("Delay-state coupling β", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes2[1].set_ylabel("Arrival minus source-bound regret", fontsize=config.AXIS_LABEL_FONT_SIZE)
    axes2[1].text(0.0, 1.03, "(b)", transform=axes2[1].transAxes, fontsize=config.PANEL_LABEL_FONT_SIZE, fontweight="bold")
    for _, row in adv.iterrows():
        appendix_rows.append(_figure_row(
            figure_id="fig_app_exp4_delay_state_coupling", panel_id="b", run_config=run_config,
            subexperiment_id="delay_state_coupling_diagnostic", setting_id=f"beta_{row.delay_state_coupling_beta:.2f}", method_id="source_labelled_reference",
            metric_id="source_binding_advantage", metric_formula_id="arrival_time_regret_minus_source_labelled_reference_regret",
            x_id="delay_state_coupling_beta", x_value=row.delay_state_coupling_beta, x_display_label="Delay-state coupling beta",
            y_value=row.source_binding_advantage_mean, ci_lower=row.source_binding_advantage_ci_low, ci_upper=row.source_binding_advantage_ci_high,
            n_seeds=row.n_seeds, n_bootstrap=row.n_bootstrap, uncertainty_unit=row.uncertainty_unit,
            notes="Positive values favour source binding. The source-binding advantage is positive across the tested coupling settings, but is not claimed to increase monotonically with beta. beta = 0 denotes no additional delay-state association. It does not imply zero delay or zero source-arrival mismatch.",
        ))
    for axis in axes2:
        axis.tick_params(labelsize=config.TICK_FONT_SIZE)
    _save(fig2, run_dir, "fig_app_exp4_delay_state_coupling", pd.DataFrame(appendix_rows), {
        "figure_id": "fig_app_exp4_delay_state_coupling", "figure_size_in": [config.PAPER_FIGURE_WIDTH_IN, 2.55], "dpi": config.PAPER_DPI,
        "mode": mode, "paper_result": bool(run_config.get("paper_result", False)), "figure_status": "appendix_diagnostic", "appendix_only": True,
        "panels": ["coupling mechanism diagnostic", "source-binding advantage"], "input_data_status": "complete_simulator",
        "ci_level": config.CI_LEVEL if mode == "full" else None, "n_bootstrap": config.BOOTSTRAP_N if mode == "full" else 0,
        "caption_note": "beta = 0 denotes no additional delay-state association. It does not imply zero delay or zero source-arrival mismatch. The source-binding advantage is positive across the tested coupling settings, but is not claimed to increase monotonically with beta.",
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir)


if __name__ == "__main__":
    main()
