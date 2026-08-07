"""Thin reproduction wrapper for the Causal-Regret repository.

This script does NOT reimplement any experiment logic. It only forwards to
each experiment's existing command-line interface, which remains the
authoritative entry point. Every command is executed from the repository root
with relative paths.

Usage (run from the repository root):

    python reproduce.py smoke [--n-jobs N] [--dry-run]
    python reproduce.py full --exp {1,2,3,4} [--n-jobs N] [--dry-run]

- ``smoke`` runs the lightweight fast-tier entry of each experiment
  (Exp3 uses its deterministic synthetic fixture, so no external data is
  required; Exp2 requires the local Criteo input, see DATA.md).
- ``full --exp N`` forwards to the formal full-run command of experiment N.
- ``--dry-run`` prints the commands without executing them.

The full per-experiment workflows (self-check, targeted validation, plotting,
promotion) are documented in REPRODUCE.md and can always be invoked directly.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

EXPERIMENTS = {
    "1": "exp1_alignment_transfer",
    "2": "exp2_real_delayed_conversion_logs",
    "3": "exp3_sequential_recommendation_delayed_feedback",
    "4": "exp4_controlled_route_audit",
}

# Per-experiment smoke (fast-tier) commands, relative to the repository root.
SMOKE_COMMANDS = {
    "1": ["exp1_alignment_transfer/main.py", "fast"],
    "2": ["exp2_real_delayed_conversion_logs/main.py", "fast"],
    "3": [
        "exp3_sequential_recommendation_delayed_feedback/main.py",
        "fast",
        "--synthetic-fixture",
    ],
    "4": ["exp4_controlled_route_audit/main.py", "fast"],
}

# Per-experiment formal full-run commands, relative to the repository root.
FULL_COMMANDS = {
    "1": ["exp1_alignment_transfer/main.py", "full"],
    "2": ["exp2_real_delayed_conversion_logs/main.py", "full"],
    "3": [
        "exp3_sequential_recommendation_delayed_feedback/main.py",
        "full",
    ],
    "4": ["exp4_controlled_route_audit/main.py", "full"],
}

# Exp2 requires the local Criteo input; smoke is skipped with a warning when
# it is absent (this is a data dependency, not a code failure).
EXP2_INPUT_HINT = (
    REPO_ROOT
    / "exp2_real_delayed_conversion_logs"
    / "inputs"
    / "pcb_dataset_final.tsv"
)


def _with_jobs(command: list[str], n_jobs: int | None) -> list[str]:
    """Append --n-jobs where the experiment CLI accepts it (3, 4, and 2)."""
    if n_jobs is None:
        return command
    exp_dir = command[0].split("/", 1)[0]
    if exp_dir in ("exp1_alignment_transfer", "exp2_real_delayed_conversion_logs"):
        # Exp1's entry point has no --n-jobs flag; Exp2 defaults to auto.
        return command
    return command + [f"--n-jobs={n_jobs}"]


def _run(command: list[str], dry_run: bool) -> int:
    printable = " ".join(["python", *command])
    if dry_run:
        print(f"[dry-run] {printable}")
        return 0
    print(f"$ {printable}")
    return subprocess.call(
        [sys.executable, *command],
        cwd=str(REPO_ROOT),
        env={**os.environ},
    )


def _cmd_smoke(n_jobs: int | None, dry_run: bool) -> int:
    failures: list[str] = []
    for exp, directory in EXPERIMENTS.items():
        if exp == "2" and not EXP2_INPUT_HINT.exists():
            print(
                f"[smoke] Experiment 2 skipped: local input missing "
                f"({EXP2_INPUT_HINT.relative_to(REPO_ROOT)}); see DATA.md"
            )
            continue
        print(f"--- Experiment {exp} ({directory}) ---")
        rc = _run(_with_jobs(SMOKE_COMMANDS[exp], n_jobs), dry_run)
        if rc != 0:
            failures.append(f"Experiment {exp} (smoke) exited {rc}")
    if failures:
        print("SMOKE FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("SMOKE OK")
    return 0


def _cmd_full(exp: str, n_jobs: int | None, dry_run: bool) -> int:
    if exp not in EXPERIMENTS:
        raise SystemExit(f"Unknown experiment: {exp}. Choose from {sorted(EXPERIMENTS)}.")
    command = FULL_COMMANDS[exp]
    if n_jobs is not None and exp in ("3", "4"):
        command = command + [f"--n-jobs={n_jobs}"]
    print(f"--- Experiment {exp} full run ---")
    return _run(command, dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Thin reproduction wrapper (forwards to the per-experiment CLIs)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("smoke", help="Run fast-tier smoke checks.")
    smoke.add_argument("--n-jobs", type=int, default=None)
    smoke.add_argument("--dry-run", action="store_true")
    full = subparsers.add_parser("full", help="Forward to a formal full run.")
    full.add_argument("--exp", choices=sorted(EXPERIMENTS), required=True)
    full.add_argument("--n-jobs", type=int, default=None)
    full.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "smoke":
        raise SystemExit(_cmd_smoke(args.n_jobs, args.dry_run))
    raise SystemExit(_cmd_full(args.exp, args.n_jobs, args.dry_run))


if __name__ == "__main__":
    main()
