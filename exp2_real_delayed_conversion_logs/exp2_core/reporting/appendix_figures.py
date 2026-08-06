from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

from contracts import PRIMARY_SOURCE_ROUTE_ORDER
from ..data.io import write_json

from .artifact_metadata import save_figure, sha256
from .style import dynamic_tv_upper, set_publication_style


def _pairwise_matrix(pairwise: pd.DataFrame, metric: str, diagonal: float | None) -> pd.DataFrame:
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    matrix = pd.DataFrame(np.nan, index=routes, columns=routes, dtype=float)
    if diagonal is not None:
        np.fill_diagonal(matrix.values, diagonal)
    for row in pairwise.itertuples(index=False):
        value = float(getattr(row, metric))
        matrix.loc[row.route_left, row.route_right] = value
        matrix.loc[row.route_right, row.route_left] = value
    return matrix


def make_pairwise_appendix_figure(
    source_pairwise: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    set_publication_style(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tv_upper = dynamic_tv_upper(source_pairwise["allocation_tv"])
    definitions: list[tuple[str, str, float, float, float, str, Any]] = [
        ("allocation_tv", "Allocation TV", 0.0, tv_upper, 0.0, "viridis", None),
        ("top_k_overlap", "Top-10 overlap", 0.0, 1.0, 1.0, "viridis", None),
        (
            "kendall_tau_b",
            "Kendall tau-b",
            -1.0,
            1.0,
            1.0,
            "coolwarm",
            TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0),
        ),
    ]
    routes = list(PRIMARY_SOURCE_ROUTE_ORDER)
    display = ["First", "Last", "Linear", "Time-decay"]
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(float(config["plots"].get("appendix_figure_width_in", 7.1)), 2.9),
        constrained_layout=True,
    )
    source_rows: list[dict[str, object]] = []
    upper_triangle_mask = np.tril(np.ones((len(routes), len(routes)), dtype=bool), k=0)
    for ax, (metric, title, vmin, vmax, diagonal, cmap, norm) in zip(
        axes, definitions, strict=True
    ):
        matrix = _pairwise_matrix(source_pairwise, metric, diagonal)
        shown = np.ma.array(matrix.to_numpy(dtype=float), mask=upper_triangle_mask)
        image_kwargs: dict[str, Any] = {"aspect": "equal", "cmap": cmap}
        if norm is None:
            image_kwargs.update({"vmin": vmin, "vmax": vmax})
        else:
            image_kwargs["norm"] = norm
        image = ax.imshow(shown, **image_kwargs)
        ax.set_title(title)
        ax.set_xticks(range(len(routes)), display, rotation=45, ha="right")
        ax.set_yticks(range(len(routes)), display)
        for i, left in enumerate(routes):
            for j, right in enumerate(routes):
                value = matrix.iloc[i, j]
                source_rows.append(
                    {"metric": metric, "route_left": left, "route_right": right, "value": value}
                )
                if j <= i:
                    continue
                label = "NA" if np.isnan(value) else f"{value:.2f}"
                ax.text(j, i, label, ha="center", va="center", fontsize=6.0)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    source_path = output_dir / "figure_exp2_pairwise_appendix_data.csv"
    pd.DataFrame(source_rows).to_csv(source_path, index=False)
    base = output_dir / "figure_exp2_pairwise_appendix"
    files = save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_pairwise_appendix",
        "source_data": source_path.name,
        "source_data_sha256": sha256(source_path),
        "figure_files": {path.name: sha256(path) for path in files},
        "allocation_tv_color_limit": [0.0, tv_upper],
        "matrix_display": "Upper triangle only; the underlying pairwise metrics are symmetric.",
        "uncertainty_definition": "Point estimates shown; intervals are reported in the appendix table.",
    }
    metadata_path = output_dir / "figure_exp2_pairwise_appendix_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}


def make_delay_composition_figure(
    candidates: pd.DataFrame,
    output_dir: str | Path,
    config: dict[str, Any],
    *,
    run_metadata: dict[str, Any],
) -> dict[str, Any]:
    set_publication_style(config)
    output_dir = Path(output_dir)
    bins = [-np.inf, 1 / 24, 6 / 24, 1, 7, 30]
    labels = ["≤1 h", "1–6 h", "6–24 h", "1–7 d", "7–30 d"]
    categories = pd.cut(
        candidates["source_lag_days"], bins=bins, labels=labels, include_lowest=True, right=True
    )
    summary = categories.value_counts(sort=False).rename_axis("delay_bin").reset_index(name="source_event_count")
    summary["source_event_share"] = summary["source_event_count"] / summary["source_event_count"].sum()
    source_path = output_dir / "figure_exp2_delay_appendix_data.csv"
    summary.to_csv(source_path, index=False)

    fig, ax = plt.subplots(figsize=(4.9, 2.6))
    y = np.arange(len(summary))[::-1]
    ax.barh(y, summary["source_event_share"])
    ax.set_yticks(y, summary["delay_bin"])
    ax.set_xlim(0.0, max(1.0, float(summary["source_event_share"].max()) * 1.15))
    ax.set_xlabel("Share of eligible source events")
    for y_value, row in zip(y, summary.itertuples(index=False), strict=True):
        ax.text(
            row.source_event_share,
            y_value,
            f" {row.source_event_share:.1%} ({row.source_event_count:,})",
            va="center",
            fontsize=float(config["plots"]["annotation_font_size"]),
        )
    ax.grid(axis="x", alpha=0.25, linewidth=0.6)
    base = output_dir / "figure_exp2_delay_appendix"
    files = save_figure(fig, base, config)
    plt.close(fig)
    metadata = {
        **run_metadata,
        "figure_id": "figure_exp2_delay_appendix",
        "source_data": source_path.name,
        "source_data_sha256": sha256(source_path),
        "figure_files": {path.name: sha256(path) for path in files},
    }
    metadata_path = output_dir / "figure_exp2_delay_appendix_metadata.json"
    write_json(metadata, metadata_path)
    return {"figure_files": files, "source_data": source_path, "metadata": metadata_path}
