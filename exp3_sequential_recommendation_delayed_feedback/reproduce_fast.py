from __future__ import annotations
import argparse
from pathlib import Path
from runner import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--synthetic-fixture", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    run_pipeline(
        root,
        "fast",
        input_root=args.input_root,
        n_jobs=args.n_jobs,
        clean_output=args.clean_output,
        synthetic_fixture=args.synthetic_fixture,
    )
