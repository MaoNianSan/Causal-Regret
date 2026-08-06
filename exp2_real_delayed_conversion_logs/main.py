from __future__ import annotations

import argparse

from runner import run, run_cohort_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Experiment 2: delayed-conversion attribution sensitivity."
    )
    parser.add_argument("mode", nargs="?", choices=["fast", "full", "cohort-check"])
    parser.add_argument("--mode", dest="mode_flag", choices=["full"], help=argparse.SUPPRESS)
    parser.add_argument("--config", default=None, help="Optional configuration path.")
    parser.add_argument("--input", default=None, help="Explicit TSV input path.")
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=None,
        help="Development override for bootstrap repetitions.",
    )
    parser.add_argument(
        "--n-jobs",
        default=None,
        help="Positive worker count or 'auto'.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selected_mode = args.mode or ("cohort-check" if args.mode_flag == "full" else None)
    if selected_mode is None:
        raise SystemExit("a run mode is required")
    if selected_mode == "cohort-check":
        raise SystemExit(run_cohort_check(config_path=args.config, input_path=args.input))
    raise SystemExit(
        run(
            selected_mode,
            config_path=args.config,
            input_path=args.input,
            n_bootstrap=args.n_bootstrap,
            n_jobs=args.n_jobs,
        )
    )


if __name__ == "__main__":
    main()
