"""History-only rolling temporal selection for the Ridge penalty."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig
from ridge_features import design_matrix, feature_schema_hash, history_design_hash
from utilities import save_frame, save_json


@dataclass(frozen=True)
class RidgeSelection:
    selected_alpha: float
    cv_results: pd.DataFrame
    manifest: dict[str, object]


def fit_ridge_coefficients(
    training: pd.DataFrame,
    action_count: int,
    alpha: float,
) -> tuple[np.ndarray, tuple[str, ...]]:
    x_train, feature_names = design_matrix(training, action_count)
    y_train = training["target_mean"].to_numpy(float)
    weights = np.sqrt(training["target_count"].to_numpy(float).clip(min=1.0))
    xw = x_train * weights[:, None]
    yw = y_train * weights
    penalty = np.eye(x_train.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(xw.T @ xw + penalty, xw.T @ yw)
    return beta, feature_names


def rolling_origin_splits(
    training: pd.DataFrame,
    min_train_days: int,
) -> list[tuple[tuple[str, ...], str]]:
    days = tuple(sorted(training["calendar_day"].astype(str).unique().tolist()))
    return [(days[:index], days[index]) for index in range(min_train_days, len(days))]


def choose_alpha(
    aggregate: pd.DataFrame,
    tie_tolerance: float,
    tie_break: str,
) -> tuple[float, bool]:
    if aggregate.empty:
        raise RuntimeError("Ridge history-only validation produced no alpha summaries.")
    best = float(aggregate["macro_supported_cell_mae_mean"].min())
    tied = aggregate[
        aggregate["macro_supported_cell_mae_mean"] <= best + float(tie_tolerance)
    ]
    if tie_break != "larger_alpha":
        raise ValueError(f"Unsupported Ridge tie-break rule: {tie_break}")
    return float(tied["alpha"].max()), len(tied) > 1


def select_ridge_alpha(
    training: pd.DataFrame,
    action_count: int,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
    *,
    evaluation_frame: pd.DataFrame | None = None,
) -> RidgeSelection:
    if evaluation_frame is not None:
        raise ValueError("Ridge selector rejects evaluation data; selection_scope=history_only.")
    if "is_common_supported" not in training.columns:
        raise ValueError(
            "Ridge history validation requires an explicit is_common_supported column."
        )
    splits = rolling_origin_splits(training, cfg.ridge_cv_min_train_days)
    if not splits:
        raise RuntimeError(
            "Ridge history-only validation requires more history days than "
            f"ridge_cv_min_train_days={cfg.ridge_cv_min_train_days}."
        )
    rows: list[dict[str, object]] = []
    for origin_id, (train_days, validation_day) in enumerate(splits):
        train = training[training["calendar_day"].astype(str).isin(train_days)]
        validation = training[
            (training["calendar_day"].astype(str) == validation_day)
            & training["is_common_supported"].astype(bool)
        ]
        if train.empty or validation.empty:
            continue
        x_valid, _ = design_matrix(validation, action_count)
        y_valid = validation["target_mean"].to_numpy(float)
        counts = validation["target_count"].to_numpy(float).clip(min=1.0)
        for alpha in cfg.ridge_alpha_grid:
            beta, _ = fit_ridge_coefficients(train, action_count, alpha)
            errors = np.abs(x_valid @ beta - y_valid)
            rows.append(
                {
                    "alpha": float(alpha),
                    "validation_origin": origin_id,
                    "train_start": train_days[0],
                    "train_end": train_days[-1],
                    "validation_date": validation_day,
                    "supported_cell_count": int(len(validation)),
                    "macro_supported_cell_mae": float(errors.mean()),
                    "exposure_weighted_supported_cell_mae": float(np.average(errors, weights=counts)),
                    "evaluation_data_used": False,
                }
            )
    results = pd.DataFrame(rows)
    if results.empty:
        raise RuntimeError("Ridge history-only validation produced no supported validation cells.")
    aggregate = (
        results.groupby("alpha", as_index=False)
        .agg(
            macro_supported_cell_mae_mean=("macro_supported_cell_mae", "mean"),
            macro_supported_cell_mae_std=("macro_supported_cell_mae", "std"),
            exposure_weighted_supported_cell_mae_mean=(
                "exposure_weighted_supported_cell_mae",
                "mean",
            ),
            origin_count=("validation_origin", "nunique"),
        )
    )
    selected_alpha, tie_applied = choose_alpha(
        aggregate,
        cfg.ridge_cv_tie_tolerance,
        cfg.ridge_cv_tie_break,
    )
    results = results.merge(aggregate, on="alpha", how="left")
    results["selected"] = np.isclose(results["alpha"], selected_alpha)
    results["tie_break_applied"] = tie_applied
    _, feature_names = design_matrix(training.iloc[:1], action_count)
    manifest = {
        "selection_scope": "history_only",
        "evaluation_data_used": False,
        "alpha_grid": [float(value) for value in cfg.ridge_alpha_grid],
        "selected_alpha": selected_alpha,
        "selection_metric": cfg.ridge_cv_metric,
        "tie_tolerance": cfg.ridge_cv_tie_tolerance,
        "tie_break_rule": cfg.ridge_cv_tie_break,
        "tie_break_applied": tie_applied,
        "origin_count": int(results["validation_origin"].nunique()),
        "validation_support_scope": "history_common_supported_action_cells",
        "feature_schema_hash": feature_schema_hash(feature_names),
        "history_design_hash": history_design_hash(training),
    }
    return RidgeSelection(selected_alpha, results, manifest)


def persist_ridge_selection(selection: RidgeSelection, output_dir: Path) -> None:
    save_frame(selection.cv_results, output_dir / "tables" / "exp3_ridge_history_cv.csv")
    save_json(selection.manifest, output_dir / "metadata" / "exp3_ridge_selection_manifest.json")
