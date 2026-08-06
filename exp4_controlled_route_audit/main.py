"""Canonical CLI for Exp4 v2. No command performs paper promotion implicitly."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from exp4.configuration.schema import EXPERIMENT_DISPLAY_NAME
from exp4.outputs.manifests import write_output_manifest
from exp4.outputs.writers import create_run_context, load_run_context
from exp4.pipeline import (
    aggregate_existing_run,
    render_existing_run,
    run_pipeline,
)
from exp4.reporting.implementation_status import write_implementation_status
from exp4.reporting.run_summary import write_run_summary
from exp4.simulation.calibration import load_proxy_route_calibration
from exp4.validation.runner import validate_run
from exp4.validation.run_provenance import audit_run_provenance, write_stage_provenance_record


BASE_DIR = Path(__file__).resolve().parent


def _default_jobs() -> int:
    return max(1, min(os.cpu_count() or 1, 8))


def _existing_context(run_dir: Path, n_jobs: int | None):
    return load_run_context(BASE_DIR, run_dir.resolve(), n_jobs=n_jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description=EXPERIMENT_DISPLAY_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for tier in ("fast", "middle", "full"):
        command = subparsers.add_parser(tier)
        command.add_argument("--n-jobs", type=int, default=_default_jobs())
        command.add_argument("--resume-run-dir", type=Path, default=None)
    for command_name in ("validate", "aggregate", "plot", "tables", "report", "provenance"):
        command = subparsers.add_parser(command_name)
        command.add_argument("--run-dir", type=Path, required=True)
        command.add_argument("--n-jobs", type=int, default=None)
    subparsers.add_parser("status")
    arguments = parser.parse_args()

    if arguments.command == "status":
        status = write_implementation_status(
            BASE_DIR, BASE_DIR / "reports" / "EXP4_V2_IMPLEMENTATION_STATUS.md"
        )
        print(json.dumps(status, indent=2, default=str))
        return

    if arguments.command == "provenance":
        context = _existing_context(arguments.run_dir, arguments.n_jobs)
        audit = audit_run_provenance(context.run_dir, BASE_DIR)
        from exp4.outputs.writers import write_json

        write_json(audit, context.run_dir / "logs" / "exp4_provenance_audit.json")
        print(json.dumps(audit, indent=2, default=str))
        return

    if arguments.command in {"fast", "middle", "full"}:
        if arguments.resume_run_dir is not None:
            context = _existing_context(arguments.resume_run_dir, arguments.n_jobs)
            if context.run_tier != arguments.command:
                raise SystemExit(
                    f"Resume tier mismatch: run={context.run_tier}, command={arguments.command}"
                )
            resume = True
        else:
            context = create_run_context(BASE_DIR, arguments.command, arguments.n_jobs)
            resume = False
        print("EXP4 V2 ROUTE ALIGNMENT AND EVIDENCE-QUALIFIED AUDIT")
        print(f"Run ID: {context.run_id}")
        print(f"Run tier: {context.run_tier}")
        print(f"Workers: {context.n_jobs}")
        print(f"Output: {context.run_dir}")
        status = run_pipeline(context, BASE_DIR, resume=resume)
        print(json.dumps(status, indent=2))
        if status["engineering_status"] != "PASS" or status["scientific_status"] != "PASS":
            raise SystemExit(1)
        return

    context = _existing_context(arguments.run_dir, arguments.n_jobs)
    calibration_path = (
        context.run_dir
        / "derived"
        / "calibration"
        / "exp4_proxy_route_calibration.json"
    )
    if arguments.command == "validate":
        engineering, scientific = validate_run(context.run_dir)
        print(json.dumps({"engineering": engineering["status"], "scientific": scientific["status"]}, indent=2))
        if engineering["status"] != "PASS" or scientific["status"] != "PASS":
            raise SystemExit(1)
    elif arguments.command == "aggregate":
        aggregate_existing_run(context, load_proxy_route_calibration(calibration_path))
    elif arguments.command in {"plot", "tables"}:
        render_existing_run(context)
    elif arguments.command == "report":
        write_run_summary(context.run_dir)
    write_stage_provenance_record(context.run_dir, BASE_DIR)
    write_output_manifest(context.run_dir)


if __name__ == "__main__":
    main()
