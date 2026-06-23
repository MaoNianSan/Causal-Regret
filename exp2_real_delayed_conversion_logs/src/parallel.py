from __future__ import annotations

"""Portable, bounded thread-parallel helpers for EXP2.

The pipeline uses thread workers rather than process workers because the Criteo
intermediate tables can be large and Windows uses spawn semantics for processes.
Shared read-only pandas/numpy inputs avoid repeated serialization. BLAS thread
pools are limited by the runner to prevent nested oversubscription.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def _as_positive_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return None
    return value_int if value_int > 0 else None


def available_cpus() -> int:
    return max(1, int(os.cpu_count() or 1))


def resolve_n_jobs(cfg: dict, task_count: int | None = None, purpose: str = "analysis") -> int:
    """Resolve a portable worker count from configuration and current hardware.

    Rules:
    - runtime.n_jobs has highest precedence when an integer is passed from CLI;
    - otherwise parallel.n_jobs may be an integer or ``auto``;
    - auto reserves configured cores (default 2), then caps at the task count;
    - bootstrap workers have a separate memory guard because each replicate
      materializes an attribution table.
    """
    runtime = cfg.get("runtime", {}) if isinstance(cfg.get("runtime"), dict) else {}
    parallel = cfg.get("parallel", {}) if isinstance(cfg.get("parallel"), dict) else {}
    raw = runtime.get("n_jobs", parallel.get("n_jobs", "auto"))
    cpus = available_cpus()
    reserve = max(0, int(parallel.get("reserve_cores", 2)))

    explicit = _as_positive_int(raw)
    if explicit is not None:
        jobs = explicit
    else:
        jobs = max(1, cpus - reserve)

    purpose_cap = parallel.get(f"{purpose}_max_workers")
    cap = _as_positive_int(purpose_cap)
    if cap is not None:
        jobs = min(jobs, cap)
    if task_count is not None:
        jobs = min(jobs, max(1, int(task_count)))
    return max(1, int(jobs))


def parallel_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    cfg: dict,
    *,
    purpose: str = "analysis",
) -> list[R]:
    """Ordered thread-parallel map with a deterministic serial fallback."""
    sequence: list[T] = list(items)
    if not sequence:
        return []
    workers = resolve_n_jobs(cfg, len(sequence), purpose=purpose)
    if workers <= 1:
        return [fn(item) for item in sequence]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"exp2-{purpose}") as pool:
        # executor.map preserves input order, which keeps emitted artifacts stable.
        return list(pool.map(fn, sequence))


def parallel_runtime_metadata(cfg: dict, *, analysis_tasks: int | None = None, bootstrap_tasks: int | None = None) -> dict:
    parallel = cfg.get("parallel", {}) if isinstance(cfg.get("parallel"), dict) else {}
    return {
        "parallel_backend": "ThreadPoolExecutor",
        "host_logical_cpus": available_cpus(),
        "configured_n_jobs": cfg.get("runtime", {}).get("n_jobs", parallel.get("n_jobs", "auto")),
        "reserve_cores": int(parallel.get("reserve_cores", 2)),
        "resolved_analysis_workers": resolve_n_jobs(cfg, analysis_tasks, purpose="analysis"),
        "resolved_bootstrap_workers": resolve_n_jobs(cfg, bootstrap_tasks, purpose="bootstrap"),
        "blas_threads_per_worker": int(parallel.get("blas_threads_per_worker", 1)),
    }
