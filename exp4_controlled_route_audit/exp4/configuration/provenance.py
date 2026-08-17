"""Stage-specific configuration identities for Exp4 provenance."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any

from exp4.configuration.parameters import (
    CALIBRATION,
    MODULE_A,
    MODULE_B,
    REPORTING,
    SHARED_DGP,
)
from exp4.configuration.registries import (
    AUDIT_DESIGN_ORDER,
    AUDIT_DESIGN_REGISTRY,
    CONTROL_ORDER,
    CONTROL_REGISTRY,
    ROUTE_ORDER,
    ROUTE_REGISTRY,
)
from exp4.configuration.run_modes import RunModeSettings, mode_settings
from exp4.configuration.schema import (
    APPENDIX_FIGURE_IDS,
    EXPERIMENT_DISPLAY_NAME,
    EXPERIMENT_ID,
    MAIN_FIGURE_ID,
    MAIN_TABLE_ID,
    RESULT_SCHEMA,
    SCIENTIFIC_CONTRACT_VERSION,
)

STAGE_CONFIG_HASH_ALGORITHM_VERSION = "exp4-stage-config-v1"


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _without_display_names(registry: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {field: value for field, value in entry.items() if field != "display_name"}
        for key, entry in registry.items()
    }


def scientific_config_payload(
    run_tier: str = "full",
    *,
    shared_dgp: Any = SHARED_DGP,
    module_a: Any = MODULE_A,
    module_b: Any = MODULE_B,
    calibration: Any = CALIBRATION,
    settings: RunModeSettings | None = None,
    route_order: tuple[str, ...] = ROUTE_ORDER,
    route_registry: dict[str, dict[str, Any]] = ROUTE_REGISTRY,
    audit_design_order: tuple[str, ...] = AUDIT_DESIGN_ORDER,
    audit_design_registry: dict[str, dict[str, Any]] = AUDIT_DESIGN_REGISTRY,
    control_order: tuple[str, ...] = CONTROL_ORDER,
    scientific_contract_version: str = SCIENTIFIC_CONTRACT_VERSION,
    raw_pairwise_discrepancy_epsilon: float = REPORTING.raw_pairwise_discrepancy_epsilon,
) -> dict[str, Any]:
    selected = settings or mode_settings(run_tier)
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "simulation",
        "run_tier": run_tier,
        "scientific_contract_version": scientific_contract_version,
        "parameters": {
            "shared_dgp": asdict(shared_dgp),
            "module_a": asdict(module_a),
            "module_b": asdict(module_b),
            "calibration": asdict(calibration),
            "raw_pairwise_discrepancy_epsilon": raw_pairwise_discrepancy_epsilon,
        },
        "run_mode": {
            "module_a_seed_count": selected.module_a_seed_count,
            "module_b_replications": selected.module_b_replications,
        },
        "route_order": list(route_order),
        "route_registry_semantics": _without_display_names(route_registry),
        "audit_design_order": list(audit_design_order),
        "audit_design_registry_semantics": _without_display_names(
            audit_design_registry
        ),
        "control_order": list(control_order),
    }


def scientific_config_hash(run_tier: str = "full", **kwargs: Any) -> str:
    return _hash_payload(scientific_config_payload(run_tier, **kwargs))


def aggregation_config_payload(
    run_tier: str = "full",
    *,
    settings: RunModeSettings | None = None,
    confidence_level: float = REPORTING.confidence_level,
    bootstrap_seed: int = REPORTING.bootstrap_seed,
) -> dict[str, Any]:
    selected = settings or mode_settings(run_tier)
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "aggregation",
        "run_tier": run_tier,
        "bootstrap_replications": selected.bootstrap_replications,
        "confidence_level": confidence_level,
        "bootstrap_seed": bootstrap_seed,
    }


def aggregation_config_hash(run_tier: str = "full", **kwargs: Any) -> str:
    return _hash_payload(aggregation_config_payload(run_tier, **kwargs))


def validation_config_payload(
    *,
    zero_defect_tolerance: float = REPORTING.zero_defect_tolerance,
    route_audit_correlation_tolerance: float = REPORTING.route_audit_correlation_tolerance,
) -> dict[str, Any]:
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "validation",
        "zero_defect_tolerance": zero_defect_tolerance,
        "route_audit_correlation_tolerance": route_audit_correlation_tolerance,
    }


def validation_config_hash(**kwargs: Any) -> str:
    return _hash_payload(validation_config_payload(**kwargs))


def reporting_config_payload(
    *,
    experiment_display_name: str = EXPERIMENT_DISPLAY_NAME,
    main_figure_id: str = MAIN_FIGURE_ID,
    main_table_id: str = MAIN_TABLE_ID,
    appendix_figure_ids: tuple[str, ...] = APPENDIX_FIGURE_IDS,
    route_registry: dict[str, dict[str, Any]] = ROUTE_REGISTRY,
    audit_design_registry: dict[str, dict[str, Any]] = AUDIT_DESIGN_REGISTRY,
    control_registry: dict[str, dict[str, Any]] = CONTROL_REGISTRY,
    paper_figure_width_in: float = REPORTING.paper_figure_width_in,
    paper_figure_height_in: float = REPORTING.paper_figure_height_in,
    paper_dpi: int = REPORTING.paper_dpi,
) -> dict[str, Any]:
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "reporting",
        "experiment_display_name": experiment_display_name,
        "figure_ids": {
            "main": main_figure_id,
            "appendix": list(appendix_figure_ids),
        },
        "table_ids": {"main": main_table_id},
        "route_registry": route_registry,
        "audit_design_registry": audit_design_registry,
        "control_registry": control_registry,
        "figure_style": {
            "width_in": paper_figure_width_in,
            "height_in": paper_figure_height_in,
            "dpi": paper_dpi,
        },
    }


def reporting_config_hash(**kwargs: Any) -> str:
    return _hash_payload(reporting_config_payload(**kwargs))


def artifact_metadata_config_payload(
    *, result_schema: str = RESULT_SCHEMA
) -> dict[str, Any]:
    return {
        "algorithm_version": STAGE_CONFIG_HASH_ALGORITHM_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "stage": "artifact_metadata",
        "result_schema": result_schema,
    }


def artifact_metadata_config_hash(**kwargs: Any) -> str:
    return _hash_payload(artifact_metadata_config_payload(**kwargs))


def stage_config_hashes(run_tier: str = "full") -> dict[str, str]:
    return {
        "scientific_config_hash": scientific_config_hash(run_tier),
        "aggregation_config_hash": aggregation_config_hash(run_tier),
        "validation_config_hash": validation_config_hash(),
        "reporting_config_hash": reporting_config_hash(),
        "artifact_metadata_config_hash": artifact_metadata_config_hash(),
    }


__all__ = [
    "STAGE_CONFIG_HASH_ALGORITHM_VERSION",
    "aggregation_config_hash",
    "aggregation_config_payload",
    "artifact_metadata_config_hash",
    "artifact_metadata_config_payload",
    "reporting_config_hash",
    "reporting_config_payload",
    "scientific_config_hash",
    "scientific_config_payload",
    "stage_config_hashes",
    "validation_config_hash",
    "validation_config_payload",
]
