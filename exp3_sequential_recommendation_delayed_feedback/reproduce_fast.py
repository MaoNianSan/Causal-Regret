from __future__ import annotations
import argparse
from src.runner import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Exp3 fast smoke test.")
    parser.add_argument("--n-jobs", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(run("fast", n_jobs=args.n_jobs))
