"""Regenerate figures from a completed Exp3 output directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import DEFAULT_CONFIG
from plot_results import plot_all

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("fast", "full"))
    args = parser.parse_args()
    output_dir = ROOT / "outputs" / args.mode
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    input_data_status = "unknown"
    if manifest_path.exists():
        input_data_status = json.loads(manifest_path.read_text(encoding="utf-8")).get(
            "input_data_status", input_data_status
        )
    plot_all(
        output_dir,
        args.mode,
        False,
        DEFAULT_CONFIG,
        input_data_status=input_data_status,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
