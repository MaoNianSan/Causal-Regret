"""Aggregate the three module-specific derived artifact families."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import MODULE_A_ID, MODULE_B_ID, MODULE_C_ID, RESULT_SCHEMA
from exp4.outputs.manifests import write_stage_manifest
from exp4.outputs.writers import RunContext, attach_metadata
from exp4.reporting.aggregate_module_a import summarize_paired_contrasts, summarize_population
from exp4.reporting.aggregate_module_b import (
    aggregate_audit_performance,
    aggregate_selection_diagnostics,
    aggregate_weight_diagnostics,
)
from exp4.reporting.aggregate_module_c import (
    aggregate_control_summary,
    aggregate_correspondence_checks,
    aggregate_parameter_recovery,
)
from exp4.simulation.calibration import ProxyRouteCalibration


def _module_a_frames(
    context: RunContext, calibration: ProxyRouteCalibration
) -> tuple[list[pd.DataFrame], list[Path]]:
    module_dir = context.run_dir / "derived" / "module_a"
    seed_level = pd.read_parquet(module_dir / "exp4_module_a_seed_level.parquet")
    settings = mode_settings(context.run_tier)
    population = summarize_population(seed_level, settings.bootstrap_replications)
    contrasts, direction = summarize_paired_contrasts(
        seed_level, settings.bootstrap_replications, context.run_tier
    )
    frames = [population, contrasts, direction]
    tiers = ("primary", "primary", "diagnostic")
    frames = [
        attach_metadata(
            frame,
            context,
            MODULE_A_ID,
            tier,
            calibration_hash=calibration.calibration_hash,
        )
        for frame, tier in zip(frames, tiers, strict=True)
    ]
    paths = [
        module_dir / "exp4_module_a_population_summary.csv",
        module_dir / "exp4_module_a_paired_contrasts.csv",
        module_dir / "exp4_module_a_seed_direction_summary.csv",
    ]
    return frames, paths


def _module_b_frames(
    context: RunContext, calibration: ProxyRouteCalibration
) -> tuple[list[pd.DataFrame], list[Path]]:
    module_dir = context.run_dir / "derived" / "module_b"
    condition = pd.read_parquet(module_dir / "exp4_module_b_condition_level.parquet")
    deciles = pd.read_parquet(module_dir / "exp4_module_b_ambiguity_deciles.parquet")
    frames = [
        aggregate_audit_performance(condition),
        aggregate_weight_diagnostics(condition),
        aggregate_selection_diagnostics(condition, deciles),
    ]
    tiers = ("primary", "primary", "diagnostic")
    frames = [
        attach_metadata(
            frame,
            context,
            MODULE_B_ID,
            tier,
            calibration_hash=calibration.calibration_hash,
        )
        for frame, tier in zip(frames, tiers, strict=True)
    ]
    paths = [
        module_dir / "exp4_module_b_audit_performance.csv",
        module_dir / "exp4_module_b_weight_diagnostics.csv",
        module_dir / "exp4_module_b_selection_diagnostics.csv",
    ]
    return frames, paths


def _module_c_frames(
    context: RunContext, calibration: ProxyRouteCalibration
) -> tuple[list[pd.DataFrame], list[Path]]:
    module_dir = context.run_dir / "derived" / "module_c"
    replication = pd.read_parquet(module_dir / "exp4_module_c_replication_level.parquet")
    parameters = pd.read_parquet(module_dir / "exp4_module_c_parameter_level.parquet")
    correspondence = pd.read_parquet(
        module_dir / "exp4_module_c_correspondence_replication_level.parquet"
    )
    frames = [
        aggregate_control_summary(replication),
        aggregate_parameter_recovery(parameters),
        aggregate_correspondence_checks(correspondence),
    ]
    # The control summary keeps its per-control analysis_tier (from the frozen
    # CONTROL_REGISTRY); the other Module C frames are diagnostic.
    tiers: tuple[str | None, ...] = (None, "diagnostic", "diagnostic")
    frames = [
        attach_metadata(
            frame,
            context,
            MODULE_C_ID,
            tier,
            calibration_hash=calibration.calibration_hash,
        )
        for frame, tier in zip(frames, tiers, strict=True)
    ]
    paths = [
        module_dir / "exp4_module_c_control_summary.csv",
        module_dir / "exp4_module_c_parameter_recovery.csv",
        module_dir / "exp4_module_c_correspondence_checks.csv",
    ]
    return frames, paths


def aggregate_existing_run(
    context: RunContext, calibration: ProxyRouteCalibration
) -> list[Path]:
    frame_groups = (
        _module_a_frames(context, calibration),
        _module_b_frames(context, calibration),
        _module_c_frames(context, calibration),
    )
    paths: list[Path] = []
    for frames, group_paths in frame_groups:
        for frame, path in zip(frames, group_paths, strict=True):
            frame.to_csv(path, index=False)
        paths.extend(group_paths)
    write_stage_manifest(
        context.run_dir,
        "aggregation",
        len(paths),
        paths,
        {"result_schema": RESULT_SCHEMA},
    )
    return paths
