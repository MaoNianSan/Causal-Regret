"""Independent engineering, scientific, and promotion checks for Exp3."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from artifact_integrity import verify_artifact_manifest
from code_version import code_version
from plot_appendix_results import plot_appendix_figures
from plot_main_results import plot_main_figure
from run_reporting import (
    calculate_final_engineering_status,
    readiness_fields,
    scientific_uncertainty_status,
    synchronize_run_outputs,
)
from self_check_contracts import (
    check_bootstrap,
    check_design_and_model,
    check_figures,
    check_full_preflight,
    check_input_and_time,
    check_metrics_and_routes,
    required_artifacts,
)
from self_check_helpers import add_check, load_json
from utilities import build_artifact_manifest, save_json


def write_self_check_outputs(
    output_dir: Path,
    manifest: dict[str, Any],
    result: dict[str, Any],
    rows: list[dict[str, object]],
) -> None:
    """Synchronize final self-check status across every public status carrier."""
    (output_dir / "checks").mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(rows)
    for key in (
        "pipeline_execution_status",
        "independent_self_check_status",
        "archival_integrity_check_status",
        "final_engineering_status",
        "scientific_contract_status",
        "scientific_uncertainty_status",
        "figure_data_contracts",
        "artifact_manifest_status",
    ):
        summary[key] = result[key]
    summary.to_csv(output_dir / "checks/exp3_self_check.csv", index=False)
    summary.to_csv(output_dir / "checks/exp3_self_check_summary.csv", index=False)
    save_json(result, output_dir / "checks/exp3_self_check.json")
    synchronize_run_outputs(output_dir, manifest)
    build_artifact_manifest(output_dir)


def _validate_self_check_inputs(output_dir: Path) -> dict[str, Path]:
    missing_processed = []
    for split_id in ("history", "evaluation"):
        base = output_dir / "processed" / f"exp3_{split_id}_events_with_targets"
        if not base.with_suffix(".parquet").exists() and not base.with_suffix(".csv").exists():
            missing_processed.append(split_id)
    if missing_processed:
        raise RuntimeError(
            "INDEPENDENT_SELF_CHECK_BLOCKED: event-level processed data are missing for "
            f"{missing_processed}. archival verification is not independent reconstruction."
        )
    artifacts = required_artifacts(output_dir)
    missing = [f"{key}={path}" for key, path in artifacts.items() if not path.exists()]
    if missing:
        raise RuntimeError("SELF_CHECK_BLOCKED: required artifacts are missing: " + "; ".join(missing))
    return artifacts


def _check_code_and_pipeline(
    rows: list[dict[str, object]],
    output_dir: Path,
    manifest: dict[str, Any],
    design: dict[str, Any],
) -> bool:
    artifact_ok, detail = verify_artifact_manifest(output_dir, archival=False)
    add_check(rows, "artifact_manifest_frozen_hashes", artifact_ok, detail, "engineering")
    current = code_version(Path(__file__).resolve().parent)
    figure_metadata = [
        load_json(path) for path in sorted((output_dir / "figures/metadata").glob("*.json"))
    ]
    version_ok = (
        manifest.get("code_version_type") == current["code_version_type"]
        and manifest.get("code_version") == current["code_version"]
        and design.get("code_version_type") == current["code_version_type"]
        and design.get("code_version") == current["code_version"]
        and bool(figure_metadata)
        and all(meta.get("code_version_type") == current["code_version_type"] for meta in figure_metadata)
        and all(meta.get("code_version") == current["code_version"] for meta in figure_metadata)
        and current["code_version"] != "unknown"
    )
    add_check(rows, "code_version_consistency", version_ok, current["code_version"], "engineering")
    completed = manifest.get("pipeline_execution_status", manifest.get("engineering_status")) == "PASS" and bool(manifest.get("completed_at_utc"))
    add_check(rows, "pipeline_completed", completed, str(manifest.get("pipeline_execution_status")), "engineering")
    return artifact_ok


def _check_run_tier(
    rows: list[dict[str, object]],
    manifest: dict[str, Any],
    design: dict[str, Any],
    config: dict[str, Any],
    artifacts: dict[str, Path],
) -> None:
    if str(manifest["run_tier"]) == "fast":
        add_check(rows, "fast_never_paper_result", manifest.get("paper_result") is False, "fast is never paper eligible", "paper")
        add_check(rows, "fast_scaled_support_declared", design.get("support_threshold_is_fast_scaled") is True, "fast support is scaled", "scientific")
        expected = "synthetic_fixture" if bool(manifest.get("synthetic_fixture")) else "original_kuairand_inputs"
        add_check(rows, "fast_input_declared", manifest.get("input_data_status") == expected, expected, "engineering")
        return
    add_check(rows, "full_threshold_frozen", int(design["support_min_events_per_fold"]) == int(config["support_min_events_per_fold_full"]), str(design["support_min_events_per_fold"]), "scientific")
    add_check(rows, "full_not_synthetic", manifest.get("synthetic_fixture") is False, "full uses KuaiRand", "paper")
    preflight = load_json(artifacts["full_preflight"])
    add_check(rows, "full_preflight_ready", preflight.get("full_design_support_ready") is True, str(preflight.get("status")), "scientific")


def run_self_check(output_dir: Path, promote_paper_result: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    artifacts = _validate_self_check_inputs(output_dir)
    manifest = load_json(artifacts["manifest"])
    config = load_json(artifacts["config"])
    design = load_json(artifacts["design"])
    split = load_json(artifacts["split_manifest"])
    model = load_json(artifacts["model_manifest"])
    bootstrap = load_json(artifacts["bootstrap"])
    rows: list[dict[str, object]] = []
    artifact_ok = _check_code_and_pipeline(rows, output_dir, manifest, design)
    check_input_and_time(rows, output_dir, manifest, config, split)
    check_design_and_model(rows, output_dir, design, model)
    support_status = check_metrics_and_routes(rows, output_dir)
    check_bootstrap(rows, output_dir, bootstrap)
    check_full_preflight(rows, output_dir, manifest)
    check_figures(rows, output_dir)
    _check_run_tier(rows, manifest, design, config, artifacts)

    engineering_pass = all(row["status"] == "PASS" for row in rows if row["category"] == "engineering")
    scientific_pass = all(row["status"] == "PASS" for row in rows if row["category"] == "scientific") and support_status == "PASS"
    contract_status = "PASS" if scientific_pass else support_status
    uncertainty_status = scientific_uncertainty_status(bootstrap)
    independent_status = "PASS" if engineering_pass and scientific_pass else "FAIL"
    run_tier = str(manifest["run_tier"])
    if run_tier == "full":
        scientific_status = contract_status if uncertainty_status == "SENSITIVITY_ONLY_ACCEPTED" else "FAIL"
    elif bool(manifest.get("synthetic_fixture")):
        scientific_status = "NOT_EVALUATED_FAST_FIXTURE"
    else:
        scientific_status = "NOT_EVALUATED_FAST_REAL"
    input_ids = {
        "timezone_rule", "interval_convention", "strict_temporal_split",
        "boundary_quarantine_within_frozen_limits", "boundary_quarantine_reported",
        "boundary_quarantine_summary_reconstruction", "history_target_window_contract",
        "evaluation_target_window_contract", "target_reuse_summary_reconstruction",
        "target_component_audit_reconstruction", "dependence_structure_disclosed",
    }
    figure_ids = {
        "main_figure_data_contract", "full_preflight_figure_data_contract",
        "dependence_figure_data_contract", "arrival_carrier_figure_data_contract",
        "figure_source_hash_contract",
    }
    input_status = "PASS" if all(row["status"] == "PASS" for row in rows if row["check_id"] in input_ids) else "FAIL"
    figure_status = "PASS" if all(row["status"] == "PASS" for row in rows if row["check_id"] in figure_ids) else "FAIL"
    manifest.update(
        {
            "independent_self_check_status": independent_status,
            "scientific_status": scientific_status,
            "scientific_contract_status": contract_status,
            "scientific_uncertainty_status": uncertainty_status,
            "input_audit_status": input_status,
            "figure_data_contract_status": figure_status,
            "figure_data_contracts": figure_status,
            "artifact_manifest_status": "PASS" if artifact_ok else "FAIL",
            "archival_integrity_check_status": "NOT_RUN",
            "paper_result": bool(manifest.get("paper_result", False)),
        }
    )
    manifest["final_engineering_status"] = calculate_final_engineering_status(manifest)
    manifest["engineering_status"] = manifest["final_engineering_status"]
    manifest.update(readiness_fields(manifest))
    paper_gate = bool(manifest["paper_promotion_eligible"])
    if promote_paper_result:
        if not paper_gate:
            raise RuntimeError("Paper promotion blocked: all full readiness gates are required.")
        manifest.update({"paper_result": True, "paper_status": "PASS"})
        plot_main_figure(output_dir, run_tier, paper_result=True)
        plot_appendix_figures(output_dir, run_tier, paper_result=True)
    result = {
        "pipeline_execution_status": manifest.get("pipeline_execution_status"),
        "independent_self_check_status": independent_status,
        "archival_integrity_check_status": manifest["archival_integrity_check_status"],
        "final_engineering_status": manifest["final_engineering_status"],
        "engineering_status": manifest["final_engineering_status"],
        "scientific_status": scientific_status,
        "scientific_contract_status": contract_status,
        "scientific_uncertainty_status": uncertainty_status,
        "formal_ci_validated": False,
        "figure_data_contracts": figure_status,
        "artifact_manifest_status": manifest["artifact_manifest_status"],
        "full_design_support_ready": bool(manifest.get("full_design_support_ready", False)),
        "full_run_recommended": bool(manifest.get("full_run_recommended", False)),
        "paper_promotion_eligible": paper_gate,
        "paper_result": bool(manifest.get("paper_result", False)),
        "code_version_type": manifest.get("code_version_type"),
        "code_version": manifest.get("code_version"),
        "checks": rows,
    }
    write_self_check_outputs(output_dir, manifest, result, rows)
    for key in (
        "pipeline_execution_status", "independent_self_check_status",
        "archival_integrity_check_status", "final_engineering_status",
        "scientific_status", "scientific_contract_status", "scientific_uncertainty_status",
    ):
        print(f"{key}={result[key]}")
    for key in ("full_design_support_ready", "full_run_recommended", "paper_promotion_eligible", "paper_result"):
        print(f"{key}={str(result[key]).lower()}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "full"], required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--promote-paper-result", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.output_dir is not None and args.run_id is not None:
        raise SystemExit("Use only one of --output-dir and --run-id.")
    if args.output_dir is not None:
        selected = args.output_dir
    elif args.run_id is not None:
        from runner import resolve_run_id

        selected = resolve_run_id(root, args.run_id, args.mode)
    else:
        from runner import resolve_latest_completed_run

        selected = resolve_latest_completed_run(root, args.mode)
    run_self_check(selected, promote_paper_result=args.promote_paper_result)


if __name__ == "__main__":
    main()
