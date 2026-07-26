"""Independent safe cleaner for Exp4 generated run directories."""

from __future__ import annotations

import shutil
from pathlib import Path

import config


def main() -> None:
    run_root = config.OUTPUT_ROOT
    run_directories = sorted(path for path in run_root.iterdir() if path.is_dir())
    total_bytes = sum(
        path.stat().st_size
        for run_dir in run_directories
        for path in run_dir.rglob("*")
        if path.is_file()
    )
    print("EXP4 output cleaner")
    print(f"Target: {run_root}")
    print(f"Run directories to remove: {len(run_directories)}")
    print(f"Total size: {total_bytes / (1024 ** 2):.2f} MB")
    confirmation = input("Type CLEAN to continue: ").strip()
    if confirmation != "CLEAN":
        raise SystemExit("Cleaning cancelled.")
    for run_dir in run_directories:
        shutil.rmtree(run_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / ".gitkeep").touch()
    print("Exp4 outputs cleaned successfully.")


if __name__ == "__main__":
    main()
