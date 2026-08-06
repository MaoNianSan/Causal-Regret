"""Independent proxy-route calibration stage."""

from __future__ import annotations

from exp4.outputs.manifests import stage_complete, write_stage_manifest
from exp4.outputs.writers import RunContext, write_json
from exp4.simulation.calibration import (
    ProxyRouteCalibration,
    calibrate_proxy_route,
    load_proxy_route_calibration,
)


def run_calibration_stage(
    context: RunContext, resume: bool
) -> ProxyRouteCalibration:
    calibration_dir = context.run_dir / "derived" / "calibration"
    calibration_path = calibration_dir / "exp4_proxy_route_calibration.json"
    if resume and stage_complete(context.run_dir, "calibration"):
        return load_proxy_route_calibration(calibration_path)
    print("[Calibration] independent seeds=20")
    calibration, delay_frame, distance_frame = calibrate_proxy_route(
        context.source_code_hash, context.config_hash
    )
    delay_path = calibration_dir / "exp4_delay_prior.csv"
    distance_path = calibration_dir / "exp4_proxy_distance_summary.csv"
    write_json(calibration.as_json(), calibration_path)
    delay_frame.to_csv(delay_path, index=False)
    distance_frame.to_csv(distance_path, index=False)
    write_stage_manifest(
        context.run_dir,
        "calibration",
        len(calibration.calibration_seed_ids),
        [calibration_path, delay_path, distance_path],
        {"calibration_hash": calibration.calibration_hash},
    )
    return calibration
