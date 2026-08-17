"""Canonical CLI for Exp4 v3. No command performs paper promotion implicitly."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from exp4.configuration.schema import EXPERIMENT_DISPLAY_NAME
from exp4.outputs.manifests import write_output_manifest
from exp4.outputs.writers import (
    create_run_context,
    exp4_worktree_clean,
    git_commit_available,
    load_run_context,
    write_json,
)
from exp4.pipeline import (
    aggregate_existing_run,
    render_existing_run,
    run_pipeline,
)
from exp4.reporting.implementation_status import write_implementation_status
from exp4.reporting.run_summary import write_run_summary
from exp4.simulation.calibration import load_proxy_route_calibration
from exp4.validation.runner import validate_run
from exp4.validation.run_provenance import (
    Exp4ReuseDecision,
    audit_run_provenance,
    record_downstream_rebuild,
    write_provenance_reconciliation,
)


BASE_DIR = Path(__file__).resolve().parent


def _default_jobs() -> int:
    return max(1, min(os.cpu_count() or 1, 8))


def _existing_context(run_dir: Path, n_jobs: int | None):
    return load_run_context(BASE_DIR, run_dir.resolve(), n_jobs=n_jobs)


def _refuse_dirty_full_worktree() -> None:
    """Formal Full must start from a clean, committed Exp4 worktree."""
    _assert_full_worktree_ready(BASE_DIR)


def _assert_full_worktree_ready(base_dir: Path) -> None:
    from exp4.outputs.writers import exp4_dirty_files

    if not exp4_worktree_clean(base_dir):
        dirty = exp4_dirty_files(base_dir)
        details = "\n".join(dirty) if dirty else "(git status unavailable)"
        raise SystemExit(
            "FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE\n"
            "Formal Full requires a clean Exp4 worktree. Dirty files:\n"
            f"{details}\n"
            "Fast and Middle may run on a dirty worktree and record "
            "exp4_worktree_clean_at_start=false."
        )
    if not git_commit_available(base_dir):
        raise SystemExit(
            "FORMAL_FULL_REFUSED_UNRESOLVABLE_GIT_COMMIT\n"
            "Formal Full requires a resolvable, non-placeholder git commit."
        )


def _selective_rebuild(context, rebuild: str) -> dict[str, object]:
    """Rebuild only downstream Exp4 stages after an explicit reuse audit."""
    audit = audit_run_provenance(context.run_dir, BASE_DIR)
    if not audit["simulation_reuse_eligible"]:
        raise SystemExit(
            "EXP4_SELECTIVE_REBUILD_REFUSED\n"
            f"reason={audit['paper_audit_failure_reason']}\n"
            "A scientific full rerun is required only when the simulation/config/"
            "calibration contract changed."
        )
    required = str(audit["required_action"])
    if rebuild == "reporting" and required == Exp4ReuseDecision.DOWNSTREAM_REBUILD.value:
        raise SystemExit("EXP4_SELECTIVE_REBUILD_REFUSED: aggregation or validation is stale; use downstream")
    if rebuild == "validation" and not audit["stages"]["aggregation"]["hash_match"]:
        raise SystemExit("EXP4_SELECTIVE_REBUILD_REFUSED: aggregation is stale; use aggregation or downstream")

    rebuilt: list[str] = []
    calibration_path = (
        context.run_dir
        / "derived"
        / "calibration"
        / "exp4_proxy_route_calibration.json"
    )
    if rebuild in {"aggregation", "downstream"}:
        aggregate_existing_run(context, load_proxy_route_calibration(calibration_path))
        rebuilt.append("aggregation")
    if rebuild in {"reporting", "downstream"}:
        render_existing_run(context)
        write_run_summary(context.run_dir)
        rebuilt.append("reporting")
    if rebuild in {"validation", "aggregation", "reporting", "downstream"}:
        engineering, scientific = validate_run(context.run_dir)
        if engineering["status"] != "PASS" or scientific["status"] != "PASS":
            raise SystemExit("EXP4_SELECTIVE_REBUILD_VALIDATION_FAILED")
        rebuilt.append("validation")

    rebuilt_stages = tuple(rebuilt)
    record_downstream_rebuild(context.run_dir, BASE_DIR, rebuilt_stages)
    reconciliation = write_provenance_reconciliation(
        context.run_dir, BASE_DIR, rebuilt_stages, pre_rebuild_audit=audit
    )
    write_output_manifest(context.run_dir)
    after = audit_run_provenance(context.run_dir, BASE_DIR)
    return {
        "run_id": context.run_id,
        "rebuilt_stages": rebuilt,
        "reconciliation": str(reconciliation),
        "before": audit,
        "after": after,
    }
def main() -> None:
    parser = argparse.ArgumentParser(description=EXPERIMENT_DISPLAY_NAME)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for tier in ("fast", "middle", "full"):
        command = subparsers.add_parser(tier)
        command.add_argument("--n-jobs", type=int, default=_default_jobs())
        command.add_argument("--resume-run-dir", type=Path, default=None)
    for command_name in (
        "validate",
        "aggregate",
        "plot",
        "tables",
        "report",
        "provenance",
        "reconcile",
    ):
        command = subparsers.add_parser(command_name)
        command.add_argument("--run-dir", type=Path, required=True)
        command.add_argument("--n-jobs", type=int, default=None)
        if command_name == "reconcile":
            command.add_argument(
                "--rebuild",
                choices=("validation", "aggregation", "reporting", "downstream"),
                required=True,
            )
    subparsers.add_parser("status")
    arguments = parser.parse_args()

    if arguments.command == "status":
        status = write_implementation_status(
            BASE_DIR, BASE_DIR / "reports" / "EXP4_V3_IMPLEMENTATION_STATUS.md"
        )
        print(json.dumps(status, indent=2, default=str))
        return

    if arguments.command == "provenance":
        context = _existing_context(arguments.run_dir, arguments.n_jobs)
        audit = audit_run_provenance(context.run_dir, BASE_DIR, recompute_calibration=True)
        write_json(audit, context.run_dir / "logs" / "exp4_provenance_audit.json")
        print(json.dumps(audit, indent=2, default=str))
        return

    if arguments.command in {"fast", "middle", "full"}:
        if arguments.command == "full":
            _refuse_dirty_full_worktree()
        if arguments.resume_run_dir is not None:
            context = _existing_context(arguments.resume_run_dir, arguments.n_jobs)
            if context.run_tier != arguments.command:
                raise SystemExit(
                    f"Resume tier mismatch: run={context.run_tier}, command={arguments.command}"
                )
            if arguments.command == "full":
                _refuse_dirty_full_worktree()
            resume = True
        else:
            context = create_run_context(BASE_DIR, arguments.command, arguments.n_jobs)
            resume = False
        print("EXP4 V3 ROUTE ALIGNMENT AND EVIDENCE-QUALIFIED AUDIT")
        print(f"Run ID: {context.run_id}")
        print(f"Run tier: {context.run_tier}")
        print(f"Workers: {context.n_jobs}")
        print(f"Output: {context.run_dir}")
        print(f"Exp4 worktree clean at start: {context.exp4_worktree_clean_at_start}")
        status = run_pipeline(context, BASE_DIR, resume=resume)
        print(json.dumps(status, indent=2))
        if status["engineering_status"] != "PASS" or status["scientific_status"] != "PASS":
            raise SystemExit(1)
        return

    context = _existing_context(arguments.run_dir, arguments.n_jobs)
    if arguments.command == "reconcile":
        print(json.dumps(_selective_rebuild(context, arguments.rebuild), indent=2))
        return
    calibration_path = (
        context.run_dir
        / "derived"
        / "calibration"
        / "exp4_proxy_route_calibration.json"
    )
    del calibration_path
    compatibility_modes = {
        "validate": "validation",
        "aggregate": "aggregation",
        "plot": "reporting",
        "tables": "reporting",
        "report": "reporting",
    }
    result = _selective_rebuild(context, compatibility_modes[arguments.command])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
