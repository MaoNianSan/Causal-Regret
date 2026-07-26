"""Static code-contract checks for Exp4."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from io_utils import write_json


def run(root: Path, run_dir: Path | None = None) -> dict[str, Any]:
    python_files = sorted(path for path in root.glob("*.py") if path.name != "code_check.py")
    source = "\n".join(path.read_text(encoding="utf-8") for path in python_files)
    plot_source = (root / "plot_results.py").read_text(encoding="utf-8")
    engine_source = (root / "engine.py").read_text(encoding="utf-8")
    main_source = (root / "main.py").read_text(encoding="utf-8") if (root / "main.py").exists() else ""
    checks = [
        ("experiment_id_normalized", config.EXPERIMENT_ID == "exp4_controlled_route_audit"),
        ("result_schema_normalized", config.RESULT_SCHEMA == "exp4_controlled_route_audit_v1"),
        ("route_ids_frozen", all(route in config.ROUTE_REGISTRY for route in config.ROUTE_ORDER)),
        ("structural_and_realized_fields_present", "structural_loss_map" in source and "realized_potential_feedback" in source),
        ("route_map_layer_present", (root / "route_maps.py").exists() and "construct_proxy_label_route" in source),
        ("audit_layer_present", (root / "audit_engine.py").exists() and "fit_cross_fitted_calibration" in source),
        ("independent_stream_names_present", "route_label_stream" in source and "audit_mcar_stream" in source and "audit_biased_stream" in source),
        ("extended_clock_present", "clock_horizon = decision_horizon +" in source),
        ("legacy_task_names_removed_from_active_python", all(term not in source for term in ["source_label_sweep", "phase_grid", "delay_coupling"])),
        ("arrival_naive_id_removed", "arrival_time_naive" not in source),
        ("impossibility_id_removed", "proxy_sufficiency_impossibility" not in source),
        ("full_does_not_auto_promote", "paper_result=true" not in main_source.lower() and "promote_results" not in main_source),
        ("plotting_reads_derived_only", "compute_action_gap_defect" not in plot_source and "construct_proxy_label_route" not in plot_source),
        ("parquet_dependency_explicit", "pyarrow" in (root / "requirements.txt").read_text(encoding="utf-8")),
        ("clean_is_independent", (root / "clean.py").exists() and "clean" not in main_source.lower()),
        ("zero_value_markers_present", "_bar_with_zero_markers" in plot_source),
        (
            "portable_run_manifest_paths",
            "trajectory_file\": output_path.relative_to(run_dir)" in source
            and "route_map_file\": route_map_path.relative_to(run_dir)" in engine_source,
        ),
    ]
    payload = {
        "check_type": "static_code_contract",
        "status": "PASS" if all(ok for _, ok in checks) else "FAIL",
        "checks": [
            {"check_name": name, "status": "PASS" if ok else "FAIL"}
            for name, ok in checks
        ],
    }
    if run_dir is not None:
        write_json(payload, run_dir / "checks" / "exp4_code_check.json")
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    arguments = parser.parse_args()
    result = run(config.BASE_DIR, arguments.run_dir)
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)
