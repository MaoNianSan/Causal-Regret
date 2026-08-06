from __future__ import annotations

import json
from pathlib import Path

from contracts import SCHEMA_VERSION, ConfigurationError, DataContractError, ScientificInvariantError

from ..cohort import build_primary_cohort
from ..raw_data import load_config, prepare_raw_log, write_json
from ..validation import validate_frozen_configuration
from .context import now_local, write_csv


def run_cohort_check(
    *,
    config_path: str | Path | None = None,
    input_path: str | Path | None = None,
) -> int:
    """Run only the route-independent real-data cohort gate."""
    project_root = Path(__file__).resolve().parents[2]
    config_file = Path(config_path) if config_path is not None else project_root / "config.yaml"
    config = load_config(config_file)
    validate_frozen_configuration(config)
    resolved_input = Path(input_path) if input_path is not None else project_root / str(config["input"]["raw_file"])
    check_id = f"cohort-check-{now_local().strftime('%Y%m%dT%H%M%S%z')}"
    output_root = project_root / "outputs" / check_id
    output_root.mkdir(parents=True, exist_ok=False)
    try:
        prepared = prepare_raw_log(resolved_input, config, mode="full", progress=True)
        primary = build_primary_cohort(prepared.candidates, prepared.impression_counts, config)
        robustness_counts: dict[str, dict[str, int | float]] = {}
        for window in config["cohort"].get("robustness_candidate_window_days", []):
            window_config = dict(config)
            window_config["cohort"] = dict(config["cohort"])
            window_config["cohort"]["analysis_window_days"] = int(window)
            cohort = build_primary_cohort(prepared.candidates, prepared.impression_counts, window_config)
            retained = cohort.journey_manifest.loc[cohort.journey_manifest["is_primary_eligible"]]
            robustness_counts[str(window)] = {
                "retained_journeys": int(len(retained)),
                "retained_uids": int(retained["user_id"].nunique()),
                "eligible_cells": int(len(cohort.decision_cell_universe)),
                "ambiguity_rate": float(cohort.audit.get("ambiguous_journey_rate", 0.0)),
            }
        primary_retained = primary.journey_manifest.loc[primary.journey_manifest["is_primary_eligible"]]
        status = {
            "schema_version": SCHEMA_VERSION,
            "cohort_check_status": "PASS",
            "primary_7d_retained_journeys": int(len(primary_retained)),
            "primary_7d_retained_uids": int(primary_retained["user_id"].nunique()),
            "primary_7d_eligible_cells": int(len(primary.decision_cell_universe)),
            "primary_7d_ambiguity_rate": float(primary.audit.get("ambiguous_journey_rate", 0.0)),
            "robustness_windows": robustness_counts,
            "temporal_coverage_status": "PASS",
            "full_exp2_rerun_allowed": True,
        }
        write_json(status, output_root / "cohort_check_status.json")
        write_csv(primary.cohort_flow, output_root / "cohort_flow.csv")
        write_json(prepared.audit, output_root / "raw_input_audit.json")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    except (ConfigurationError, DataContractError, ScientificInvariantError) as exc:
        status = {
            "schema_version": SCHEMA_VERSION,
            "cohort_check_status": "STOP_AND_REVIEW",
            "full_exp2_rerun_allowed": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        write_json(status, output_root / "cohort_check_status.json")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 1
