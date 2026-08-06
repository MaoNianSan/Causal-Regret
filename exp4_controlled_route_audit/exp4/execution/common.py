"""Ordered parallel mapping and path-manifest helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from typing import Callable, Iterable, Iterator, TypeVar

from exp4.simulation.trajectory import StructuralTrajectory


T = TypeVar("T")
R = TypeVar("R")


def ordered_map(
    function: Callable[[T], R], values: Iterable[T], n_jobs: int
) -> Iterator[R]:
    if n_jobs <= 1:
        for value in values:
            yield function(value)
        return
    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        yield from executor.map(function, values)


def path_manifest_record(
    trajectory: StructuralTrajectory,
    path: Path,
    run_dir: Path,
    route_map_path: Path | None = None,
    route_map_hash: str | None = None,
) -> dict[str, object]:
    return {
        "module_id": trajectory.module_id,
        "task_id": trajectory.task_id,
        "trajectory_file": path.relative_to(run_dir).as_posix(),
        "route_map_file": (
            route_map_path.relative_to(run_dir).as_posix()
            if route_map_path is not None
            else None
        ),
        "trajectory_hash": trajectory.trajectory_hash,
        "route_map_hash": route_map_hash,
        "decision_horizon": trajectory.decision_horizon,
        "warmup": trajectory.warmup,
        "clock_horizon": trajectory.clock_horizon,
        "mean_delay": trajectory.mean_delay,
        "stream_seeds": json.dumps(trajectory.stream_seeds, sort_keys=True),
        **trajectory.path_hashes,
    }
