"""Selective Exp1 rebuilds that reuse a verified scientific source run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main import OUTPUTS_DIR, PROJECT_ROOT, load_frozen_calibration
from plot_appendix import generate_all as generate_appendix_figures
from plot_main import generate as generate_main_figure
from self_check import run_checks
from src.artifact_io import refresh_output_manifest
from src.derived import rebuild_derived_from_scientific_artifacts
from src.run_provenance import (
    Exp1ReuseDecision,
    audit_exp1_provenance,
    bootstrap_existing_full_provenance,
    migrate_scientific_execution_contract,
    migrate_stage_config_provenance,
    record_exp1_reconciliation,
)
from targeted import execute as execute_targeted_validation


def _run_tier_for(source_run: Path) -> str:
    try:
        relative = source_run.resolve().relative_to(OUTPUTS_DIR.resolve())
    except ValueError as exc:
        raise RuntimeError("source run must be inside exp1_alignment_transfer/outputs") from exc
    if len(relative.parts) != 1 or relative.name not in {"fast", "full"}:
        raise RuntimeError("source run must be outputs/fast or outputs/full")
    return relative.name


def _relative_paths(source_run: Path, paths: list[Path]) -> list[str]:
    return [
        str(path.relative_to(source_run)).replace("\\", "/") for path in paths
    ]


def _rebuild_aggregation(source_run: Path, run_tier: str) -> list[str]:
    result = rebuild_derived_from_scientific_artifacts(source_run, run_tier)
    return _relative_paths(source_run, list(result["artifacts"].values()))


def _rebuild_validation(source_run: Path, run_tier: str) -> list[str]:
    run_checks(run_tier)
    targeted_dir = execute_targeted_validation(run_tier, force=True)
    required = [
        source_run / "checks" / "exp1_validation_report.json",
        targeted_dir / "exp1_targeted_validation_report.json",
        targeted_dir / "exp1_targeted_mean_delay_seed_metrics.csv",
        targeted_dir / "exp1_targeted_mean_delay_summary.csv",
        targeted_dir / "exp1_targeted_horizon_seed_metrics.csv",
        targeted_dir / "exp1_targeted_horizon_summary.csv",
        targeted_dir / "exp1_targeted_theory_exact_shift_sweep.csv",
        targeted_dir / "exp1_targeted_theory_margin_threshold_sweep.csv",
        targeted_dir / "fig_exp1_targeted_validation_data.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Validation reconciliation missing artifacts: {missing}")
    targeted_report = json.loads(
        (targeted_dir / "exp1_targeted_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    if targeted_report.get("status") != "PASS":
        raise RuntimeError("Targeted validation reconciliation did not PASS")
    return _relative_paths(source_run, required)


def _rebuild_reporting(source_run: Path, run_tier: str) -> list[str]:
    generate_main_figure(run_tier)
    generate_appendix_figures(run_tier)
    reporting = [
        path
        for directory in (
            source_run / "figures" / "png",
            source_run / "figures" / "pdf",
            source_run / "figures" / "metadata",
        )
        for path in sorted(directory.glob("*"))
        if path.is_file()
    ]
    return _relative_paths(source_run, reporting)


def reconcile(source_run: Path, rebuild: str) -> dict[str, object]:
    run_tier = _run_tier_for(source_run)
    before = audit_exp1_provenance(source_run, PROJECT_ROOT)
    if not before["scientific_reuse_eligible"]:
        raise RuntimeError(
            "Exp1 selective rebuild refused: " + str(before["failure_reason"])
        )

    required = before["decision"]
    if rebuild == "reporting" and required in {
        Exp1ReuseDecision.DOWNSTREAM_REBUILD.value,
        Exp1ReuseDecision.VALIDATION_REBUILD.value,
    }:
        raise RuntimeError("Validation or aggregation is stale; use the required rebuild")
    if rebuild == "validation" and required == Exp1ReuseDecision.DOWNSTREAM_REBUILD.value:
        if not before["stage_hash_matches"]["aggregation_source_hash"]:
            raise RuntimeError("Aggregation is stale; use --rebuild aggregation or downstream")

    rebuilt: list[str] = []
    rebuilt_artifacts: dict[str, list[str]] = {}
    if rebuild in {"aggregation", "downstream"}:
        rebuilt_artifacts["aggregation"] = _rebuild_aggregation(source_run, run_tier)
        rebuilt.append("aggregation")
    if rebuild in {"validation", "aggregation", "downstream"}:
        rebuilt_artifacts["validation"] = _rebuild_validation(source_run, run_tier)
        rebuilt.append("validation")
    if rebuild in {"reporting", "downstream"}:
        rebuilt_artifacts["reporting"] = _rebuild_reporting(source_run, run_tier)
        rebuilt.append("reporting")

    reconciliation = record_exp1_reconciliation(
        source_run, PROJECT_ROOT, rebuilt, rebuilt_artifacts
    )
    refresh_output_manifest(source_run)
    after = audit_exp1_provenance(source_run, PROJECT_ROOT)
    return {
        "source_run": str(source_run),
        "rebuilt_stages": rebuilt,
        "rebuilt_artifacts": rebuilt_artifacts,
        "reconciliation": str(reconciliation),
        "before": before,
        "after": after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild Exp1 downstream artifacts without rerunning simulation."
    )
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument(
        "--rebuild",
        choices=("validation", "aggregation", "reporting", "downstream"),
        default=None,
    )
    parser.add_argument(
        "--initialize-existing",
        action="store_true",
        help="write explicit historical provenance for a verified existing full run",
    )
    parser.add_argument("--audit", action="store_true")
    parser.add_argument(
        "--migrate-scientific-execution-contract",
        action="store_true",
        help="replay a fixed stored-full subset and migrate only the execution-contract hash",
    )
    parser.add_argument(
        "--migrate-stage-config-provenance",
        action="store_true",
        help="migrate a verified full from monolithic to stage-aware config identity",
    )
    args = parser.parse_args()
    source_run = args.source_run.resolve()
    _run_tier_for(source_run)

    if args.initialize_existing:
        lineage, stage = bootstrap_existing_full_provenance(source_run, PROJECT_ROOT)
        print(f"EXP1_PROVENANCE_INITIALIZED lineage={lineage} stage={stage}")
    if args.migrate_scientific_execution_contract:
        migration, payload = migrate_scientific_execution_contract(
            source_run, PROJECT_ROOT, load_frozen_calibration()
        )
        print(
            "EXP1_SCIENTIFIC_EXECUTION_CONTRACT_MIGRATED "
            f"equivalence={payload['scientific_equivalence']} artifact={migration}"
        )
    if args.migrate_stage_config_provenance:
        migration, payload = migrate_stage_config_provenance(source_run, PROJECT_ROOT)
        print(
            "EXP1_STAGE_CONFIG_PROVENANCE_MIGRATED "
            f"equivalence={payload['scientific_generation_equivalence']} "
            f"artifact={migration}"
        )
    if args.audit:
        print(json.dumps(audit_exp1_provenance(source_run, PROJECT_ROOT), indent=2))
    if args.rebuild:
        print(json.dumps(reconcile(source_run, args.rebuild), indent=2))
    if not any(
        (
            args.initialize_existing,
            args.migrate_scientific_execution_contract,
            args.migrate_stage_config_provenance,
            args.audit,
            args.rebuild,
        )
    ):
        parser.error("provide --initialize-existing, --audit, and/or --rebuild")


if __name__ == "__main__":
    main()
