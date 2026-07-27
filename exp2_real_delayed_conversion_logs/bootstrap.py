from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.sparse import csr_matrix
from scipy.stats import kendalltau
from tqdm.auto import tqdm

from contracts import PRIMARY_ROUTE_ORDER, PRIMARY_SOURCE_ROUTE_ORDER, ScientificInvariantError
from metrics import PairwiseMetricState


@dataclass(frozen=True)
class BootstrapResult:
    draws: pd.DataFrame
    arrival_summary: pd.DataFrame
    pairwise_summary: pd.DataFrame
    audit: dict[str, Any]


@dataclass(frozen=True)
class _BootstrapState:
    route_matrices: dict[str, csr_matrix]
    eligible_impressions: np.ndarray
    tie_rank: np.ndarray
    n_users: int
    top_k: int
    frozen_support_masks: dict[tuple[str, str], np.ndarray]
    frozen_support_counts: dict[tuple[str, str], int]


def resolve_n_jobs(value: str | int, *, reserve_cores: int = 2) -> int:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("n_jobs must be positive.")
        return value
    text = str(value).strip().lower()
    if text != "auto":
        parsed = int(text)
        if parsed <= 0:
            raise ValueError("n_jobs must be positive.")
        return parsed
    available = os.cpu_count() or 1
    return min(8, max(1, available - max(0, int(reserve_cores))))


def _build_state(
    assignments: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    *,
    top_k: int,
    metric_states: tuple[PairwiseMetricState, ...],
) -> _BootstrapState:
    retained = journey_manifest.loc[
        journey_manifest["is_primary_eligible"], ["journey_id", "user_id"]
    ].copy()
    users = np.sort(retained["user_id"].astype(str).unique())
    user_to_index = {user_id: index for index, user_id in enumerate(users)}

    cells = decision_cells.sort_values(
        ["campaign_id", "source_date_utc", "decision_cell_id"], kind="stable"
    ).reset_index(drop=True)
    cell_ids = cells["decision_cell_id"].astype(str).to_numpy()
    cell_to_index = {cell_id: index for index, cell_id in enumerate(cell_ids)}
    if top_k >= len(cells):
        raise ScientificInvariantError(
            f"top_k={top_k} must be below cell universe={len(cells)}."
        )

    primary = assignments.loc[assignments["route_id"].isin(PRIMARY_ROUTE_ORDER)].copy()
    primary = primary.merge(retained, on="journey_id", how="left", validate="many_to_one")
    if primary["user_id"].isna().any():
        raise ScientificInvariantError("Primary route assignments contain journeys outside the cohort.")
    primary["user_index"] = primary["user_id"].astype(str).map(user_to_index)
    primary["cell_index"] = primary["decision_cell_id"].astype(str).map(cell_to_index)
    if primary[["user_index", "cell_index"]].isna().any().any():
        raise ScientificInvariantError("Bootstrap assignments fall outside user/cell indices.")

    route_matrices: dict[str, csr_matrix] = {}
    for route_id in PRIMARY_ROUTE_ORDER:
        route = primary.loc[primary["route_id"].eq(route_id)]
        matrix = csr_matrix(
            (
                route["credit_weight"].to_numpy(dtype=float),
                (
                    route["user_index"].to_numpy(dtype=np.int64),
                    route["cell_index"].to_numpy(dtype=np.int64),
                ),
            ),
            shape=(len(users), len(cells)),
            dtype=float,
        )
        route_matrices[route_id] = matrix

    expected_pairs = {
        ("arrival_bin_anchor", route_id) for route_id in PRIMARY_SOURCE_ROUTE_ORDER
    }
    expected_pairs.update(combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2))
    observed_pairs = {(item.route_left, item.route_right) for item in metric_states}
    if len(observed_pairs) != len(metric_states) or observed_pairs != expected_pairs:
        raise ScientificInvariantError(
            "Bootstrap requires exactly one frozen Kendall support for every primary comparison."
        )
    frozen_support_masks: dict[tuple[str, str], np.ndarray] = {}
    frozen_support_counts: dict[tuple[str, str], int] = {}
    for item in metric_states:
        support_ids = tuple(str(value) for value in item.support_cell_ids)
        if len(support_ids) != len(set(support_ids)):
            raise ScientificInvariantError("Frozen Kendall support contains duplicate cell IDs.")
        missing = sorted(set(support_ids).difference(cell_to_index))
        if missing:
            raise ScientificInvariantError(
                f"Frozen Kendall support contains unknown cell IDs: {missing[:10]}"
            )
        mask = np.zeros(len(cells), dtype=bool)
        mask[[cell_to_index[cell_id] for cell_id in support_ids]] = True
        if int(mask.sum()) < 2:
            raise ScientificInvariantError("Frozen Kendall support has fewer than two cells.")
        key = (item.route_left, item.route_right)
        frozen_support_masks[key] = mask
        frozen_support_counts[key] = int(mask.sum())

    return _BootstrapState(
        route_matrices=route_matrices,
        eligible_impressions=cells["eligible_impression_count"].to_numpy(dtype=float),
        tie_rank=np.arange(len(cells), dtype=np.int64),
        n_users=len(users),
        top_k=int(top_k),
        frozen_support_masks=frozen_support_masks,
        frozen_support_counts=frozen_support_counts,
    )


def _top_k_indices(scores: np.ndarray, tie_rank: np.ndarray, top_k: int) -> np.ndarray:
    order = np.lexsort((tie_rank, -np.asarray(scores, dtype=float)))
    return order[:top_k]


def _route_vectors(state: _BootstrapState, multiplicity: np.ndarray) -> dict[str, dict[str, np.ndarray]]:
    outputs: dict[str, dict[str, np.ndarray]] = {}
    for route_id, matrix in state.route_matrices.items():
        credits = np.asarray(matrix.T.dot(multiplicity), dtype=float).reshape(-1)
        total = float(credits.sum())
        if total <= 0:
            raise ScientificInvariantError(f"Bootstrap route {route_id} has nonpositive credit.")
        allocation = credits / total
        scores = credits / state.eligible_impressions
        outputs[route_id] = {"credits": credits, "allocation": allocation, "scores": scores}
    return outputs


def _pair_metrics(
    vectors: dict[str, dict[str, np.ndarray]],
    left_route: str,
    right_route: str,
    state: _BootstrapState,
) -> dict[str, float | int]:
    left = vectors[left_route]
    right = vectors[right_route]
    tv = 0.5 * float(np.abs(left["allocation"] - right["allocation"]).sum())
    left_top = set(_top_k_indices(left["scores"], state.tie_rank, state.top_k).tolist())
    right_top = set(_top_k_indices(right["scores"], state.tie_rank, state.top_k).tolist())
    overlap = len(left_top.intersection(right_top)) / float(state.top_k)
    pair_key = (left_route, right_route)
    support = state.frozen_support_masks[pair_key]
    support_count = int(support.sum())
    full_sample_support_count = state.frozen_support_counts[pair_key]
    if support_count != full_sample_support_count:
        raise ScientificInvariantError("Bootstrap Kendall support changed within a replicate.")
    left_scores = left["scores"][support]
    right_scores = right["scores"][support]
    left_constant = bool(np.unique(left_scores).size <= 1)
    right_constant = bool(np.unique(right_scores).size <= 1)
    zero_mass_vector = bool(
        np.isclose(left["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
        or np.isclose(right["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
    )
    if support_count >= 2 and not (left_constant or right_constant):
        tau = float(
            kendalltau(
                left_scores,
                right_scores,
                variant="b",
                nan_policy="omit",
            ).statistic
        )
    else:
        tau = float("nan")
    return {
        "allocation_tv": float(np.clip(tv, 0.0, 1.0)),
        "top_k_overlap": overlap,
        "ranking_displacement_at_k": 1.0 - overlap,
        "kendall_tau_b": tau,
        "common_active_support_count": full_sample_support_count,
        "full_sample_support_count": full_sample_support_count,
        "bootstrap_support_count": support_count,
        "support_frozen": True,
        "constant_vector": left_constant or right_constant,
        "zero_mass_vector": zero_mass_vector,
    }


def _run_replicate(replication_id: int, seed: int, state: _BootstrapState) -> list[dict[str, object]]:
    rng = np.random.default_rng(seed)
    multiplicity = rng.multinomial(
        state.n_users, np.full(state.n_users, 1.0 / state.n_users, dtype=float)
    ).astype(float)
    vectors = _route_vectors(state, multiplicity)
    rows: list[dict[str, object]] = []
    for route_id in PRIMARY_SOURCE_ROUTE_ORDER:
        metrics = _pair_metrics(vectors, "arrival_bin_anchor", route_id, state)
        rows.append(
            {
                "replication_id": replication_id,
                "record_type": "arrival_displacement",
                "route_id": route_id,
                "route_left": "arrival_bin_anchor",
                "route_right": route_id,
                "top_k": state.top_k,
                **metrics,
            }
        )
    for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2):
        metrics = _pair_metrics(vectors, left_route, right_route, state)
        rows.append(
            {
                "replication_id": replication_id,
                "record_type": "source_route_pair",
                "route_id": pd.NA,
                "route_left": left_route,
                "route_right": right_route,
                "top_k": state.top_k,
                **metrics,
            }
        )
    return rows


def _quantile_summary(
    draws: pd.DataFrame,
    *,
    group_columns: list[str],
    confidence_level: float,
) -> pd.DataFrame:
    alpha = (1.0 - confidence_level) / 2.0
    metrics = [
        "allocation_tv",
        "top_k_overlap",
        "ranking_displacement_at_k",
        "kendall_tau_b",
        "common_active_support_count",
    ]
    rows: list[dict[str, object]] = []
    for keys, group in draws.groupby(group_columns, sort=False, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys, strict=True))
        row["bootstrap_repetitions"] = int(group["replication_id"].nunique())
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(dtype=float)
            row[f"{metric}_bootstrap_mean"] = float(np.mean(values)) if len(values) else np.nan
            row[f"{metric}_bootstrap_median"] = float(np.median(values)) if len(values) else np.nan
            row[f"{metric}_ci_lower"] = float(np.quantile(values, alpha)) if len(values) else np.nan
            row[f"{metric}_ci_upper"] = float(np.quantile(values, 1.0 - alpha)) if len(values) else np.nan
        full_counts = pd.to_numeric(group["full_sample_support_count"], errors="raise").unique()
        if len(full_counts) != 1:
            raise ScientificInvariantError("Full-sample Kendall support varies within a comparison.")
        bootstrap_support = pd.to_numeric(
            group["bootstrap_support_count"], errors="raise"
        ).to_numpy(dtype=int)
        row["full_sample_support_count"] = int(full_counts[0])
        row["bootstrap_support_min"] = int(bootstrap_support.min())
        row["bootstrap_support_max"] = int(bootstrap_support.max())
        row["support_frozen"] = bool(group["support_frozen"].all())
        row["kendall_tau_b_nan_fraction"] = float(group["kendall_tau_b"].isna().mean())
        row["constant_vector_fraction"] = float(group["constant_vector"].mean())
        row["zero_mass_vector_fraction"] = float(group["zero_mass_vector"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def run_uid_cluster_bootstrap(
    assignments: pd.DataFrame,
    journey_manifest: pd.DataFrame,
    decision_cells: pd.DataFrame,
    config: dict[str, Any],
    *,
    mode: str,
    metric_states: tuple[PairwiseMetricState, ...],
    n_bootstrap_override: int | None = None,
    n_jobs_override: str | int | None = None,
    progress: bool = True,
) -> BootstrapResult:
    statistics = config["statistics"]
    n_bootstrap = int(
        n_bootstrap_override
        if n_bootstrap_override is not None
        else statistics["fast_repetitions" if mode == "fast" else "full_repetitions"]
    )
    if n_bootstrap <= 0:
        raise ValueError("Bootstrap repetitions must be positive.")
    top_k = int(config["ranking"]["primary_top_k"])
    state = _build_state(
        assignments,
        journey_manifest,
        decision_cells,
        top_k=top_k,
        metric_states=metric_states,
    )
    runtime = config["runtime"]
    n_jobs = resolve_n_jobs(
        n_jobs_override if n_jobs_override is not None else runtime.get("n_jobs", "auto"),
        reserve_cores=int(runtime.get("reserve_cores", 2)),
    )
    batch_size = int(statistics.get("bootstrap_batch_size", 20))
    base_seed = int(statistics["bootstrap_seed"])
    seed_sequences = np.random.SeedSequence(base_seed).spawn(n_bootstrap)
    seeds = [int(sequence.generate_state(1, dtype=np.uint64)[0]) for sequence in seed_sequences]

    all_rows: list[dict[str, object]] = []
    batches = range(0, n_bootstrap, batch_size)
    iterator = tqdm(
        batches,
        desc="UID-cluster bootstrap",
        disable=not progress,
        total=(n_bootstrap + batch_size - 1) // batch_size,
        unit="batch",
    )
    for start in iterator:
        stop = min(start + batch_size, n_bootstrap)
        results = Parallel(n_jobs=n_jobs, prefer="threads")(
            delayed(_run_replicate)(replication_id, seeds[replication_id], state)
            for replication_id in range(start, stop)
        )
        for rows in results:
            all_rows.extend(rows)

    draws = pd.DataFrame(all_rows)
    confidence_level = float(statistics["confidence_level"])
    arrival_summary = _quantile_summary(
        draws.loc[draws["record_type"].eq("arrival_displacement")],
        group_columns=["route_id", "top_k"],
        confidence_level=confidence_level,
    )
    pairwise_summary = _quantile_summary(
        draws.loc[draws["record_type"].eq("source_route_pair")],
        group_columns=["route_left", "route_right", "top_k"],
        confidence_level=confidence_level,
    )
    comparison_audit: list[dict[str, Any]] = []
    for keys, group in draws.groupby(
        ["record_type", "route_left", "route_right"], sort=False, dropna=False
    ):
        full_counts = group["full_sample_support_count"].unique()
        if len(full_counts) != 1:
            raise ScientificInvariantError("Bootstrap comparison has inconsistent full support.")
        comparison_audit.append(
            {
                "record_type": str(keys[0]),
                "route_left": str(keys[1]),
                "route_right": str(keys[2]),
                "full_sample_support_count": int(full_counts[0]),
                "bootstrap_support_min": int(group["bootstrap_support_count"].min()),
                "bootstrap_support_max": int(group["bootstrap_support_count"].max()),
                "support_frozen": bool(group["support_frozen"].all()),
                "nan_fraction": float(group["kendall_tau_b"].isna().mean()),
                "constant_vector_fraction": float(group["constant_vector"].mean()),
                "zero_mass_vector_fraction": float(group["zero_mass_vector"].mean()),
            }
        )
    audit = {
        "bootstrap_unit": "user_id",
        "bootstrap_repetitions": n_bootstrap,
        "bootstrap_seed": base_seed,
        "confidence_level": confidence_level,
        "interval_method": "percentile",
        "n_users": state.n_users,
        "n_jobs": n_jobs,
        "support_definition": "full_sample_union_positive_credit_cells",
        "support_frozen": bool(all(item["support_frozen"] for item in comparison_audit)),
        "comparisons": comparison_audit,
    }
    return BootstrapResult(
        draws=draws,
        arrival_summary=arrival_summary,
        pairwise_summary=pairwise_summary,
        audit=audit,
    )


def _attach_metric_diagnostics(
    frame: pd.DataFrame,
    point_columns: dict[str, str],
) -> pd.DataFrame:
    output = frame.copy()
    for metric, point_column in point_columns.items():
        mean_column = f"{metric}_bootstrap_mean"
        median_column = f"{metric}_bootstrap_median"
        lower_column = f"{metric}_ci_lower"
        upper_column = f"{metric}_ci_upper"
        output[f"{metric}_bootstrap_bias_mean"] = output[mean_column] - output[point_column]
        output[f"{metric}_bootstrap_bias_median"] = output[median_column] - output[point_column]
        output[f"{metric}_point_outside_percentile_ci"] = (
            output[point_column].lt(output[lower_column])
            | output[point_column].gt(output[upper_column])
        )
    return output


def attach_bootstrap_intervals(
    arrival_point: pd.DataFrame,
    pairwise_point: pd.DataFrame,
    bootstrap: BootstrapResult,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    arrival = arrival_point.merge(
        bootstrap.arrival_summary,
        on=["route_id", "top_k"],
        how="left",
        validate="one_to_one",
    )
    pairwise = pairwise_point.merge(
        bootstrap.pairwise_summary,
        on=["route_left", "route_right", "top_k"],
        how="left",
        validate="one_to_one",
    )
    arrival = _attach_metric_diagnostics(
        arrival,
        {
            "allocation_tv": "allocation_tv_vs_arrival",
            "top_k_overlap": "top_k_overlap_vs_arrival",
            "ranking_displacement_at_k": "ranking_displacement_at_k",
            "kendall_tau_b": "kendall_tau_b_vs_arrival",
            "common_active_support_count": "common_active_support_count",
        },
    )
    pairwise = _attach_metric_diagnostics(
        pairwise,
        {
            "allocation_tv": "allocation_tv",
            "top_k_overlap": "top_k_overlap",
            "ranking_displacement_at_k": "ranking_displacement_at_k",
            "kendall_tau_b": "kendall_tau_b",
            "common_active_support_count": "common_active_support_count",
        },
    )
    return arrival, pairwise


def build_bootstrap_bias_audit(
    arrival: pd.DataFrame, pairwise: pd.DataFrame
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for frame_name, frame, identity_columns in (
        ("arrival_displacement", arrival, ["route_id"]),
        ("source_route_pair", pairwise, ["route_left", "route_right"]),
    ):
        for metric in (
            "allocation_tv",
            "top_k_overlap",
            "ranking_displacement_at_k",
            "kendall_tau_b",
            "common_active_support_count",
        ):
            outside_column = f"{metric}_point_outside_percentile_ci"
            mean_bias_column = f"{metric}_bootstrap_bias_mean"
            median_bias_column = f"{metric}_bootstrap_bias_median"
            for row in frame.itertuples(index=False):
                record = {
                    "record_type": frame_name,
                    "metric": metric,
                    "point_outside_percentile_ci": bool(getattr(row, outside_column)),
                    "bootstrap_bias_mean": float(getattr(row, mean_bias_column)),
                    "bootstrap_bias_median": float(getattr(row, median_bias_column)),
                }
                for identity in identity_columns:
                    record[identity] = getattr(row, identity)
                records.append(record)
    allocation_tv_records = [record for record in records if record["metric"] == "allocation_tv"]
    outside_count = sum(
        record["point_outside_percentile_ci"] for record in allocation_tv_records
    )
    return {
        "interval_method": "percentile",
        "headline_metric": "allocation_tv",
        "diagnostic_status": "WARNING" if outside_count else "PASS",
        "point_outside_percentile_ci_count": int(outside_count),
        "diagnostic_count": int(len(allocation_tv_records)),
        "all_metric_diagnostic_count": int(len(records)),
        "interpretation": (
            "A point estimate outside a percentile bootstrap interval is recorded as a warning, "
            "not a run failure; non-smooth nonnegative statistics may have biased bootstrap distributions."
        ),
        "records": records,
    }
