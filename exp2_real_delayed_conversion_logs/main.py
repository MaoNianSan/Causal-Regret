from __future__ import annotations

import argparse

from runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Experiment 2: delayed-conversion attribution sensitivity."
    )
    parser.add_argument("mode", choices=["fast", "full"])
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
    raise SystemExit(
        run(
            args.mode,
            config_path=args.config,
            input_path=args.input,
            n_bootstrap=args.n_bootstrap,
            n_jobs=args.n_jobs,
        )
    )


if __name__ == "__main__":
    main()
