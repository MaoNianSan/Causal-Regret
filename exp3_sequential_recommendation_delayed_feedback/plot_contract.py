"""Frozen-table loading and shared drawing primitives for the Exp3 main figure."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from design_contract import ROUTE_SPECS


ROUTE_ORDER = ["arrival_carrier", "history_mean_control", "ridge_proxy"]
DISPLAY = {route_id: spec.route_display_name for route_id, spec in ROUTE_SPECS.items()}
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


@dataclass(frozen=True)
class MainFigureInputs:
    primary: pd.DataFrame
    paired: pd.DataFrame
    support: pd.Series
    action_coverage: pd.DataFrame
    registry: pd.DataFrame
    manifest: dict[str, object]
    selection: dict[str, object]
    source_paths: tuple[Path, ...]


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def validated_range(low: float, high: float) -> tuple[float, float]:
    values = np.asarray([low, high], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Non-finite sensitivity range: {values.tolist()}")
    if low > high:
        raise ValueError(f"Invalid sensitivity range ordering: lower={low}, upper={high}")
    return float(low), float(high)


def evaluation_exposure_scope(table: pd.DataFrame, scope: str) -> tuple[int, float]:
    selected = table[(table["split_id"] == "evaluation") & (table["design_scope"] == scope)]
    if len(selected) != 1:
        raise RuntimeError(f"Expected exactly one evaluation exposure-mass row for {scope}")
    return (
        int(selected.iloc[0]["selected_action_count"]),
        float(selected.iloc[0]["selected_action_exposure_mass_coverage"]),
    )


def load_main_figure_inputs(output_dir: Path) -> MainFigureInputs:
    paths = (
        output_dir / "tables" / "exp3_primary_route_results.csv",
        output_dir / "tables" / "exp3_paired_ranking_contrast.csv",
        output_dir / "tables" / "exp3_support_coverage.csv",
        output_dir / "tables" / "exp3_action_space_coverage.csv",
        output_dir / "tables" / "exp3_metric_registry.csv",
    )
    primary = read_table(paths[0])
    missing = [route for route in ROUTE_ORDER if route not in set(primary["route_id"])]
    if missing:
        raise RuntimeError(f"Main figure is missing routes: {missing}")
    primary = primary.set_index("route_id").loc[ROUTE_ORDER].reset_index()
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    selection_path = output_dir / "metadata" / "exp3_ridge_selection_manifest.json"
    return MainFigureInputs(
        primary=primary,
        paired=read_table(paths[1]),
        support=read_table(paths[2]).iloc[0],
        action_coverage=read_table(paths[3]),
        registry=read_table(paths[4]),
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
        selection=json.loads(selection_path.read_text(encoding="utf-8")),
        source_paths=paths,
    )


def draw_route_metric(
    ax: plt.Axes,
    table: pd.DataFrame,
    metric_id: str,
    xlabel: str,
    *,
    show_labels: bool,
    include_zero: bool = False,
) -> list[dict[str, object]]:
    rows = []
    values = []
    y_positions = np.arange(len(ROUTE_ORDER), dtype=float)
    for y, row in zip(y_positions, table.itertuples()):
        route_id = str(row.route_id)
        point = float(getattr(row, metric_id))
        median = float(getattr(row, f"{metric_id}_resampling_median"))
        low, high = validated_range(
            float(getattr(row, f"{metric_id}_sensitivity_lower")),
            float(getattr(row, f"{metric_id}_sensitivity_upper")),
        )
        color = COLORS[route_id]
        ax.hlines(y, low, high, color=color, linewidth=1.5, alpha=0.65)
        ax.plot(median, y, marker=MARKERS[route_id], markerfacecolor="white", markeredgecolor=color)
        ax.plot(point, y, marker=MARKERS[route_id], color=color)
        values.extend([point, median, low, high])
        rows.append(
            {
                "route_id": route_id,
                "metric_id": metric_id,
                "full_sample_estimate": point,
                "resampling_median": median,
                "sensitivity_lower": low,
                "sensitivity_upper": high,
            }
        )
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    lower = float(finite.min()) if finite.size else 0.0
    upper = float(finite.max()) if finite.size else 1.0
    if include_zero:
        lower, upper = min(0.0, lower), max(0.0, upper)
        ax.axvline(0.0, color="0.45", linestyle="--", linewidth=0.8)
    span = max(upper - lower, 1e-6)
    ax.set_xlim(lower - 0.06 * span, upper + 0.10 * span)
    ax.set_yticks(y_positions, [DISPLAY[route] for route in ROUTE_ORDER] if show_labels else [])
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.18, linewidth=0.6)
    return rows


_validated_range = validated_range
_evaluation_exposure_scope = evaluation_exposure_scope
