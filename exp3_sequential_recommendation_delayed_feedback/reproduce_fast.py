from __future__ import annotations

import argparse

from src.runner import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Exp3 fast smoke test.")
    parser.add_argument("--n-jobs", type=int, default=None)
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete prior active outputs for this mode before running. Required when stale active outputs exist.",
    )
    args = parser.parse_args()
    raise SystemExit(run("fast", n_jobs=args.n_jobs, clean_output=args.clean_output))
