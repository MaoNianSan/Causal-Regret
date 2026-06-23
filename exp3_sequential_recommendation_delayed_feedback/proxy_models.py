"""Chronologically separated ridge proxies for Exp3.

All main-period features are built from completed history and earlier main bins.
No aggregate statistic from future main bins is used as a fallback, imputation
constant, or score component.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig


@dataclass(frozen=True)
class RidgeProxyModel:
    """A ridge readout fitted on history-standard action-bin cells only."""

    name: str
    beta: np.ndarray
    action_count: int
    feature_names: list[str]
    alpha: float

    def predict(
        self,
        action_idx: np.ndarray,
        lag_mean: np.ndarray,
        lag_count: np.ndarray,
        ewma_mean: np.ndarray,
        ewma_count: np.ndarray,
    ) -> np.ndarray:
        design = make_design_matrix(
            self.name,
            action_idx,
            lag_mean,
            lag_count,
            ewma_mean,
            ewma_count,
            self.action_count,
        )
        return design @ self.beta


@dataclass(frozen=True)
class ProxyPriors:
    """Completed-history priors used to initialize main-period feature states."""

    proxy_sum: float
    proxy_count: float
    composite_sum: float
    composite_count: float
    ewma_mean: np.ndarray
    ewma_count: np.ndarray

    @property
    def proxy_mean(self) -> float:
        return self.proxy_sum / self.proxy_count if self.proxy_count > 0 else 0.0

    @property
    def composite_mean(self) -> float:
        return self.composite_sum / self.composite_count if self.composite_count > 0 else 0.0


def decision_bin(values: np.ndarray | pd.Series, width: int) -> np.ndarray:
    values_array = np.asarray(values, dtype=np.int64)
    return (values_array // int(width)) * int(width)


def action_proxy_cells(
    events: pd.DataFrame,
    actions: list[str],
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    mapping = {action: index for index, action in enumerate(actions)}
    out = events.copy()
    out["source_bin"] = decision_bin(out[cfg.time_col], cfg.sequential_bin_ms)
    out["action_idx"] = out["action_bucket"].astype(str).map(mapping).astype(int)
    return (
        out.groupby(["source_bin", "action_idx", "action_bucket"], dropna=False)
        .agg(
            proxy_count=("short_term_proxy", "size"),
            proxy_sum=("short_term_proxy", "sum"),
            composite_sum=("short_term_composite", "sum"),
        )
        .reset_index()
    )


def target_cells(
    events: pd.DataFrame,
    actions: list[str],
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    target_name = f"y_long_value_log_{cfg.primary_horizon}"
    valid = events[events[f"valid_for_{cfg.primary_horizon}"].eq(1)].copy()
    mapping = {action: index for index, action in enumerate(actions)}
    valid["source_bin"] = decision_bin(valid[cfg.time_col], cfg.sequential_bin_ms)
    valid["action_idx"] = valid["action_bucket"].astype(str).map(mapping).astype(int)
    cells = (
        valid.groupby(["source_bin", "action_idx", "action_bucket"], dropna=False)
        .agg(target_count=(target_name, "size"), target_sum=(target_name, "sum"))
        .reset_index()
    )
    cells["observed_target"] = cells["target_sum"] / cells["target_count"]
    return cells


def history_mean_static_scores(
    history_events: pd.DataFrame,
    actions: list[str],
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """Return a history-only per-action target mean.

    This is a deliberately static control: it uses no main-period short-term
    proxy, no main arrival message, and no main source label.  It isolates how
    much of any proxy-route performance can be attributed to stable action
    category differences already present in the history split.
    """
    cells = target_cells(history_events, actions, cfg)
    if cells.empty:
        return np.zeros(len(actions), dtype=float)
    total_sum = float(cells["target_sum"].sum())
    total_count = float(cells["target_count"].sum())
    fallback = total_sum / total_count if total_count > 0 else 0.0
    scores = np.full(len(actions), fallback, dtype=float)
    grouped = cells.groupby("action_idx", sort=False).agg(target_sum=("target_sum", "sum"), target_count=("target_count", "sum"))
    for action_idx, record in grouped.iterrows():
        if float(record.target_count) > 0:
            scores[int(action_idx)] = float(record.target_sum) / float(record.target_count)
    return scores


def _state_update(
    ewma_mean: np.ndarray,
    ewma_updates: np.ndarray,
    row: pd.DataFrame,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Update per-action EWMA using one *completed* source bin."""
    if row.empty:
        return ewma_mean, ewma_updates
    indices = row["action_idx"].to_numpy(int)
    counts = row["proxy_count"].to_numpy(float)
    means = np.divide(
        row["proxy_sum"].to_numpy(float),
        counts,
        out=np.zeros_like(counts),
        where=counts > 0,
    )
    for index, mean, count in zip(indices, means, counts):
        if count <= 0:
            continue
        if ewma_updates[index] <= 0:
            ewma_mean[index] = mean
        else:
            ewma_mean[index] = alpha * mean + (1.0 - alpha) * ewma_mean[index]
        ewma_updates[index] += 1.0
    return ewma_mean, ewma_updates


def _feature_state_by_bin(
    proxy_cells: pd.DataFrame,
    bins: np.ndarray,
    n_actions: int,
    cfg: ExperimentConfig,
    *,
    initial_ewma: tuple[np.ndarray, np.ndarray] | None = None,
    initial_proxy_totals: tuple[float, float] = (0.0, 0.0),
) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Return features available at the beginning of each decision bin.

    For bin ``b``, the state includes at most bin ``b - width``. The fallback
    mean is an expanding statistic from completed bins, initialized only from
    the completed history split when scoring main. This prevents the former
    full-main-period look-ahead through global proxy means.
    """
    by_bin = {int(bin_id): frame for bin_id, frame in proxy_cells.groupby("source_bin", sort=False)}
    if initial_ewma is None:
        ewma_mean = np.zeros(n_actions, dtype=float)
        ewma_updates = np.zeros(n_actions, dtype=float)
    else:
        ewma_mean = initial_ewma[0].astype(float, copy=True)
        ewma_updates = initial_ewma[1].astype(float, copy=True)

    completed_proxy_sum = float(initial_proxy_totals[0])
    completed_proxy_count = float(initial_proxy_totals[1])
    states: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    width = int(cfg.sequential_bin_ms)

    for bin_id in sorted(map(int, bins)):
        previous = by_bin.get(bin_id - width)
        if previous is not None and not previous.empty:
            ewma_mean, ewma_updates = _state_update(ewma_mean, ewma_updates, previous, cfg.ewma_alpha)
            completed_proxy_sum += float(previous["proxy_sum"].sum())
            completed_proxy_count += float(previous["proxy_count"].sum())

        fallback_mean = completed_proxy_sum / completed_proxy_count if completed_proxy_count > 0 else 0.0
        lag_mean = np.full(n_actions, fallback_mean, dtype=float)
        lag_count = np.zeros(n_actions, dtype=float)
        if previous is not None and not previous.empty:
            indices = previous["action_idx"].to_numpy(int)
            counts = previous["proxy_count"].to_numpy(float)
            sums = previous["proxy_sum"].to_numpy(float)
            lag_count[indices] = counts
            lag_mean[indices] = np.divide(
                sums,
                counts,
                out=np.full_like(sums, fallback_mean),
                where=counts > 0,
            )

        ewma_feature_mean = ewma_mean.copy()
        ewma_feature_mean[ewma_updates <= 0] = fallback_mean
        states[bin_id] = (
            lag_mean,
            lag_count,
            ewma_feature_mean,
            ewma_updates.copy(),
        )
    return states


def _final_ewma(
    proxy_cells: pd.DataFrame,
    n_actions: int,
    cfg: ExperimentConfig,
) -> tuple[np.ndarray, np.ndarray]:
    ewma_mean = np.zeros(n_actions, dtype=float)
    ewma_updates = np.zeros(n_actions, dtype=float)
    for _, frame in proxy_cells.sort_values("source_bin").groupby("source_bin", sort=True):
        ewma_mean, ewma_updates = _state_update(ewma_mean, ewma_updates, frame, cfg.ewma_alpha)
    return ewma_mean, ewma_updates


def _proxy_priors(
    history_proxy: pd.DataFrame,
    n_actions: int,
    cfg: ExperimentConfig,
) -> ProxyPriors:
    ewma_mean, ewma_updates = _final_ewma(history_proxy, n_actions, cfg)
    return ProxyPriors(
        proxy_sum=float(history_proxy["proxy_sum"].sum()),
        proxy_count=float(history_proxy["proxy_count"].sum()),
        composite_sum=float(history_proxy["composite_sum"].sum()),
        composite_count=float(history_proxy["proxy_count"].sum()),
        ewma_mean=ewma_mean,
        ewma_count=ewma_updates,
    )


def make_design_matrix(
    name: str,
    action_idx: np.ndarray,
    lag_mean: np.ndarray,
    lag_count: np.ndarray,
    ewma_mean: np.ndarray,
    ewma_count: np.ndarray,
    n_actions: int,
) -> np.ndarray:
    indices = np.asarray(action_idx, dtype=int)
    one_hot = np.zeros((len(indices), n_actions), dtype=float)
    one_hot[np.arange(len(indices)), np.clip(indices, 0, n_actions - 1)] = 1.0
    lag_mean = np.asarray(lag_mean, dtype=float)
    lag_count = np.log1p(np.asarray(lag_count, dtype=float))
    ewma_mean = np.asarray(ewma_mean, dtype=float)
    ewma_count = np.log1p(np.asarray(ewma_count, dtype=float))
    intercept = np.ones((len(indices), 1), dtype=float)
    if name == "short_term_ridge_proxy":
        return np.column_stack([intercept, one_hot, lag_mean, lag_count])
    if name == "history_ewma_ridge_proxy":
        return np.column_stack([intercept, one_hot, lag_mean, lag_count, ewma_mean, ewma_count])
    raise ValueError(f"Unknown ridge proxy: {name}")


def fit_ridge_proxy(
    history_events: pd.DataFrame,
    actions: list[str],
    model_name: str,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> RidgeProxyModel:
    """Fit a ridge proxy using only history-period target cells.

    Feature states for each history bin use only earlier history bins. The first
    bin receives a neutral zero/count-zero fallback rather than a full-history
    aggregate, which would leak future history observations into training rows.
    """
    n_actions = len(actions)
    proxy = action_proxy_cells(history_events, actions, cfg)
    targets = target_cells(history_events, actions, cfg)
    bins = targets["source_bin"].drop_duplicates().sort_values().to_numpy(np.int64)
    states = _feature_state_by_bin(proxy, bins, n_actions, cfg)

    rows: list[tuple[int, float, float, float, float, float]] = []
    for record in targets.itertuples(index=False):
        bin_id, action_index = int(record.source_bin), int(record.action_idx)
        lag_mean, lag_count, ewma_mean, ewma_count = states[bin_id]
        rows.append((
            action_index,
            float(lag_mean[action_index]),
            float(lag_count[action_index]),
            float(ewma_mean[action_index]),
            float(ewma_count[action_index]),
            float(record.observed_target),
        ))
    train = pd.DataFrame(
        rows,
        columns=["action_idx", "lag_mean", "lag_count", "ewma_mean", "ewma_count", "target"],
    )
    if len(train) < max(10, n_actions):
        raise ValueError("Insufficient valid historical action-bin cells to fit ridge proxy.")

    design = make_design_matrix(
        model_name,
        train["action_idx"].to_numpy(int),
        train["lag_mean"],
        train["lag_count"],
        train["ewma_mean"],
        train["ewma_count"],
        n_actions,
    )
    outcome = train["target"].to_numpy(float)
    penalty = np.eye(design.shape[1], dtype=float) * float(cfg.ridge_alpha)
    penalty[0, 0] = 0.0
    beta = np.linalg.pinv(design.T @ design + penalty) @ (design.T @ outcome)

    feature_names = ["intercept", *[f"action_{action}" for action in actions], "lag_proxy_mean", "log1p_lag_proxy_count"]
    if model_name == "history_ewma_ridge_proxy":
        feature_names += ["ewma_proxy_mean", "log1p_ewma_updates"]
    return RidgeProxyModel(model_name, beta, n_actions, feature_names, float(cfg.ridge_alpha))


def predict_ridge_proxy(
    model: RidgeProxyModel,
    action_idx: np.ndarray,
    lag_mean: np.ndarray,
    lag_count: np.ndarray,
    ewma_mean: np.ndarray,
    ewma_count: np.ndarray,
) -> np.ndarray:
    """Predict main-period scores from a history-fitted proxy."""
    return model.predict(action_idx, lag_mean, lag_count, ewma_mean, ewma_count)


def build_main_proxy_scores(
    main_events: pd.DataFrame,
    history_events: pd.DataFrame,
    actions: list[str],
    candidate_bins: np.ndarray,
    cfg: ExperimentConfig = DEFAULT_CONFIG,
) -> tuple[dict[str, dict[int, np.ndarray]], dict[str, RidgeProxyModel], pd.DataFrame]:
    """Fit on completed history and score main bins without future-main leakage."""
    n_actions = len(actions)
    history_proxy = action_proxy_cells(history_events, actions, cfg)
    main_proxy = action_proxy_cells(main_events, actions, cfg)
    priors = _proxy_priors(history_proxy, n_actions, cfg)
    states = _feature_state_by_bin(
        main_proxy,
        candidate_bins,
        n_actions,
        cfg,
        initial_ewma=(priors.ewma_mean, priors.ewma_count),
        initial_proxy_totals=(priors.proxy_sum, priors.proxy_count),
    )
    models = {
        "short_term_ridge_proxy": fit_ridge_proxy(history_events, actions, "short_term_ridge_proxy", cfg),
        "history_ewma_ridge_proxy": fit_ridge_proxy(history_events, actions, "history_ewma_ridge_proxy", cfg),
    }

    static_scores = history_mean_static_scores(history_events, actions, cfg)
    score_map: dict[str, dict[int, np.ndarray]] = {
        method: {} for method in [*models, "short_term_composite_surrogate", "history_mean_static"]
    }
    proxy_by_bin = {int(bin_id): frame for bin_id, frame in main_proxy.groupby("source_bin", sort=False)}
    completed_composite_sum = priors.composite_sum
    completed_composite_count = priors.composite_count
    last_bin: int | None = None

    for bin_id in map(int, candidate_bins):
        previous = proxy_by_bin.get(bin_id - int(cfg.sequential_bin_ms))
        if previous is not None and not previous.empty:
            completed_composite_sum += float(previous["composite_sum"].sum())
            completed_composite_count += float(previous["proxy_count"].sum())
        composite_fallback = (
            completed_composite_sum / completed_composite_count
            if completed_composite_count > 0
            else 0.0
        )
        lag_mean, lag_count, ewma_mean, ewma_count = states[bin_id]
        action_indices = np.arange(n_actions, dtype=int)
        for method, model in models.items():
            score_map[method][bin_id] = predict_ridge_proxy(
                model,
                action_indices,
                lag_mean,
                lag_count,
                ewma_mean,
                ewma_count,
            )

        composite_score = np.full(n_actions, composite_fallback, dtype=float)
        if previous is not None and not previous.empty:
            indices = previous["action_idx"].to_numpy(int)
            counts = previous["proxy_count"].to_numpy(float)
            sums = previous["composite_sum"].to_numpy(float)
            composite_score[indices] = np.divide(
                sums,
                counts,
                out=np.full_like(sums, composite_fallback),
                where=counts > 0,
            )
        score_map["short_term_composite_surrogate"][bin_id] = composite_score
        score_map["history_mean_static"][bin_id] = static_scores.copy()
        last_bin = bin_id

    coefficient_rows: list[dict[str, object]] = []
    for method, model in models.items():
        for feature, coefficient in zip(model.feature_names, model.beta):
            coefficient_rows.append({
                "method_id": method,
                "feature": feature,
                "coefficient": float(coefficient),
                "ridge_alpha": model.alpha,
                "fit_split": "history_standard_only",
                "main_feature_fallback": "completed_history_plus_earlier_main_bins_only",
            })
    coefficient_rows.append({
        "method_id": "history_mean_static",
        "feature": "history_action_target_mean",
        "coefficient": 1.0,
        "ridge_alpha": np.nan,
        "fit_split": "history_standard_only",
        "main_feature_fallback": "not_applicable_history_static_control",
    })
    return score_map, models, pd.DataFrame(coefficient_rows)
