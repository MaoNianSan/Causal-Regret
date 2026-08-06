from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from contracts import ScientificInvariantError
from ..metrics import PairwiseMetricState

from .audit import build_bootstrap_bias_audit, build_resampling_audit
from .draws import (
    _BootstrapState,
    build_bootstrap_state,
    build_replicate_seeds,
    resolve_n_jobs,
)
from .replicate_metrics import _pair_metrics, run_replicate
from .summaries import attach_bootstrap_intervals, quantile_summary


@dataclass(frozen=True)
class BootstrapResult:
    draws: pd.DataFrame
    arrival_summary: pd.DataFrame
    pairwise_summary: pd.DataFrame
    audit: dict[str, Any]


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
    resampling = config["resampling"]
    n_bootstrap = int(
        n_bootstrap_override
        if n_bootstrap_override is not None
        else resampling["fast_repetitions" if mode == "fast" else "full_repetitions"]
    )
    if n_bootstrap <= 0:
        raise ValueError("Bootstrap repetitions must be positive.")
    top_k = int(config["ranking"]["primary_top_k"])
    state = build_bootstrap_state(
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
    batch_size = int(resampling.get("batch_size", 20))
    base_seed = int(resampling["seed"])
    seeds = build_replicate_seeds(base_seed, n_bootstrap)

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
            delayed(run_replicate)(replication_id, seeds[replication_id], state)
            for replication_id in range(start, stop)
        )
        for rows in results:
            all_rows.extend(rows)

    draws = pd.DataFrame(all_rows)
    reported_quantiles = tuple(float(value) for value in resampling["reported_quantiles"])
    if reported_quantiles != (0.025, 0.5, 0.975):
        raise ScientificInvariantError(
            "Reported resampling quantiles must be [0.025, 0.5, 0.975]."
        )
    arrival_summary = quantile_summary(
        draws.loc[draws["record_type"].eq("arrival_displacement")],
        group_columns=["route_id", "top_k"],
        reported_quantiles=reported_quantiles,
    )
    pairwise_summary = quantile_summary(
        draws.loc[draws["record_type"].eq("source_route_pair")],
        group_columns=["route_left", "route_right", "top_k"],
        reported_quantiles=reported_quantiles,
    )
    audit = build_resampling_audit(
        draws,
        n_bootstrap=n_bootstrap,
        base_seed=base_seed,
        reported_quantiles=reported_quantiles,
        n_users=state.n_users,
        n_jobs=n_jobs,
    )
    return BootstrapResult(
        draws=draws,
        arrival_summary=arrival_summary,
        pairwise_summary=pairwise_summary,
        audit=audit,
    )


__all__ = [
    "BootstrapResult",
    "attach_bootstrap_intervals",
    "build_bootstrap_bias_audit",
    "resolve_n_jobs",
    "run_uid_cluster_bootstrap",
]
