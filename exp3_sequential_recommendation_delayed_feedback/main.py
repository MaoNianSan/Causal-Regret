from __future__ import annotations
import argparse
from src.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Exp3 sequential delayed-feedback evaluation."
    )
    parser.add_argument("--mode", required=True, choices=("fast", "full"))
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=None,
        help="Worker count. Default auto-selects <=16 for fast and <=32 for full.",
    )
    args = parser.parse_args()
    return run(args.mode, n_jobs=args.n_jobs)


if __name__ == "__main__":
    raise SystemExit(main())
