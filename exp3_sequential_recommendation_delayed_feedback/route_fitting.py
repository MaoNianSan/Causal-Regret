"""Final Historical mean and Ridge fitting after design and alpha freeze."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import AuditDesign
from config import DEFAULT_CONFIG, ExperimentConfig
from design_contract import route_metadata
from ridge_features import design_matrix, make_feature_frames
from ridge_selection import fit_ridge_coefficients, persist_ridge_selection, select_ridge_alpha
from utilities import save_frame, save_json


@dataclass(frozen=True)
class FittedRoutes:
    history_scores: np.ndarray
    ridge_beta: np.ndarray
    route_scores: pd.DataFrame
    feature_names: tuple[str, ...]
    selected_alpha: float


def history_mean_scores(
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


def fit_routes(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    design: AuditDesign,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> FittedRoutes:
    actions = design.candidate_actions
    history_scores = history_mean_scores(history, design, cfg)
    training, scoring = make_feature_frames(history, evaluation, design)
    if training.empty or scoring.empty:
        raise RuntimeError("Ridge feature construction produced no rows.")
    selection = select_ridge_alpha(training, len(actions), cfg)
    persist_ridge_selection(selection, output_dir)
    beta, feature_names = fit_ridge_coefficients(training, len(actions), selection.selected_alpha)
    x_score, _ = design_matrix(scoring, len(actions))
    scoring["ridge_proxy_score"] = x_score @ beta
    scoring["history_mean_score"] = [
        history_scores[int(group_id), int(action_rank)]
        for group_id, action_rank in zip(scoring["user_group_id"], scoring["action_rank"])
    ]
    route_frames = []
    for route_id, score_column in (
        ("history_mean_control", "history_mean_score"),
        ("ridge_proxy", "ridge_proxy_score"),
    ):
        route = scoring[["calendar_day", "user_group_id", "action_id", score_column]].copy()
        route = route.rename(columns={score_column: "route_score"})
        for key, value in route_metadata(route_id).items():
            route[key] = value
        route_frames.append(route)
    route_scores = pd.concat(route_frames, ignore_index=True)
    coefficients = pd.DataFrame({"feature_name": feature_names, "coefficient": beta})
    save_frame(training, output_dir / "derived" / "exp3_ridge_training_cells.parquet")
    save_frame(scoring, output_dir / "derived" / "exp3_ridge_scoring_cells.parquet")
    save_frame(route_scores, output_dir / "derived" / "exp3_route_scores_fixed.parquet")
    save_frame(coefficients, output_dir / "tables" / "exp3_ridge_coefficients.csv")
    save_json(
        {
            "model_id": "ridge_proxy",
            "model_family": "ridge_linear_readout",
            "selected_alpha": selection.selected_alpha,
            "selected_alpha_is_run_artifact": True,
            "selection_scope": "history_only",
            "evaluation_model_selection_used": False,
            "feature_contract": "action_one_hot_plus_previous_completed_bin_proxy",
            "ewma_features_used": False,
            "feature_names": list(feature_names),
            "feature_schema_hash": selection.manifest["feature_schema_hash"],
            "history_design_hash": selection.manifest["history_design_hash"],
            "training_cell_count": int(len(training)),
            "scoring_cell_count": int(len(scoring)),
        },
        output_dir / "metadata" / "exp3_model_manifest.json",
    )
    return FittedRoutes(history_scores, beta, route_scores, feature_names, selection.selected_alpha)


_history_mean_scores = history_mean_scores
