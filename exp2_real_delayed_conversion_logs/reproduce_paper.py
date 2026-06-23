from __future__ import annotations

import argparse

from src.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce Experiment 2 paper-grade full outputs.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--n-bootstrap", type=int, default=None)
    parser.add_argument("--n-jobs", default="auto")
    args = parser.parse_args()
    raise SystemExit(run("full", args.config, args.n_bootstrap, args.n_jobs))


if __name__ == "__main__":
    main()
