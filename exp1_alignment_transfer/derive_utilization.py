"""Reporting-only materialization of the realized stability-utilization artifacts.

This utility never reruns the scientific experiment, never rewrites primary
seed-level files, and never promotes anything. It reads the frozen seed-level
route metrics of one Exp1 output root and emits the added derived artifacts

    derived/exp1_regret_stability_utilization.csv
    derived/exp1_regret_stability_utilization_summary.csv

next to the existing derived files. The paper-candidate root is the default
because the realized-utilization diagnostic is reported against the frozen
canonical result; ``outputs/fast`` and ``outputs/full`` obtain the same
artifacts automatically from the derived reconstruction stage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main import PROJECT_ROOT
from src.artifact_io import sha256_file
from src.derived import materialize_regret_stability_utilization


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs/paper_candidate")
    parser.add_argument("--repetitions", type=int, default=None)
    parser.add_argument("--ci-level", type=float, default=None)
    args = parser.parse_args()

    root = Path(args.output_root)
    if not root.is_absolute():
        root = (PROJECT_ROOT / root).resolve()
    if not root.is_dir():
        raise RuntimeError(f"Unknown Exp1 output root: {root}")

    paths = materialize_regret_stability_utilization(
        root,
        repetitions=args.repetitions,
        ci_level=args.ci_level,
        route_seed=None,
    )
    print("UTILIZATION_ARTIFACTS_COMPLETE")
    print(
        json.dumps(
            {
                name: {
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
                for name, path in paths.items()
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
