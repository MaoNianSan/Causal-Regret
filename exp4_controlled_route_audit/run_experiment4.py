"""Canonical Exp4 execution pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

import config
from aggregate_results import (
    summarize_audit_conditions,
    summarize_calibration_controls,
    summarize_effective_support,
    summarize_route_boundary,
)
from engine import run_module_a_seed, run_module_b_replication
from io_utils import (
    ParquetBatchWriter,
    RunContext,
    attach_metadata,
    write_json,
    write_parquet,
    write_run_config,
)


def _add_global_metadata(
    frame: pd.DataFrame,
    run_context: RunContext,
    module_id: str | None = None,
    analysis_tier: str | None = None,
    seed_column: str | None = None,
) -> pd.DataFrame:
    output = frame.copy()
    output["run_id"] = run_context.run_id
    output["run_tier"] = run_context.run_tier
    output["paper_result"] = False
    output["experiment_id"] = config.EXPERIMENT_ID
    if module_id is not None:
        output["module_id"] = module_id
    if analysis_tier is not None:
        output["analysis_tier"] = analysis_tier
    if "configuration_id" not in output.columns:
        output["configuration_id"] = "aggregate"
    if "seed_or_replication" not in output.columns:
        if seed_column is not None and seed_column in output.columns:
            output["seed_or_replication"] = output[seed_column]
        else:
            output["seed_or_replication"] = "aggregate"
    output["code_commit"] = run_context.code_commit
    output["config_hash"] = run_context.config_hash
    output["input_manifest_hash"] = run_context.input_manifest_hash
    output["result_schema"] = run_context.result_schema
    return output


def _write_legacy_reuse_audit(run_context: RunContext) -> None:
    payload = {
        "audit_scope": "legacy_exp4_v1_outputs",
        "state_transition_action_dependent": False,
        "structural_loss_map_saved": False,
        "realized_feedback_saved": False,
        "delay_path_policy_independent": True,
        "route_action_path_saved": False,
        "route_label_mask_saved": False,
        "audit_label_mask_saved": False,
        "proxy_features_saved": False,
        "path_hash_consistent": None,
        "reuse_status": "REQUIRES_RERUN",
        "reason": (
            "Legacy outputs do not contain the deterministic structural maps, full route "
            "maps, extended clock, or independent route/audit evidence streams required "
            "by the new estimands."
        ),
        "result_schema": config.RESULT_SCHEMA,
    }
    write_json(
        payload,
        run_context.run_dir / "checks" / "exp4_trajectory_reuse_audit.json",
    )


def run_experiment4(run_context: RunContext) -> dict[str, Path]:
    settings = config.mode_settings(run_context.run_tier)
    write_run_config(run_context, settings)
    _write_legacy_reuse_audit(run_context)
    derived_dir = run_context.run_dir / "derived"

    print("[1/6] Generate Module A shared trajectories and route maps")
    module_a_seed_records: list[dict[str, Any]] = []
    module_a_pair_records: list[dict[str, Any]] = []
    learner_records: list[dict[str, Any]] = []
    path_manifest_records: list[dict[str, Any]] = []
    for seed in tqdm(settings["module_a_seeds"], desc="Module A seeds", unit="seed"):
        result = run_module_a_seed(
            seed=int(seed),
            decision_horizon=int(settings["module_a_decision_horizon"]),
            warmup_rounds=int(settings["module_a_warmup_rounds"]),
            run_dir=run_context.run_dir,
        )
        module_a_seed_records.extend(result["seed_records"])
        module_a_pair_records.extend(result["pair_records"])
        learner_records.extend(result["learner_records"])
        path_manifest_records.append(result["trajectory_manifest_record"])

    seed_level = _add_global_metadata(
        pd.DataFrame(module_a_seed_records),
        run_context,
        module_id=config.MODULE_ROUTE_BOUNDARY,
        seed_column="seed",
    )
    pair_level = _add_global_metadata(
        pd.DataFrame(module_a_pair_records),
        run_context,
        module_id=config.MODULE_ROUTE_BOUNDARY,
        seed_column="seed",
    )
    learner_frame = _add_global_metadata(
        pd.DataFrame(learner_records),
        run_context,
        module_id=config.MODULE_LEARNER_APPENDIX,
        analysis_tier="appendix",
        seed_column="seed",
    )
    write_parquet(seed_level, derived_dir / "exp4_route_boundary_seed_level.parquet")
    write_parquet(
        pair_level, derived_dir / "exp4_route_boundary_pairwise_metrics.parquet"
    )
    learner_frame.to_csv(
        derived_dir / "exp4_learner_consequence_appendix.csv", index=False
    )
    route_boundary_summary = summarize_route_boundary(
        seed_level, int(settings["bootstrap_replications"])
    )
    route_boundary_summary = _add_global_metadata(
        route_boundary_summary,
        run_context,
        module_id=config.MODULE_ROUTE_BOUNDARY,
        seed_column=None,
    )
    route_boundary_summary.to_csv(
        derived_dir / "exp4_route_boundary_summary.csv", index=False
    )

    print("[2/6] Run Module B evidence-qualified audit simulations")
    raw_records: list[dict[str, Any]] = []
    calibrated_records: list[dict[str, Any]] = []
    population_target_records: list[dict[str, Any]] = []
    control_records: list[dict[str, Any]] = []
    audit_unit_path = derived_dir / "exp4_audit_unit_level.parquet"
    calibration_parameter_path = (
        derived_dir / "exp4_calibration_fold_parameters.parquet"
    )
    with ParquetBatchWriter(audit_unit_path) as audit_unit_writer, ParquetBatchWriter(
        calibration_parameter_path
    ) as parameter_writer:
        for replication_id in tqdm(
            range(int(settings["module_b_replications"])),
            desc="Module B replications",
            unit="rep",
        ):
            result = run_module_b_replication(
                replication_id=replication_id,
                decision_horizon=int(settings["module_b_decision_horizon"]),
                warmup_rounds=int(settings["module_b_warmup_rounds"]),
                run_dir=run_context.run_dir,
            )
            audit_units = _add_global_metadata(
                pd.DataFrame(result["audit_unit_records"]),
                run_context,
                module_id=config.MODULE_AUDIT_RELIABILITY,
                analysis_tier="primary",
                seed_column="replication_id",
            )
            audit_unit_writer.write(audit_units)
            parameters = pd.DataFrame(result["calibration_parameter_records"])
            parameters["module_id"] = parameters["route_id"].astype(str).map(
                lambda value: (
                    config.MODULE_CALIBRATION_CONTROL
                    if value.startswith("control__")
                    else config.MODULE_AUDIT_RELIABILITY
                )
            )
            parameters["analysis_tier"] = parameters["route_id"].astype(str).map(
                lambda value: (
                    "appendix"
                    if value == "control__nonlinear_monotone"
                    else "primary"
                )
            )
            parameters = _add_global_metadata(
                parameters,
                run_context,
                module_id=None,
                analysis_tier=None,
                seed_column="replication_id",
            )
            parameter_writer.write(parameters)
            raw_records.extend(result["raw_records"])
            calibrated_records.extend(result["calibrated_records"])
            population_target_records.extend(result["population_target_records"])
            control_records.extend(result["control_records"])
            path_manifest_records.append(result["trajectory_manifest_record"])

    print("[3/6] Aggregate Monte Carlo estimators and evidence support")
    raw_estimates = _add_global_metadata(
        pd.DataFrame(raw_records),
        run_context,
        module_id=config.MODULE_AUDIT_RELIABILITY,
        analysis_tier="primary",
        seed_column="replication_id",
    )
    calibrated_estimates = _add_global_metadata(
        pd.DataFrame(calibrated_records),
        run_context,
        module_id=config.MODULE_AUDIT_RELIABILITY,
        analysis_tier="primary",
        seed_column="replication_id",
    )
    population_targets = _add_global_metadata(
        pd.DataFrame(population_target_records),
        run_context,
        module_id=config.MODULE_AUDIT_RELIABILITY,
        analysis_tier="primary",
        seed_column="replication_id",
    )
    control_estimates = _add_global_metadata(
        pd.DataFrame(control_records),
        run_context,
        module_id=config.MODULE_CALIBRATION_CONTROL,
        seed_column="replication_id",
    )
    raw_estimates.to_csv(derived_dir / "exp4_raw_estimates.csv", index=False)
    calibrated_estimates.to_csv(
        derived_dir / "exp4_calibrated_estimates.csv", index=False
    )
    population_targets.to_csv(
        derived_dir / "exp4_population_targets.csv", index=False
    )
    control_estimates.to_csv(
        derived_dir / "exp4_calibration_control_replication_level.csv", index=False
    )
    audit_summary = summarize_audit_conditions(
        raw_estimates,
        calibrated_estimates,
        int(settings["bootstrap_replications"]),
    )
    audit_summary = _add_global_metadata(
        audit_summary,
        run_context,
        module_id=config.MODULE_AUDIT_RELIABILITY,
        analysis_tier="primary",
    )
    audit_summary.to_csv(
        derived_dir / "exp4_audit_condition_summary.csv", index=False
    )
    support_summary = summarize_effective_support(raw_estimates)
    support_summary = _add_global_metadata(
        support_summary,
        run_context,
        module_id=config.MODULE_AUDIT_RELIABILITY,
        analysis_tier="primary",
    )
    support_summary.to_csv(
        derived_dir / "exp4_effective_support_summary.csv", index=False
    )
    control_summary = summarize_calibration_controls(
        control_estimates,
        int(settings["bootstrap_replications"]),
    )
    control_summary = _add_global_metadata(
        control_summary,
        run_context,
        module_id=config.MODULE_CALIBRATION_CONTROL,
    )
    control_summary.to_csv(
        derived_dir / "exp4_calibration_control_summary.csv", index=False
    )

    print("[4/6] Write path manifests and frozen run records")
    path_manifest = _add_global_metadata(
        pd.DataFrame(path_manifest_records),
        run_context,
        module_id="structural_trajectory",
        analysis_tier="reproducibility",
        seed_column="seed_or_replication",
    )
    path_manifest.to_csv(
        run_context.run_dir / "logs" / "exp4_path_manifest.csv", index=False
    )
    write_json(
        {
            "experiment_id": config.EXPERIMENT_ID,
            "result_schema": config.RESULT_SCHEMA,
            "legacy_schema_blocked": config.LEGACY_RESULT_SCHEMA,
            "paper_result": False,
            "run_tier": run_context.run_tier,
        },
        run_context.run_dir / "logs" / "exp4_result_status.json",
    )

    print("Derived data complete")
    return {
        "seed_level": derived_dir / "exp4_route_boundary_seed_level.parquet",
        "route_boundary_summary": derived_dir / "exp4_route_boundary_summary.csv",
        "audit_summary": derived_dir / "exp4_audit_condition_summary.csv",
        "support_summary": derived_dir / "exp4_effective_support_summary.csv",
        "control_summary": derived_dir / "exp4_calibration_control_summary.csv",
        "raw_estimates": derived_dir / "exp4_raw_estimates.csv",
        "calibrated_estimates": derived_dir / "exp4_calibrated_estimates.csv",
        "population_targets": derived_dir / "exp4_population_targets.csv",
    }
