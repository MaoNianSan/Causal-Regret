"""Module A stage execution and seed-level artifact writing."""

from __future__ import annotations

import pandas as pd

from exp4.configuration.parameters import MODULE_A
from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import MODULE_A_ID
from exp4.execution.common import ordered_map, path_manifest_record
from exp4.modules.module_a import run_module_a_seed
from exp4.outputs.manifests import stage_complete, write_stage_manifest
from exp4.outputs.writers import RunContext, attach_metadata, write_parquet
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.simulation.trajectory import save_trajectory


def run_module_a_stage(
    context: RunContext,
    calibration: ProxyRouteCalibration,
    resume: bool,
) -> None:
    output_path = context.run_dir / "derived" / "module_a" / "exp4_module_a_seed_level.parquet"
    manifest_path = context.run_dir / "logs" / "exp4_module_a_path_manifest.csv"
    if resume and stage_complete(context.run_dir, "module_a"):
        return
    seed_count = mode_settings(context.run_tier).module_a_seed_count
    seeds = MODULE_A.evaluation_seeds[:seed_count]
    worker = lambda seed: run_module_a_seed(seed, calibration)
    records: list[dict[str, object]] = []
    path_records: list[dict[str, object]] = []
    for position, result in enumerate(
        ordered_map(worker, seeds, context.n_jobs), start=1
    ):
        trajectory_path = context.run_dir / "raw" / "trajectories" / f"module_a_seed_{result.trajectory.task_id:03d}.npz"
        save_trajectory(result.trajectory, trajectory_path)
        records.extend(result.seed_records)
        path_records.append(
            path_manifest_record(result.trajectory, trajectory_path, context.run_dir)
        )
        print(f"[Module A {position}/{len(seeds)}] seed={result.trajectory.task_id}")
    seed_level = attach_metadata(
        pd.DataFrame.from_records(records),
        context,
        MODULE_A_ID,
        "primary",
        "seed",
        calibration.calibration_hash,
    )
    write_parquet(seed_level, output_path)
    pd.DataFrame.from_records(path_records).to_csv(manifest_path, index=False)
    write_stage_manifest(
        context.run_dir,
        "module_a",
        len(seeds),
        [output_path, manifest_path],
        {"calibration_hash": calibration.calibration_hash},
    )
