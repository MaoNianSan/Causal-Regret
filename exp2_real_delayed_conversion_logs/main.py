from __future__ import annotations

import argparse

from src.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete Experiment 2 pipeline with isolated fast/full outputs."
    )
    parser.add_argument("--mode", choices=["fast", "full"], required=True)
    parser.add_argument(
        "--config",
        default=None,
        help="Optional base configuration; local input path remains inputs/pcb_dataset_final.tsv.",
    )
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=None,
        help="Optional development override; omitted uses the configured value.",
    )
    parser.add_argument(
        "--n-jobs",
        default="auto",
        help="Worker count: positive integer or 'auto' (default; detects current logical CPUs).",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Optional development fixture path; omitted preserves the protected Criteo input path.",
    )
    args = parser.parse_args()
    raise SystemExit(
        run(args.mode, args.config, args.n_bootstrap, args.n_jobs, args.input)
    )


if __name__ == "__main__":
    main()
