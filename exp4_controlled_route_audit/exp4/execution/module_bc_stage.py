"""Module B/C execution and replication-level artifact writing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from exp4.configuration.parameters import MODULE_B
from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import MODULE_B_ID, MODULE_C_ID
from exp4.execution.common import ordered_map, path_manifest_record
from exp4.modules.module_b import ModuleBResult, run_module_b
from exp4.modules.module_c import ModuleCResult, run_module_c
from exp4.outputs.manifests import stage_complete, write_stage_manifest
from exp4.outputs.writers import ParquetBatchWriter, RunContext, attach_metadata, write_parquet
from exp4.routes.partial_label_proxy import construct_partial_label_proxy_route
from exp4.simulation.calibration import ProxyRouteCalibration
from exp4.simulation.trajectory import StructuralTrajectory, generate_structural_trajectory, save_trajectory


@dataclass(frozen=True)
class ModuleBCResult:
    replication_id: int
    trajectory: StructuralTrajectory
    proxy_route_map: np.ndarray
    proxy_route_hash: str
    module_b: ModuleBResult
    module_c: ModuleCResult


def run_module_bc_replication(
    replication_id: int, calibration: ProxyRouteCalibration
) -> ModuleBCResult:
    trajectory = generate_structural_trajectory(
        "module_b", replication_id, MODULE_B.horizon, MODULE_B.warmup
    )
    proxy_route = construct_partial_label_proxy_route(
        trajectory,
        MODULE_B.route_label_rate,
        MODULE_B.proxy_noise_sd,
        calibration,
    )
    return ModuleBCResult(
        replication_id,
        trajectory,
        proxy_route.route_loss_map,
        proxy_route.route_map_hash,
        run_module_b(replication_id, trajectory, proxy_route),
        run_module_c(replication_id, trajectory, proxy_route),
    )


def _paths(context: RunContext) -> dict[str, object]:
    module_b = context.run_dir / "derived" / "module_b"
    module_c = context.run_dir / "derived" / "module_c"
    return {
        "unit": module_b / "exp4_module_b_audit_unit_level.parquet",
        "condition": module_b / "exp4_module_b_condition_level.parquet",
        "decile": module_b / "exp4_module_b_ambiguity_deciles.parquet",
        "c_replication": module_c / "exp4_module_c_replication_level.parquet",
        "c_parameter": module_c / "exp4_module_c_parameter_level.parquet",
        "c_correspondence": module_c / "exp4_module_c_correspondence_replication_level.parquet",
        "manifest": context.run_dir / "logs" / "exp4_module_bc_path_manifest.csv",
    }


def _store_raw_result(
    context: RunContext,
    result: ModuleBCResult,
    calibration: ProxyRouteCalibration,
) -> dict[str, object]:
    trajectory_path = context.run_dir / "raw" / "trajectories" / f"module_b_replication_{result.replication_id:04d}.npz"
    route_map_path = context.run_dir / "raw" / "route_maps" / f"module_b_replication_{result.replication_id:04d}.npz"
    save_trajectory(result.trajectory, trajectory_path)
    np.savez_compressed(
        route_map_path,
        structural_loss_map=result.trajectory.structural_loss_map,
        proxy_route_loss_map=result.proxy_route_map,
        trajectory_hash=np.array([result.trajectory.trajectory_hash]),
        route_map_hash=np.array([result.proxy_route_hash]),
        calibration_hash=np.array([calibration.calibration_hash]),
    )
    return path_manifest_record(
        result.trajectory,
        trajectory_path,
        context.run_dir,
        route_map_path,
        result.proxy_route_hash,
    )


def _write_frames(
    context: RunContext,
    calibration: ProxyRouteCalibration,
    paths: dict[str, object],
    records: dict[str, list[dict[str, object]]],
) -> None:
    specs = (
        ("condition", MODULE_B_ID, "primary", "condition"),
        ("decile", MODULE_B_ID, "appendix", "decile"),
        ("c_replication", MODULE_C_ID, "mixed", "c_replication"),
        ("c_parameter", MODULE_C_ID, "diagnostic", "c_parameter"),
        ("c_correspondence", MODULE_C_ID, "diagnostic", "c_correspondence"),
    )
    for record_key, module_id, tier, path_key in specs:
        frame = attach_metadata(
            pd.DataFrame.from_records(records[record_key]),
            context,
            module_id,
            tier,
            "replication_id",
            calibration.calibration_hash,
        )
        write_parquet(frame, paths[path_key])
    pd.DataFrame.from_records(records["manifest"]).to_csv(paths["manifest"], index=False)


def run_module_bc_stage(
    context: RunContext,
    calibration: ProxyRouteCalibration,
    resume: bool,
) -> None:
    paths = _paths(context)
    if resume and stage_complete(context.run_dir, "module_bc"):
        return
    replication_count = mode_settings(context.run_tier).module_b_replications
    worker = lambda replication_id: run_module_bc_replication(replication_id, calibration)
    records: dict[str, list[dict[str, object]]] = {
        key: [] for key in ("condition", "decile", "c_replication", "c_parameter", "c_correspondence", "manifest")
    }
    with ParquetBatchWriter(paths["unit"]) as unit_writer:
        for position, result in enumerate(
            ordered_map(worker, range(replication_count), context.n_jobs), start=1
        ):
            unit_writer.write(
                attach_metadata(result.module_b.unit_level, context, MODULE_B_ID, "primary", "replication_id", calibration.calibration_hash)
            )
            records["condition"].extend(result.module_b.condition_records)
            records["decile"].extend(result.module_b.ambiguity_decile_records)
            records["c_replication"].extend(result.module_c.replication_records)
            records["c_parameter"].extend(result.module_c.parameter_records)
            records["c_correspondence"].extend(result.module_c.correspondence_records)
            records["manifest"].append(_store_raw_result(context, result, calibration))
            print(f"[Module B/C {position}/{replication_count}] replication={result.replication_id}")
    _write_frames(context, calibration, paths, records)
    artifacts = [path for path in paths.values() if hasattr(path, "exists")]
    write_stage_manifest(
        context.run_dir,
        "module_bc",
        replication_count,
        artifacts,
        {"calibration_hash": calibration.calibration_hash},
    )
