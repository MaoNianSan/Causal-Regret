from __future__ import annotations

import argparse

from src.runner import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EXP2 fast logged-attribution-sensitivity validation with UID bootstrap.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--n-bootstrap", type=int, default=None)
    parser.add_argument("--n-jobs", default="auto")
    args = parser.parse_args()
    raise SystemExit(run("fast", args.config, args.n_bootstrap, args.n_jobs))
