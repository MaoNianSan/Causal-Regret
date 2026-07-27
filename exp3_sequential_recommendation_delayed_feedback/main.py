"""Command-line entry point for Experiment 3."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from artifact_integrity import create_archival_package, verify_archival_package
from input_audit import audit_inputs
from runner import (
    new_run_id,
    resolve_latest_audited_pass_run,
    resolve_latest_completed_run,
    resolve_latest_resumable_run,
    resolve_run_id,
    run_pipeline,
)
from self_check import run_self_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exp3 proxy score--gap--ranking recovery")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("fast", "full"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--input-root", type=Path, default=None)
        sub.add_argument("--output-dir", type=Path, default=None)
        sub.add_argument("--n-jobs", type=int, default=1)
        sub.add_argument("--clean-output", action="store_true")
        sub.add_argument(
            "--resume-bootstrap",
            action="store_true",
            help="Resume deterministic bootstrap draws in an existing run directory",
        )
        if command == "fast":
            sub.add_argument(
                "--synthetic-fixture",
                action="store_true",
                help=(
                    "Run the deterministic software fixture explicitly. Without this flag, "
                    "fast uses the frozen KuaiRand inputs and hard-fails when they are absent."
                ),
            )
        sub.add_argument("--debug", action="store_true")
    check = subparsers.add_parser("self-check")
    check.add_argument("--mode", choices=["fast", "full"], required=True)
    check.add_argument("--output-dir", type=Path, default=None)
    check.add_argument("--run-id", default=None)
    check.add_argument("--promote-paper-result", action="store_true")
    check.add_argument("--debug", action="store_true")
    audit = subparsers.add_parser("audit-inputs")
    audit.add_argument("--input-root", type=Path, default=None)
    audit.add_argument("--output-dir", type=Path, default=None)
    audit.add_argument("--debug", action="store_true")
    archive = subparsers.add_parser("archive")
    archive.add_argument("--mode", choices=["fast", "full"], required=True)
    archive.add_argument("--run-id", default=None)
    archive.add_argument("--output-dir", type=Path, default=None)
    archive.add_argument("--package-dir", type=Path, default=None)
    archive.add_argument("--debug", action="store_true")
    verify = subparsers.add_parser("archive-verify")
    verify.add_argument("--package-dir", type=Path, required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--debug", action="store_true")
    return parser


def _record_failed_run(output_dir: Path, command: str, exc: Exception) -> None:
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(
            {
                "engineering_status": "FAIL",
                "pipeline_execution_status": "FAIL",
                "independent_self_check_status": "NOT_RUN",
                "final_engineering_status": "FAIL",
                "scientific_status": "NOT_EVALUATED",
                "scientific_uncertainty_status": "NOT_EVALUATED",
                "full_run_recommended": False,
                "paper_promotion_eligible": False,
                "failed_command": command,
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
                "paper_result": False,
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        return


def main() -> None:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parent
    debug = bool(getattr(args, "debug", False))
    output_dir: Path
    run_id: str | None = None

    if args.command in {"fast", "full"}:
        if args.resume_bootstrap:
            output_dir = (args.output_dir or resolve_latest_resumable_run(root, args.command)).resolve()
        else:
            run_label = (
                "fixture"
                if args.command == "fast" and bool(getattr(args, "synthetic_fixture", False))
                else args.command
            )
            run_id = new_run_id(run_label)
            output_dir = (args.output_dir or root / "outputs" / run_id).resolve()
    elif args.command == "self-check":
        if args.output_dir is not None and args.run_id is not None:
            raise SystemExit("Use only one of --output-dir and --run-id.")
        selected = (
            args.output_dir
            or (resolve_run_id(root, args.run_id, args.mode) if args.run_id else None)
            or resolve_latest_completed_run(root, args.mode)
        )
        output_dir = selected.resolve()
    elif args.command == "archive":
        if args.output_dir is not None and args.run_id is not None:
            raise SystemExit("Use only one of --output-dir and --run-id.")
        selected = (
            args.output_dir
            or (resolve_run_id(root, args.run_id, args.mode) if args.run_id else None)
            or resolve_latest_audited_pass_run(root, args.mode)
        )
        output_dir = selected.resolve()
    elif args.command == "archive-verify":
        output_dir = args.package_dir.resolve()
    else:
        output_dir = (args.output_dir or root / "outputs" / "input_audit").resolve()

    try:
        if args.command in {"fast", "full"}:
            result_dir = run_pipeline(
                root,
                args.command,
                input_root=args.input_root,
                output_dir=output_dir,
                run_id=run_id,
                n_jobs=args.n_jobs,
                clean_output=args.clean_output,
                resume_bootstrap=args.resume_bootstrap,
                synthetic_fixture=bool(getattr(args, "synthetic_fixture", False)),
            )
            manifest_path = result_dir / "metadata" / "run_manifest.json"
            completed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            print(f"RUN_ID={completed_manifest['run_id']}")
            print(f"OUTPUT_DIR={result_dir}")
        elif args.command == "self-check":
            run_self_check(output_dir, promote_paper_result=args.promote_paper_result)
        elif args.command == "archive":
            package_dir, zip_path, result = create_archival_package(
                root, output_dir, package_dir=args.package_dir
            )
            print(f"archival_integrity_check_status={result['archival_integrity_check_status']}")
            print(f"archival_package_dir={package_dir}")
            print(f"archival_package_zip={zip_path}")
        elif args.command == "archive-verify":
            result = verify_archival_package(output_dir, args.run_id)
            print(f"archival_integrity_check_status={result['archival_integrity_check_status']}")
            print("verification_role=archival_integrity_only_not_independent_reconstruction")
        else:
            audit = audit_inputs(root, input_root=args.input_root, output_dir=output_dir)
            if str(audit.get("audit_status")) != "PASS":
                raise RuntimeError(
                    "INPUT_AUDIT_STOP_AND_REVIEW: real KuaiRand history/evaluation inputs "
                    "do not satisfy the frozen non-overlap contract."
                )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        if args.command in {"fast", "full"}:
            _record_failed_run(output_dir, args.command, exc)
        if debug:
            raise
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
