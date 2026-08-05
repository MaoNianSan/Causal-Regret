from __future__ import annotations

"""Generate the three-panel main Exp1 figure from frozen figure data only."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import MECHANISM_ORDER
from src.artifact_io import (
    atomic_write_json,
    hash_payload,
    refresh_output_manifest,
    sha256_file,
    utc_now,
)

PROJECT_ROOT = Path(__file__).resolve().parent


def _row(data: pd.DataFrame, mechanism: str, panel: str, series: str) -> pd.Series:
    subset = data[
        (data.mechanism_id == mechanism)
        & (data.panel_id == panel)
        & (data.series_id == series)
    ]
    if len(subset) != 1:
        raise RuntimeError(
            f"Expected one row for {mechanism}/{panel}/{series}, got {len(subset)}"
        )
    return subset.iloc[0]


def _draw_panel_a_columns(
    ax: plt.Axes,
    data: pd.DataFrame,
    mechanisms: list[str],
    y: np.ndarray,
    col1_x: float,
    col2_x: float,
    header_y: float | None = None,
) -> list:
    """Draw the two right-aligned auxiliary columns of Panel (a).

    ``Mean delay`` (structural rounds, 1 decimal) and ``Conflict rate``
    (route-optimal conflict rate, 2 decimals) are placed at fixed
    axes-fraction x positions so the two headers and all numeric rows stay
    aligned and never overlap.  Returns the created Text artists so tests can
    verify non-overlap at render time.
    """
    if header_y is None:
        header_y = float(y.max()) + 0.55
    header_style = dict(
        fontsize=8.5, va="center", ha="right", clip_on=False, color="#333333"
    )
    value_style = dict(
        fontsize=8, va="center", ha="right", clip_on=False, color="#1f4e79"
    )
    panel_a = data[data.panel_id == "A"]
    delay_rows = panel_a[panel_a.series_id == "generated_mean_delay"].set_index(
        "mechanism_id"
    )
    conflict_rows = panel_a[panel_a.series_id == "ranking_reversal_rate"].set_index(
        "mechanism_id"
    )
    # Blended transform: x in axes-fraction, y in data coordinates.  Using a
    # plain transAxes transform with data y (0..N) would place the text many
    # axes-heights above the panel and collapse constrained_layout.
    transform = ax.get_yaxis_transform()
    texts: list = [
        ax.text(col1_x, header_y, "Mean delay", transform=transform, **header_style),
        ax.text(col2_x, header_y, "Conflict rate", transform=transform, **header_style),
    ]
    for mechanism, yi in zip(mechanisms, y, strict=True):
        texts.append(
            ax.text(
                col1_x,
                yi,
                f"{delay_rows.loc[mechanism, 'estimate']:.1f}",
                transform=transform,
                **value_style,
            )
        )
        texts.append(
            ax.text(
                col2_x,
                yi,
                f"{conflict_rows.loc[mechanism, 'estimate']:.2f}",
                transform=transform,
                **value_style,
            )
        )
    return texts


def _scientific_source_lineage() -> str:
    """Scientific lineage recorded when calibration was frozen."""
    manifest_path = PROJECT_ROOT / "calibration" / "exp1_calibration_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest.get("code_lineage", "unavailable")


def _presentation_source_lineage() -> str:
    """Fingerprint of the presentation-only figure source in this package."""
    import hashlib

    h = hashlib.sha256()
    for name in ("plot_main.py", "plot_appendix.py"):
        file_path = PROJECT_ROOT / name
        h.update(name.encode("utf-8"))
        h.update(file_path.read_bytes())
    return "presentation:" + h.hexdigest()


def generate(run_tier: str) -> tuple[Path, Path]:
    output = PROJECT_ROOT / "outputs" / run_tier
    data_path = output / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv"
    if not data_path.exists():
        raise RuntimeError(
            f"Missing frozen main-figure data: {data_path}. "
            f"Run `python main.py {run_tier}` and `python self_check.py --run {run_tier}` first."
        )
    data = pd.read_csv(data_path)
    mechanisms = list(MECHANISM_ORDER)
    labels = [
        data.loc[data.mechanism_id == mechanism, "mechanism_display_name"].iloc[0]
        for mechanism in mechanisms
    ]
    y = np.arange(len(mechanisms))[::-1]

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(14.5, 5.4),
        gridspec_kw={"width_ratios": [1.0, 1.05, 1.25]},
        constrained_layout=True,
    )

    # Shared row guides improve cross-panel reading.
    for axis in axes:
        for yi in y:
            axis.axhline(yi, linewidth=0.45, alpha=0.12, zorder=0)

    # Panel A: alignment budget with two right-aligned auxiliary columns.
    # ``Mean delay`` and ``Conflict rate`` (route-optimal conflict rate) are
    # drawn as separate aligned columns at fixed axes-fraction positions so the
    # headers and numeric rows never overlap.
    ANNOT_COL1_X = 0.70  # right edge of the ``Mean delay`` column
    ANNOT_COL2_X = 0.955  # right edge of the ``Conflict rate`` column
    DATA_WIDTH_FRACTION = 0.55  # alignment data occupies the left 55% of the panel
    ax = axes[0]
    for yi, mechanism in zip(y, mechanisms, strict=True):
        alignment = _row(data, mechanism, "A", "alignment_budget_rate")
        ax.errorbar(
            alignment.estimate,
            yi,
            xerr=[
                [alignment.estimate - alignment.ci_lower],
                [alignment.ci_upper - alignment.estimate],
            ],
            fmt="o",
            capsize=3,
            color="#1f4e79",
            ecolor="#1f4e79",
            markerfacecolor="#1f4e79",
            markeredgecolor="#1f4e79",
        )
    anchor = float(
        data[
            (data.panel_id == "A") & (data.series_id == "alignment_budget_rate")
        ].ci_upper.max()
    )
    ax.set_xlim(left=0, right=anchor / DATA_WIDTH_FRACTION)
    ax.set_ylim(-0.6, float(y.max()) + 0.9)
    _draw_panel_a_columns(ax, data, mechanisms, y, ANNOT_COL1_X, ANNOT_COL2_X)
    ax.set_yticks(y, labels)
    ax.set_xlabel(r"Alignment budget $\mathfrak{A}_T^{\mathrm{arr}}/T$")
    ax.set_title("(a) Route alignment")
    ax.grid(axis="x", alpha=0.25)

    # Panel B: structural regret and transfer bound, not a stacked decomposition.
    ax = axes[1]
    offset = 0.13
    for yi, mechanism in zip(y, mechanisms, strict=True):
        structural = _row(data, mechanism, "B", "structural_regret_rate")
        bound = _row(data, mechanism, "B", "transfer_bound_rate")
        ax.plot(
            [structural.estimate, bound.estimate], [yi, yi], linewidth=1.0, alpha=0.55
        )
        ax.errorbar(
            structural.estimate,
            yi - offset,
            xerr=[
                [structural.estimate - structural.ci_lower],
                [structural.ci_upper - structural.estimate],
            ],
            fmt="o",
            capsize=3,
            color="#1f4e79",
            ecolor="#1f4e79",
            markerfacecolor="#1f4e79",
            markeredgecolor="#1f4e79",
            label=r"$R_T^c/T$" if mechanism == mechanisms[0] else None,
        )
        ax.errorbar(
            bound.estimate,
            yi + offset,
            xerr=[[bound.estimate - bound.ci_lower], [bound.ci_upper - bound.estimate]],
            fmt="s",
            capsize=3,
            color="#d97706",
            ecolor="#d97706",
            markerfacecolor="white",
            markeredgecolor="#d97706",
            label=(
                r"$(R_T^r+\mathfrak{A}_T^r)/T$" if mechanism == mechanisms[0] else None
            ),
        )
    ax.set_yticks(y, [])
    ax.set_xlim(left=0)
    ax.set_xlabel("Regret rate")
    ax.set_title("(b) Regret transfer")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, fontsize=8, loc="upper right")

    # Panel C: same learner, different scalar-feedback binding.
    ax = axes[2]
    for yi, mechanism in zip(y, mechanisms, strict=True):
        arrival = _row(data, mechanism, "C", "arrival_clock")
        source = _row(data, mechanism, "C", "source_round")
        contrast = _row(data, mechanism, "C", "paired_contrast")
        ax.plot(
            [source.estimate, arrival.estimate], [yi, yi], linewidth=1.2, alpha=0.65
        )
        ax.errorbar(
            arrival.estimate,
            yi,
            xerr=[
                [arrival.estimate - arrival.ci_lower],
                [arrival.ci_upper - arrival.estimate],
            ],
            fmt="o",
            capsize=3,
            color="#b54708",
            ecolor="#b54708",
            markerfacecolor="#b54708",
            markeredgecolor="#b54708",
            label="Arrival-clock binding" if mechanism == mechanisms[0] else None,
        )
        ax.errorbar(
            source.estimate,
            yi,
            xerr=[
                [source.estimate - source.ci_lower],
                [source.ci_upper - source.estimate],
            ],
            fmt="s",
            capsize=3,
            color="#2e7d32",
            ecolor="#2e7d32",
            markerfacecolor="white",
            markeredgecolor="#2e7d32",
            label="Source-round binding" if mechanism == mechanisms[0] else None,
        )
        right = max(arrival.ci_upper, source.ci_upper)
        ax.annotate(
            rf"$\Delta$={contrast.estimate:.3f}",
            (right, yi),
            xytext=(7, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
        )
    ax.set_yticks(y, [])
    ax.set_xlim(left=0)
    ax.set_xlabel(r"Structural regret $R_T^c/T$")
    ax.set_title("(c) Same learner, different binding")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    fig.suptitle(
        "Controlled alignment, regret transfer, and learner consequences", fontsize=13
    )
    png = output / "figures" / "png" / "fig_exp1_alignment_transfer.png"
    pdf = output / "figures" / "pdf" / "fig_exp1_alignment_transfer.pdf"
    png.parent.mkdir(parents=True, exist_ok=True)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    scientific_manifest = json.loads(
        (PROJECT_ROOT / "calibration" / "exp1_calibration_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    metadata = {
        "figure_id": "fig_exp1_alignment_transfer",
        "run_tier": run_tier,
        "paper_result": bool(data.paper_result.all()),
        "source_figure_data": str(data_path),
        "source_figure_data_sha256": sha256_file(data_path),
        "png_sha256": sha256_file(png),
        "pdf_sha256": sha256_file(pdf),
        "generated_at": utc_now(),
        "scientific_source_lineage": _scientific_source_lineage(),
        "presentation_source_lineage": _presentation_source_lineage(),
        "scientific_artifact_manifest_hash": hash_payload(scientific_manifest),
        "figure_data_hash": sha256_file(data_path),
        "figure_code_hash": sha256_file(PROJECT_ROOT / "plot_main.py"),
        "panels": {
            "A": (
                "arrival-route action-gap alignment budget with right-aligned "
                "Mean delay and Conflict rate (route-optimal conflict rate) columns"
            ),
            "B": "structural regret and the regret-transfer upper bound",
            "C": (
                "paired contextual Delayed EXP3 consequence under arrival-clock "
                "and source-round scalar-feedback binding"
            ),
        },
    }
    atomic_write_json(
        output / "figures" / "metadata" / "fig_exp1_alignment_transfer_metadata.json",
        metadata,
    )
    refresh_output_manifest(output)
    return png, pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_tier", nargs="?", choices=("fast", "full"))
    parser.add_argument("--run", dest="run_option", choices=("fast", "full"))
    args = parser.parse_args()
    run_tier = args.run_option or args.run_tier
    if run_tier is None:
        parser.error("provide run tier positionally or with --run")
    png, pdf = generate(run_tier)
    print("MAIN_FIGURE_COMPLETE")
    print(f"png={png}")
    print(f"pdf={pdf}")


if __name__ == "__main__":
    main()
