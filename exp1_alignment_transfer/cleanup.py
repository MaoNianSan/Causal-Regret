from __future__ import annotations

"""Explicit, standalone cleanup for run outputs only."""

import argparse
from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("fast", "full", "paper_candidate", "all_runs"))
    parser.add_argument("--yes", action="store_true", help="skip interactive CLEAN confirmation")
    args = parser.parse_args()
    targets = (
        [PROJECT_ROOT / "outputs" / name for name in ("fast", "full", "paper_candidate")]
        if args.target == "all_runs"
        else [PROJECT_ROOT / "outputs" / args.target]
    )
    existing = [path for path in targets if path.exists()]
    print("Exp1 output cleaner")
    print("Calibration artifacts and source code are never removed.")
    for path in existing:
        print(f"target={path}")
    if not existing:
        print("nothing_to_remove=true")
        return
    if not args.yes:
        confirmation = input("Type CLEAN to continue: ").strip()
        if confirmation != "CLEAN":
            print("cleanup_cancelled=true")
            return
    for path in existing:
        shutil.rmtree(path)
    status_dir = PROJECT_ROOT / "status"
    status_prefixes = {
        "fast": ("fast_",),
        "full": ("full_",),
        "paper_candidate": ("paper_",),
        "all_runs": ("fast_", "full_", "paper_"),
    }[args.target]
    removed_status = 0
    if status_dir.exists():
        for status_path in status_dir.glob("*.json"):
            if status_path.name == "calibration_status.json":
                continue
            if status_path.name.startswith(status_prefixes):
                status_path.unlink()
                removed_status += 1
    print(f"removed_run_status_files={removed_status}")
    print("cleanup_complete=true")


if __name__ == "__main__":
    main()
