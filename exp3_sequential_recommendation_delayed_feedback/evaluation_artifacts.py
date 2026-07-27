"""Immutable evaluation-array types and frozen point-estimate I/O."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from route_diagnostics import write_route_selection_diagnostics
from utilities import read_frame, save_frame


@dataclass(frozen=True)
class EvaluationArrays:
    user_ids: tuple[str, ...]
    calendar_days: tuple[str, ...]
    candidate_actions: tuple[str, ...]
    user_group_ids: np.ndarray
    reference_fold_ids: np.ndarray
    source_target_sum: np.ndarray  # user x day x action
    source_target_count: np.ndarray
    arrival_target_sum: np.ndarray  # cumulative before each decision clock
    arrival_target_count: np.ndarray
    fixed_route_scores: dict[str, np.ndarray]  # route -> day x group x action
    history_scores: np.ndarray  # group x action


@dataclass
class MetricResult:
    route_metrics: pd.DataFrame
    support_metrics: pd.DataFrame
    support_cells: pd.DataFrame
    support_margins: pd.DataFrame
    audit_unit_metrics: pd.DataFrame
    action_cell_metrics: pd.DataFrame
    decile_calibration: pd.DataFrame


def save_evaluation_arrays(arrays: EvaluationArrays, output_dir: Path) -> Path:
    """Persist immutable bootstrap inputs for interruption-safe resume."""
    path = output_dir / "derived" / "exp3_evaluation_arrays.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        user_ids=np.asarray(arrays.user_ids, dtype=str),
        calendar_days=np.asarray(arrays.calendar_days, dtype=str),
        candidate_actions=np.asarray(arrays.candidate_actions, dtype=str),
        user_group_ids=arrays.user_group_ids,
        reference_fold_ids=arrays.reference_fold_ids,
        source_target_sum=arrays.source_target_sum,
        source_target_count=arrays.source_target_count,
        arrival_target_sum=arrays.arrival_target_sum,
        arrival_target_count=arrays.arrival_target_count,
        history_scores=arrays.history_scores,
        fixed_history_mean_control=arrays.fixed_route_scores["history_mean_control"],
        fixed_ridge_proxy=arrays.fixed_route_scores["ridge_proxy"],
    )
    return path


def load_evaluation_arrays(output_dir: Path) -> EvaluationArrays:
    path = output_dir / "derived" / "exp3_evaluation_arrays.npz"
    if not path.exists():
        raise FileNotFoundError(f"Bootstrap resume requires persisted evaluation arrays: {path}")
    with np.load(path, allow_pickle=False) as data:
        return EvaluationArrays(
            user_ids=tuple(data["user_ids"].astype(str).tolist()),
            calendar_days=tuple(data["calendar_days"].astype(str).tolist()),
            candidate_actions=tuple(data["candidate_actions"].astype(str).tolist()),
            user_group_ids=data["user_group_ids"].copy(),
            reference_fold_ids=data["reference_fold_ids"].copy(),
            source_target_sum=data["source_target_sum"].copy(),
            source_target_count=data["source_target_count"].copy(),
            arrival_target_sum=data["arrival_target_sum"].copy(),
            arrival_target_count=data["arrival_target_count"].copy(),
            fixed_route_scores={
                "history_mean_control": data["fixed_history_mean_control"].copy(),
                "ridge_proxy": data["fixed_ridge_proxy"].copy(),
            },
            history_scores=data["history_scores"].copy(),
        )


def load_point_estimates(output_dir: Path) -> MetricResult:
    """Load the frozen point estimand required by a resumed bootstrap."""
    return MetricResult(
        route_metrics=read_frame(output_dir / "derived" / "exp3_route_metrics_point.csv"),
        support_metrics=read_frame(output_dir / "derived" / "exp3_support_metrics_point.csv"),
        support_cells=read_frame(output_dir / "derived" / "exp3_evaluation_support_cells.csv"),
        support_margins=read_frame(output_dir / "derived" / "exp3_evaluation_support_margins.csv"),
        audit_unit_metrics=read_frame(output_dir / "derived" / "exp3_audit_unit_metrics.parquet"),
        action_cell_metrics=read_frame(output_dir / "derived" / "exp3_action_cell_metrics.parquet"),
        decile_calibration=read_frame(output_dir / "derived" / "exp3_decile_calibration_point.csv"),
    )


def write_point_estimates(result: MetricResult, output_dir: Path) -> None:
    save_frame(result.route_metrics, output_dir / "derived" / "exp3_route_metrics_point.csv")
    save_frame(result.support_metrics, output_dir / "derived" / "exp3_support_metrics_point.csv")
    save_frame(result.support_cells, output_dir / "derived" / "exp3_evaluation_support_cells.csv")
    save_frame(result.support_margins, output_dir / "derived" / "exp3_evaluation_support_margins.csv")
    save_frame(result.audit_unit_metrics, output_dir / "derived" / "exp3_audit_unit_metrics.parquet")
    save_frame(result.action_cell_metrics, output_dir / "derived" / "exp3_action_cell_metrics.parquet")
    save_frame(result.decile_calibration, output_dir / "derived" / "exp3_decile_calibration_point.csv")
    write_route_selection_diagnostics(result.audit_unit_metrics, output_dir)
