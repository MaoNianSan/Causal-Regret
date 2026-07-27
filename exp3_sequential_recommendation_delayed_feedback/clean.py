"""Safely remove one immutable Exp3 run directory."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from runner import resolve_latest_completed_run


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id")
    group.add_argument("--mode", choices=["fast", "full"], help="Select the latest run of this tier")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--force-paper", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    target = (
        (root / "outputs" / args.run_id).resolve()
        if args.run_id
        else resolve_latest_completed_run(root, args.mode)
    )
    if not target.exists():
        print(f"No output directory: {target}")
        return
    manifest_path = target / "metadata" / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if bool(manifest.get("paper_result", False)) and not args.force_paper:
            raise SystemExit("Refusing to remove a promoted paper result. Archive it or pass --force-paper explicitly.")
    if not args.yes:
        confirmation = input(f"Type CLEAN to remove {target.name}: ")
        if confirmation != "CLEAN":
            raise SystemExit("Cancelled")
    shutil.rmtree(target)
    print(f"Removed run: {target}")


if __name__ == "__main__":
    main()
