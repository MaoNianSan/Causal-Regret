"""History mean control and history-fitted Ridge proxy route."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import AuditDesign
from config import DEFAULT_CONFIG, ExperimentConfig
from utilities import save_frame, save_json


@dataclass(frozen=True)
class FittedRoutes:
    history_scores: np.ndarray
    ridge_beta: np.ndarray
    route_scores: pd.DataFrame
    feature_names: tuple[str, ...]


def _history_mean_scores(
    history: pd.DataFrame,
    design: AuditDesign,
    cfg: ExperimentConfig,
) -> np.ndarray:
    actions = design.candidate_actions
    action_index = {action: index for index, action in enumerate(actions)}
    valid = history[history["is_target_eligible"] & history["action_id"].isin(actions)].copy()
    action_stats = valid.groupby("action_id").agg(
        target_sum=("future_engagement_target_6h", "sum"),
        target_count=("future_engagement_target_6h", "count"),
    )
    global_mean = float(valid["future_engagement_target_6h"].mean())
    action_mean = np.full(len(actions), global_mean, dtype=float)
    for action, record in action_stats.iterrows():
        action_mean[action_index[str(action)]] = float(record.target_sum) / float(record.target_count)

    scores = np.zeros((design.user_group_count, len(actions)), dtype=float)
    group_stats = valid.groupby(["user_group_id", "action_id"]).agg(
        target_sum=("future_engagement_target_6h", "sum"),
        target_count=("future_engagement_target_6h", "count"),
    )
    for group_id in range(design.user_group_count):
        for action, index in action_index.items():
            if (group_id, action) not in group_stats.index:
                scores[group_id, index] = action_mean[index]
                continue
            record = group_stats.loc[(group_id, action)]
            scores[group_id, index] = (
                float(record.target_sum) + cfg.history_prior_count * action_mean[index]
            ) / (float(record.target_count) + cfg.history_prior_count)
    return scores


def _daily_cells(frame: pd.DataFrame, actions: tuple[str, ...], value: str) -> pd.DataFrame:
    valid = frame[frame["action_id"].isin(actions)].copy()
    if value == "proxy":
        return (
            valid.groupby(["calendar_day", "user_group_id", "action_id"], observed=True)
            .agg(proxy_sum=("short_term_proxy", "sum"), proxy_count=("short_term_proxy", "size"))
            .reset_index()
        )
    valid = valid[valid["is_target_eligible"]]
    table = (
        valid.groupby(["calendar_day", "user_group_id", "action_id"], observed=True)
        .agg(
            target_sum=("future_engagement_target_6h", "sum"),
            target_count=("future_engagement_target_6h", "count"),
        )
        .reset_index()
    )
    table["target_mean"] = table["target_sum"] / table["target_count"]
    return table


def _feature_row(
    *,
    day: str,
    group_id: int,
    action: str,
    action_rank: int,
    last_sum: float,
    last_count: float,
) -> dict[str, object]:
    return {
        "calendar_day": day,
        "user_group_id": group_id,
        "action_id": action,
        "action_rank": action_rank,
        "lag_proxy_mean": last_sum / last_count if last_count > 0 else 0.0,
        "lag_proxy_count": last_count,
        "lag_proxy_missing": float(last_count <= 0),
    }


def _make_features(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    design: AuditDesign,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    actions = design.candidate_actions
    history_days = sorted(history["calendar_day"].unique().tolist())
    evaluation_days = sorted(evaluation["calendar_day"].unique().tolist())
    history_proxy = _daily_cells(history, actions, "proxy")
    evaluation_proxy = _daily_cells(evaluation, actions, "proxy")
    history_target = _daily_cells(history, actions, "target")
    hist_proxy_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (float(row.proxy_sum), float(row.proxy_count))
        for row in history_proxy.itertuples()
    }
    eval_proxy_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (float(row.proxy_sum), float(row.proxy_count))
        for row in evaluation_proxy.itertuples()
    }
    target_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (float(row.target_mean), float(row.target_count))
        for row in history_target.itertuples()
    }

    training_rows: list[dict[str, object]] = []
    scoring_rows: list[dict[str, object]] = []
    for group_id in range(design.user_group_count):
        for action_rank, action in enumerate(actions):
            last_sum = 0.0
            last_count = 0.0
            for day in history_days:
                row = _feature_row(
                    day=day,
                    group_id=group_id,
                    action=action,
                    action_rank=action_rank,
                    last_sum=last_sum,
                    last_count=last_count,
                )
                target = target_map.get((day, group_id, action))
                if target is not None:
                    row.update({"target_mean": target[0], "target_count": target[1]})
                    training_rows.append(row)
                current_sum, current_count = hist_proxy_map.get((day, group_id, action), (0.0, 0.0))
                if current_count > 0:
                    last_sum, last_count = current_sum, current_count
            for day in evaluation_days:
                scoring_rows.append(
                    _feature_row(
                        day=day,
                        group_id=group_id,
                        action=action,
                        action_rank=action_rank,
                        last_sum=last_sum,
                        last_count=last_count,
                    )
                )
                current_sum, current_count = eval_proxy_map.get((day, group_id, action), (0.0, 0.0))
                if current_count > 0:
                    last_sum, last_count = current_sum, current_count
    return pd.DataFrame(training_rows), pd.DataFrame(scoring_rows)


def _design_matrix(frame: pd.DataFrame, action_count: int) -> tuple[np.ndarray, tuple[str, ...]]:
    one_hot = np.zeros((len(frame), action_count), dtype=float)
    ranks = frame["action_rank"].to_numpy(int)
    one_hot[np.arange(len(frame)), ranks] = 1.0
    numeric = np.column_stack(
        [
            frame["lag_proxy_mean"].to_numpy(float),
            np.log1p(frame["lag_proxy_count"].to_numpy(float)),
            frame["lag_proxy_missing"].to_numpy(float),
        ]
    )
    matrix = np.column_stack([np.ones(len(frame)), one_hot, numeric])
    names = (
        "intercept",
        *tuple(f"action_indicator_{index:02d}" for index in range(action_count)),
        "lag_proxy_mean",
        "log1p_lag_proxy_count",
        "lag_proxy_missing",
    )
    return matrix, names


def fit_proxy_routes(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    design: AuditDesign,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> FittedRoutes:
    actions = design.candidate_actions
    history_scores = _history_mean_scores(history, design, cfg)
    training, scoring = _make_features(history, evaluation, design)
    if training.empty or scoring.empty:
        raise RuntimeError("Ridge feature construction produced no rows.")
    x_train, feature_names = _design_matrix(training, len(actions))
    y_train = training["target_mean"].to_numpy(float)
    weights = np.sqrt(training["target_count"].to_numpy(float).clip(min=1.0))
    xw = x_train * weights[:, None]
    yw = y_train * weights
    penalty = np.eye(x_train.shape[1]) * cfg.ridge_alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(xw.T @ xw + penalty, xw.T @ yw)
    x_score, _ = _design_matrix(scoring, len(actions))
    scoring["ridge_proxy_score"] = x_score @ beta
    scoring["history_mean_score"] = [
        history_scores[int(group_id), int(action_rank)]
        for group_id, action_rank in zip(scoring["user_group_id"], scoring["action_rank"])
    ]

    long_rows: list[pd.DataFrame] = []
    for route_id, score_column in (
        ("history_mean_control", "history_mean_score"),
        ("ridge_proxy", "ridge_proxy_score"),
    ):
        route = scoring[["calendar_day", "user_group_id", "action_id", score_column]].copy()
        route = route.rename(columns={score_column: "route_score"})
        route["route_id"] = route_id
        route["route_role"] = "control" if route_id == "history_mean_control" else "primary_proxy"
        route["is_deployable"] = True
        route["uses_future_outcome"] = False
        route["uses_source_identity"] = False
        long_rows.append(route)
    route_scores = pd.concat(long_rows, ignore_index=True)
    coefficients = pd.DataFrame({"feature_name": feature_names, "coefficient": beta})
    save_frame(training, output_dir / "derived" / "exp3_ridge_training_cells.parquet")
    save_frame(scoring, output_dir / "derived" / "exp3_ridge_scoring_cells.parquet")
    save_frame(route_scores, output_dir / "derived" / "exp3_route_scores_fixed.parquet")
    save_frame(coefficients, output_dir / "tables" / "exp3_ridge_coefficients.csv")
    save_json(
        {
            "model_id": "ridge_proxy",
            "model_family": "ridge_linear_readout",
            "ridge_alpha": cfg.ridge_alpha,
            "training_split": "history_only",
            "evaluation_model_selection_used": False,
            "feature_contract": "action_one_hot_plus_previous_completed_bin_proxy",
            "ewma_features_used": False,
            "feature_names": list(feature_names),
            "training_cell_count": int(len(training)),
            "scoring_cell_count": int(len(scoring)),
        },
        output_dir / "metadata" / "exp3_model_manifest.json",
    )
    return FittedRoutes(history_scores, beta, route_scores, feature_names)
