from __future__ import annotations

import argparse

from src.runner import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP1 controlled identifiability simulation.")
    parser.add_argument("--mode", choices=("fast", "full"), required=True)
    parser.add_argument(
        "--raw-log-mode",
        choices=("summary_only", "full"),
        default=None,
        help="Fast defaults to summary_only; full defaults to full raw logs.",
    )
    parser.add_argument("--smoke", action="store_true", help="Use a short non-paper horizon for execution tests.")
    parser.add_argument("--output-tag", default=None, help="Write to outputs/<tag> instead of outputs/<mode>.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run(args.mode, raw_log_mode=args.raw_log_mode, smoke=args.smoke, output_tag=args.output_tag)


if __name__ == "__main__":
    raise SystemExit(main())
