"""Promote one audited full run by immutable run ID."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from self_check import run_self_check


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote an Exp3 full run")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output_dir = (root / "outputs" / args.run_id).resolve()
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Unknown run ID: {args.run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("run_tier")) != "full":
        raise RuntimeError("Only a full run can be promoted.")
    run_self_check(output_dir, promote_paper_result=True)
    print(f"PROMOTED_RUN_ID={args.run_id}")


if __name__ == "__main__":
    main()
