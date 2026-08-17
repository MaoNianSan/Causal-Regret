"""Exp1 presentation-only renderer over frozen full-run artifacts."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from presentation.common import (
    PreviewLayout,
    assert_no_suptitle,
    configure_matplotlib,
    standardize_long_form,
    write_figure_bundle,
)
from presentation.renderers import (
    figure_metadata,
    write_manifest,
    write_standard_table,
    write_table_frame,
)
from presentation_sources import PresentationSource

MECHANISMS = [
    "zero_delay",
    "exact_valid_shift",
    "geometric_delay",
    "mixture_delay",
    "state_coupled_delay",
    "systematic_misbinding",
]
MAIN_CONTRACT = {
    "layout": [1, 3],
    "canvas_inches": [7.1, 3.6],
    "mechanisms": MECHANISMS,
    "panel_a": ["alignment_budget_rate", "generated_mean_delay"],
    "panel_b": ["structural_regret_rate", "transfer_bound_rate"],
    "panel_b_intervals": ["structural_regret_rate", "transfer_bound_rate"],
    "panel_c": ["arrival_clock", "source_round", "paired_contrast"],
    "panel_c_intervals": ["arrival_clock", "source_round"],
    "panel_c_no_interval": ["paired_contrast"],
    "main_exclusions": ["ranking_reversal_rate"],
}


def build_main_long_form(
    data: pd.DataFrame, source: PresentationSource
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in data.iterrows():
        if str(row["series_id"]) == "ranking_reversal_rate":
            continue
        rows.append(
            {
                "panel_id": str(row["panel_id"]).lower(),
                "metric_id": str(row["metric_id"]),
                "estimand_id": str(row["metric_id"]),
                "condition_id": str(row["mechanism_id"]),
                "series_id": str(row["series_id"]),
                "point_estimate": row["estimate"],
                "interval_lower": row["ci_lower"],
                "interval_upper": row["ci_upper"],
                "uncertainty_role": "95% seed-bootstrap interval",
                "uncertainty_method": "seed_bootstrap",
                "repetition_count": row.get("bootstrap_repetitions", pd.NA),
                "sample_count": row.get("n_seeds", pd.NA),
                "unit": "rate",
                "better_direction": "lower",
                "source_table": "fig_exp1_alignment_transfer_data.csv",
                "source_row_key": str(index),
            }
        )
    return standardize_long_form(
        pd.DataFrame(rows),
        figure_id=source.main_figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=False,
    )


def _metadata(
    source: PresentationSource,
    *,
    claim: str,
    panels: dict[str, str],
    metrics: dict[str, str],
    boundary: str,
    contract: dict[str, Any],
    uncertainty: str,
    sample_count: Any = "NA",
    marker_semantics: dict[str, str] | None = None,
) -> dict[str, Any]:
    return figure_metadata(
        source,
        claim=claim,
        panels=panels,
        metrics=metrics,
        boundary=boundary,
        code_paths=[Path(__file__)],
        contract=contract,
        sample_count=sample_count,
        uncertainty=uncertainty,
        marker_semantics=marker_semantics,
    )


def _appendix_composite(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    title: str,
    paths: list[Path],
) -> None:
    frames = [(path, pd.read_csv(path)) for path in paths]
    fig, axes = plt.subplots(
        1, len(frames), figsize=(7.1, 3.0), constrained_layout=True, squeeze=False
    )
    long_rows: list[dict[str, Any]] = []
    for panel_index, (path, frame) in enumerate(frames):
        axis = axes[0, panel_index]
        numeric = [
            column
            for column in frame.columns
            if pd.api.types.is_numeric_dtype(frame[column])
            and column not in {"seed", "t", "n_seeds", "bootstrap_repetitions"}
        ]
        for column in numeric[:2]:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            axis.plot(values.index, values, marker=".", linewidth=0.8, label=column)
            for source_index, value in values.items():
                long_rows.append(
                    {
                        "panel_id": chr(ord("a") + panel_index),
                        "metric_id": column,
                        "estimand_id": column,
                        "condition_id": path.stem,
                        "series_id": column,
                        "point_estimate": value,
                        "uncertainty_role": "frozen appendix diagnostic",
                        "uncertainty_method": "source table",
                        "source_table": path.name,
                        "source_row_key": str(source_index),
                    }
                )
        if numeric:
            axis.legend(frameon=False, fontsize=6.5)
        axis.set_title(
            path.stem.replace("fig_exp1_", "")
            .replace("_data", "")
            .replace("_", " ")
            .title(),
            loc="left",
            fontweight="bold",
        )
        axis.set_xlabel("Frozen source row")
        axis.grid(axis="y", alpha=0.2)
    assert_no_suptitle(fig)
    long_frame = standardize_long_form(
        pd.DataFrame(long_rows),
        figure_id=figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=False,
        analysis_tier="appendix",
    )
    write_figure_bundle(
        fig,
        long_frame,
        layout,
        figure_id=figure_id,
        section="appendix",
        metadata=_metadata(
            source,
            claim=title,
            panels={chr(ord("a") + i): path.stem for i, path in enumerate(paths)},
            metrics={},
            boundary="Appendix diagnostic from frozen full-run sources; no new scientific estimate.",
            contract={
                "layout": [1, len(paths)],
                "sources": [path.name for path in paths],
            },
            uncertainty="Frozen source diagnostic",
        ),
        source_files=paths,
    )


TARGETED_BINDING_LABELS = {
    "arrival_clock": "Arrival-clock binding",
    "source_round": "Source-round binding",
}


def _targeted_validation_figure(
    source: PresentationSource,
    layout: PreviewLayout,
    *,
    figure_id: str,
    path: Path,
) -> None:
    """Render the frozen targeted-validation source as (a) mean-delay
    robustness and (b) systematic-misbinding horizon scaling with the frozen
    95% seed-bootstrap intervals.  No targeted validation is recomputed."""
    frame = pd.read_csv(path)
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.0), constrained_layout=True)
    long_rows: list[dict[str, Any]] = []
    specs = [
        (
            0,
            "mean_delay_robustness",
            "target_mean_delay",
            "structural_regret_rate",
            "Target mean delay",
            r"Structural regret rate, $R_T^c/T$",
            "(a) Mean-delay robustness",
        ),
        (
            1,
            "horizon_scaling",
            "target_horizon",
            "structural_regret",
            r"Horizon $T$",
            r"Cumulative structural regret, $R_T^c$",
            "(b) Systematic-misbinding horizon scaling",
        ),
    ]
    for panel_index, component, x_column, metric_id, xlabel, ylabel, title in specs:
        axis = axes[panel_index]
        panel = frame[frame.targeted_component.eq(component)]
        for binding, color in (
            ("arrival_clock", "#b54708"),
            ("source_round", "#2e7d32"),
        ):
            group = panel[
                panel.feedback_binding_id.eq(binding) & panel.metric_id.eq(metric_id)
            ].sort_values(x_column)
            axis.errorbar(
                group[x_column],
                group.estimate,
                yerr=[group.estimate - group.ci_lower, group.ci_upper - group.estimate],
                fmt="o-",
                capsize=2.5,
                color=color,
                ecolor=color,
                linewidth=0.9,
                markersize=3.4,
                label=TARGETED_BINDING_LABELS[binding],
            )
            for source_index, row in group.iterrows():
                long_rows.append(
                    {
                        "panel_id": chr(ord("a") + panel_index),
                        "metric_id": metric_id,
                        "estimand_id": metric_id,
                        "condition_id": f"{component}:{binding}",
                        "series_id": f"{binding}_{x_column}",
                        "point_estimate": row.estimate,
                        "interval_lower": row.ci_lower,
                        "interval_upper": row.ci_upper,
                        "uncertainty_role": "95% seed-bootstrap interval",
                        "uncertainty_method": "seed_bootstrap",
                        "repetition_count": row.get("bootstrap_repetitions", pd.NA),
                        "sample_count": row.get("n_seeds", pd.NA),
                        "unit": (
                            "rate"
                            if metric_id == "structural_regret_rate"
                            else "regret"
                        ),
                        "better_direction": "lower",
                        "source_table": path.name,
                        "source_row_key": str(source_index),
                    }
                )
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        axis.set_title(title, loc="left", fontweight="bold")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=6.5)
    assert_no_suptitle(fig)
    long_frame = standardize_long_form(
        pd.DataFrame(long_rows),
        figure_id=figure_id,
        experiment_id=source.experiment_id,
        run_id=source.run_id,
        run_tier=source.run_tier,
        paper_result=False,
        analysis_tier="appendix",
    )
    write_figure_bundle(
        fig,
        long_frame,
        layout,
        figure_id=figure_id,
        section="appendix",
        metadata=_metadata(
            source,
            claim="Mean-delay robustness and systematic-misbinding horizon scaling from the frozen targeted validation.",
            panels={
                "a": "Structural regret rate across target mean delays.",
                "b": "Cumulative structural regret across horizons.",
            },
            metrics={
                "structural_regret_rate": "R_T^c/T",
                "structural_regret": "R_T^c",
            },
            boundary="Appendix diagnostic from the frozen targeted-validation source; no targeted recomputation.",
            contract={"layout": [1, 2], "sources": [path.name]},
            uncertainty="95% seed-bootstrap interval",
        ),
        source_files=[path],
    )


def render_presentation(
    source: PresentationSource, preview_root: Path
) -> dict[str, Any]:
    configure_matplotlib()
    layout = PreviewLayout(preview_root, source.experiment_id, source.run_id)
    data_path = source.source_run / "figures/data/fig_exp1_alignment_transfer_data.csv"
    table_path = source.source_run / "tables/tab_exp1_mechanism_summary.csv"
    data = pd.read_csv(data_path)
    data["mechanism_id"] = pd.Categorical(
        data["mechanism_id"], MECHANISMS, ordered=True
    )
    data = data.sort_values(["mechanism_id", "panel_id", "series_id"])
    labels = (
        data.drop_duplicates("mechanism_id")
        .set_index("mechanism_id")["mechanism_display_name"]
        .reindex(MECHANISMS)
        .tolist()
    )
    y = np.arange(len(MECHANISMS))[::-1]
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 3.6), constrained_layout=True)
    for axis in axes:
        axis.axvline(0, color="0.55", linewidth=0.7, linestyle="--", zorder=0)
        axis.grid(axis="x", alpha=0.22, linewidth=0.55)

    panel_a = data[data.panel_id.eq("A")]
    for yi, mechanism in zip(y, MECHANISMS, strict=True):
        row = panel_a[
            panel_a.mechanism_id.eq(mechanism)
            & panel_a.series_id.eq("alignment_budget_rate")
        ].iloc[0]
        axes[0].errorbar(
            row.estimate,
            yi,
            xerr=[[row.estimate - row.ci_lower], [row.ci_upper - row.estimate]],
            fmt="o",
            color="#1f4e79",
            ecolor="#1f4e79",
            capsize=2.5,
            markersize=3.6,
        )
        delay = panel_a[
            panel_a.mechanism_id.eq(mechanism)
            & panel_a.series_id.eq("generated_mean_delay")
        ].iloc[0]
        axes[0].text(
            0.98,
            yi,
            f"{delay.estimate:.1f}",
            transform=axes[0].get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=7.2,
        )
    axes[0].text(
        0.98,
        y.max() + 0.52,
        "Mean delay",
        transform=axes[0].get_yaxis_transform(),
        ha="right",
        va="center",
        fontsize=7.4,
        fontweight="bold",
    )
    axes[0].set_yticks(y, labels)
    axes[0].set_xlabel(r"Alignment budget rate, $A_T^{arr}/T$")
    axes[0].set_title(
        "(a) Route alignment under matched delay", loc="left", fontweight="bold"
    )

    panel_b = data[data.panel_id.eq("B")]
    for yi, mechanism in zip(y, MECHANISMS, strict=True):
        structural = panel_b[
            panel_b.mechanism_id.eq(mechanism)
            & panel_b.series_id.eq("structural_regret_rate")
        ].iloc[0]
        bound = panel_b[
            panel_b.mechanism_id.eq(mechanism)
            & panel_b.series_id.eq("transfer_bound_rate")
        ].iloc[0]
        axes[1].plot(
            [structural.estimate, bound.estimate], [yi, yi], color="0.4", linewidth=0.8
        )
        axes[1].errorbar(
            structural.estimate,
            yi,
            xerr=[
                [structural.estimate - structural.ci_lower],
                [structural.ci_upper - structural.estimate],
            ],
            fmt="none",
            ecolor="#182b49",
            elinewidth=0.8,
            capsize=2.0,
        )
        axes[1].plot(
            structural.estimate,
            yi,
            marker="o",
            color="#182b49",
            markersize=4.2,
            label=r"$R_T^c/T$" if yi == y[0] else None,
        )
        axes[1].errorbar(
            bound.estimate,
            yi,
            xerr=[[bound.estimate - bound.ci_lower], [bound.ci_upper - bound.estimate]],
            fmt="none",
            ecolor="#b8860b",
            elinewidth=0.8,
            capsize=2.0,
        )
        axes[1].plot(
            bound.estimate,
            yi,
            marker="s",
            markerfacecolor="white",
            markeredgecolor="#b8860b",
            color="#b8860b",
            markersize=4.2,
            label=r"$(R_T^r+A_T^r)/T$" if yi == y[0] else None,
        )
    axes[1].set_yticks(y, [])
    axes[1].set_xlabel("Rate")
    axes[1].set_title(
        "(b) Structural regret and transfer bound", loc="left", fontweight="bold"
    )
    axes[1].legend(frameon=False, loc="upper right")

    panel_c = data[data.panel_id.eq("C")]
    for yi, mechanism in zip(y, MECHANISMS, strict=True):
        arrival = panel_c[
            panel_c.mechanism_id.eq(mechanism) & panel_c.series_id.eq("arrival_clock")
        ].iloc[0]
        source_row = panel_c[
            panel_c.mechanism_id.eq(mechanism) & panel_c.series_id.eq("source_round")
        ].iloc[0]
        contrast = panel_c[
            panel_c.mechanism_id.eq(mechanism) & panel_c.series_id.eq("paired_contrast")
        ].iloc[0]
        axes[2].plot(
            [source_row.estimate, arrival.estimate],
            [yi, yi],
            color="0.45",
            linewidth=0.8,
        )
        axes[2].errorbar(
            arrival.estimate,
            yi,
            xerr=[
                [arrival.estimate - arrival.ci_lower],
                [arrival.ci_upper - arrival.estimate],
            ],
            fmt="none",
            ecolor="#b54708",
            elinewidth=0.7,
            capsize=1.5,
        )
        axes[2].plot(
            arrival.estimate,
            yi,
            marker="o",
            color="#b54708",
            markersize=4.2,
            label="Arrival-clock" if yi == y[0] else None,
        )
        axes[2].errorbar(
            source_row.estimate,
            yi,
            xerr=[
                [source_row.estimate - source_row.ci_lower],
                [source_row.ci_upper - source_row.estimate],
            ],
            fmt="none",
            ecolor="#2e7d32",
            elinewidth=0.7,
            capsize=1.5,
        )
        axes[2].plot(
            source_row.estimate,
            yi,
            marker="s",
            markerfacecolor="white",
            markeredgecolor="#2e7d32",
            color="#2e7d32",
            markersize=4.2,
            label="Source-round" if yi == y[0] else None,
        )
        axes[2].text(
            0.98,
            yi,
            rf"$\Delta$ {contrast.estimate:.3f}",
            transform=axes[2].get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=7.1,
        )
    axes[2].set_yticks(y, [])
    axes[2].set_xlabel(r"Structural regret $R_T^c/T$")
    axes[2].set_title("(c) Factual-feedback binding", loc="left", fontweight="bold")
    axes[2].legend(frameon=False, loc="upper left")
    assert_no_suptitle(fig)

    main = write_figure_bundle(
        fig,
        build_main_long_form(data, source),
        layout,
        figure_id=source.main_figure_id,
        section="main",
        metadata=_metadata(
            source,
            claim="Alignment, structural regret transfer, and scalar-feedback binding across canonical mechanisms.",
            panels={
                "a": "Horizontal alignment-budget forest with one mean-delay column.",
                "b": "Structural regret and transfer bound.",
                "c": "Arrival-clock versus source-round binding.",
            },
            metrics={
                "alignment_budget_rate": "A_T^arr/T",
                "structural_regret_rate": "R_T^c/T",
                "transfer_bound_rate": "(R_T^r+A_T^r)/T",
            },
            boundary="Action-gap alignment controls transfer; learner allocation is a separate consequence.",
            contract=MAIN_CONTRACT,
            sample_count="30 seeds",
            uncertainty="95% seed-bootstrap interval",
            marker_semantics={
                "filled_circle": "structural or arrival-clock estimate",
                "open_square": "transfer bound or source-round estimate",
                "horizontal_line": "within-mechanism contrast",
                "horizontal_interval": "95% seed-bootstrap interval from frozen ci_lower/ci_upper fields",
            },
        ),
        source_files=[data_path],
    )

    appendix_groups = [
        (
            "exp1_appendix_delay_coupling_diagnostics",
            "Delay survival and state-coupling verification",
            [
                source.source_run / "figures/data/fig_exp1_delay_survival_data.csv",
                source.source_run / "figures/data/fig_exp1_state_coupling_data.csv",
            ],
        ),
        (
            "exp1_appendix_reversal_trajectory_diagnostics",
            "Reversal-margin and route-trajectory diagnostics",
            [
                source.source_run / "figures/data/fig_exp1_reversal_margin_data.csv",
                source.source_run / "figures/data/fig_exp1_route_trajectory_data.csv",
            ],
        ),
    ]
    for figure_id, title, paths in appendix_groups:
        _appendix_composite(
            source, layout, figure_id=figure_id, title=title, paths=paths
        )
    targeted_path = (
        source.source_run / "targeted" / "fig_exp1_targeted_validation_data.csv"
    )
    _targeted_validation_figure(
        source,
        layout,
        figure_id="exp1_appendix_targeted_validation",
        path=targeted_path,
    )

    table = pd.read_csv(table_path)
    protocol_columns = ["mechanism_id", "mechanism", "mean_delay"]
    write_table_frame(
        layout,
        table[protocol_columns],
        "tab_exp1_mechanism_protocol",
        semantics="Mechanism protocol and matched-delay summary.",
        source_files=[table_path],
    )
    write_standard_table(
        layout,
        table_path,
        "tab_exp1_mechanism_summary",
        semantics="Complete mechanism table including conflict-rate values removed from main Panel (a).",
    )
    appendix_ids = [item[0] for item in appendix_groups] + [
        "exp1_appendix_targeted_validation"
    ]
    write_manifest(layout, source, figure_ids=[source.main_figure_id])
    write_manifest(layout, source, appendix=True, figure_ids=appendix_ids)
    return {"layout": layout, "main": main, "appendix_ids": appendix_ids}


__all__ = [
    "MAIN_CONTRACT",
    "build_main_long_form",
    "render_presentation",
    "_targeted_validation_figure",
]
