"""Feature construction for the history-fitted Ridge route."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from audit_design import AuditDesign


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


def make_feature_frames(
    history: pd.DataFrame,
    evaluation: pd.DataFrame,
    design: AuditDesign,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build history training cells and evaluation scoring cells without fitting."""
    actions = design.candidate_actions
    history_days = sorted(history["calendar_day"].astype(str).unique().tolist())
    evaluation_days = sorted(evaluation["calendar_day"].astype(str).unique().tolist())
    history_proxy = _daily_cells(history, actions, "proxy")
    evaluation_proxy = _daily_cells(evaluation, actions, "proxy")
    history_target = _daily_cells(history, actions, "target")
    history_support = (
        history[
            history["is_target_eligible"]
            & history["action_id"].isin(actions)
        ]
        .groupby(
            ["calendar_day", "user_group_id", "reference_fold_id", "action_id"],
            observed=True,
        )
        .size()
        .rename("target_count")
        .reset_index()
    )
    reference_fold_count = int(design.design_freeze.get("reference_fold_count", 2))
    support_map: dict[tuple[str, int, str], bool] = {}
    for (day, group_id, action), counts in history_support.groupby(
        ["calendar_day", "user_group_id", "action_id"], observed=True
    ):
        by_fold = counts.set_index("reference_fold_id")["target_count"]
        support_map[(str(day), int(group_id), str(action))] = all(
            float(by_fold.get(fold_id, 0.0)) >= design.support_min_events_per_fold
            for fold_id in range(reference_fold_count)
        )
    hist_proxy_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (
            float(row.proxy_sum),
            float(row.proxy_count),
        )
        for row in history_proxy.itertuples()
    }
    eval_proxy_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (
            float(row.proxy_sum),
            float(row.proxy_count),
        )
        for row in evaluation_proxy.itertuples()
    }
    target_map = {
        (str(row.calendar_day), int(row.user_group_id), str(row.action_id)): (
            float(row.target_mean),
            float(row.target_count),
        )
        for row in history_target.itertuples()
    }

    training_rows: list[dict[str, object]] = []
    scoring_rows: list[dict[str, object]] = []
    for group_id in range(design.user_group_count):
        for action_rank, action in enumerate(actions):
            last_sum = 0.0
            last_count = 0.0
            for day in history_days:
                row = _feature_row(day, group_id, action, action_rank, last_sum, last_count)
                target = target_map.get((day, group_id, action))
                if target is not None:
                    row.update(
                        {
                            "target_mean": target[0],
                            "target_count": target[1],
                            "is_common_supported": support_map.get(
                                (day, group_id, action), False
                            ),
                        }
                    )
                    training_rows.append(row)
                current = hist_proxy_map.get((day, group_id, action), (0.0, 0.0))
                if current[1] > 0:
                    last_sum, last_count = current
            for day in evaluation_days:
                scoring_rows.append(
                    _feature_row(day, group_id, action, action_rank, last_sum, last_count)
                )
                current = eval_proxy_map.get((day, group_id, action), (0.0, 0.0))
                if current[1] > 0:
                    last_sum, last_count = current
    return pd.DataFrame(training_rows), pd.DataFrame(scoring_rows)


def design_matrix(frame: pd.DataFrame, action_count: int) -> tuple[np.ndarray, tuple[str, ...]]:
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


def feature_schema_hash(feature_names: tuple[str, ...]) -> str:
    return hashlib.sha256("\n".join(feature_names).encode("utf-8")).hexdigest()


def history_design_hash(training: pd.DataFrame) -> str:
    columns = [
        "calendar_day",
        "user_group_id",
        "action_id",
        "action_rank",
        "lag_proxy_mean",
        "lag_proxy_count",
        "lag_proxy_missing",
        "target_mean",
        "target_count",
        "is_common_supported",
    ]
    ordered = training[columns].sort_values(columns[:4]).reset_index(drop=True)
    hashed = pd.util.hash_pandas_object(ordered, index=False).to_numpy(np.uint64)
    return hashlib.sha256(hashed.tobytes()).hexdigest()


# One-release compatibility for existing callers and tests.
_make_features = make_feature_frames
_design_matrix = design_matrix
