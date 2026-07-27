"""Construction of immutable cross-fitted evaluation arrays."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from audit_design import AuditDesign
from config import DEFAULT_CONFIG, ExperimentConfig
from evaluation_artifacts import EvaluationArrays, save_evaluation_arrays
from proxy_routes import FittedRoutes
from utilities import save_frame


def build_evaluation_arrays(
    evaluation: pd.DataFrame,
    design: AuditDesign,
    fitted: FittedRoutes,
    output_dir: Path,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> EvaluationArrays:
    actions = design.candidate_actions
    action_index = {action: index for index, action in enumerate(actions)}
    users = sorted(evaluation[cfg.user_col].astype(str).unique().tolist())
    user_index = {user: index for index, user in enumerate(users)}
    days = sorted(evaluation["calendar_day"].astype(str).unique().tolist())
    day_index = {day: index for index, day in enumerate(days)}
    day_starts = np.array(
        [
            int(pd.Timestamp(day, tz=cfg.timezone_name).timestamp() * 1000)
            for day in days
        ],
        dtype=np.int64,
    )
    shape = (len(users), len(days), len(actions))
    source_sum = np.zeros(shape, dtype=np.float64)
    source_count = np.zeros(shape, dtype=np.float64)
    arrival_sum = np.zeros(shape, dtype=np.float64)
    arrival_count = np.zeros(shape, dtype=np.float64)

    eligible = evaluation[
        evaluation["is_target_eligible"]
        & evaluation["action_id"].isin(actions)
    ].copy()
    for row in eligible.itertuples():
        u = user_index[str(getattr(row, cfg.user_col))]
        d = day_index[str(row.calendar_day)]
        a = action_index[str(row.action_id)]
        source_sum[u, d, a] += float(row.future_engagement_target_6h)
        source_count[u, d, a] += 1.0

    arrival_events = evaluation[
        evaluation["is_target_eligible"]
        & evaluation["carrier_status"].eq("matched")
        & evaluation["carrier_action_id"].isin(actions)
    ].copy()
    # Build a sparse list per user, then cumulative totals at each decision clock.
    for user, group in arrival_events.groupby(cfg.user_col, sort=False):
        u = user_index[str(user)]
        group = group.sort_values("feedback_arrival_time", kind="stable")
        arrival_times = group["feedback_arrival_time"].to_numpy(float)
        event_actions = group["carrier_action_id"].map(action_index).to_numpy(int)
        event_values = group["future_engagement_target_6h"].to_numpy(float)
        running_sum = np.zeros(len(actions), dtype=float)
        running_count = np.zeros(len(actions), dtype=float)
        position = 0
        for d, clock in enumerate(day_starts):
            while position < len(group) and arrival_times[position] < clock:
                action = event_actions[position]
                running_sum[action] += event_values[position]
                running_count[action] += 1.0
                position += 1
            arrival_sum[u, d] = running_sum
            arrival_count[u, d] = running_count

    user_table = evaluation[[cfg.user_col, "user_group_id", "reference_fold_id"]].drop_duplicates(cfg.user_col)
    user_table = user_table.set_index(cfg.user_col).reindex(users)
    group_ids = user_table["user_group_id"].to_numpy(int)
    fold_ids = user_table["reference_fold_id"].to_numpy(int)

    fixed_scores: dict[str, np.ndarray] = {}
    for route_id in ("history_mean_control", "ridge_proxy"):
        table = fitted.route_scores[fitted.route_scores["route_id"] == route_id]
        array = np.full((len(days), design.user_group_count, len(actions)), np.nan, dtype=float)
        for row in table.itertuples():
            if str(row.calendar_day) in day_index and str(row.action_id) in action_index:
                array[day_index[str(row.calendar_day)], int(row.user_group_id), action_index[str(row.action_id)]] = float(row.route_score)
        if not np.isfinite(array).all():
            raise RuntimeError(f"Fixed route score table is incomplete for {route_id}.")
        fixed_scores[route_id] = array

    arrays = EvaluationArrays(
        user_ids=tuple(users),
        calendar_days=tuple(days),
        candidate_actions=tuple(actions),
        user_group_ids=group_ids,
        reference_fold_ids=fold_ids,
        source_target_sum=source_sum,
        source_target_count=source_count,
        arrival_target_sum=arrival_sum,
        arrival_target_count=arrival_count,
        fixed_route_scores=fixed_scores,
        history_scores=fitted.history_scores,
    )
    save_frame(
        pd.DataFrame(
            {
                "user_id": users,
                "user_group_id": group_ids,
                "reference_fold_id": fold_ids,
            }
        ),
        output_dir / "processed" / "exp3_evaluation_user_index.csv",
    )
    save_evaluation_arrays(arrays, output_dir)
    return arrays

