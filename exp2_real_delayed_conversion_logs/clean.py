from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely remove Experiment 2 generated outputs.")
    parser.add_argument("--yes", action="store_true", help="Skip the CLEAN confirmation prompt.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    entries = list(root.iterdir())
    total_bytes = sum(
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file()
    )
    print("EXP2 output cleaner")
    print(f"Target: {root}")
    print(f"Entries to remove: {len(entries)}")
    print(f"Total size: {total_bytes / (1024 ** 2):.2f} MB")
    if not args.yes:
        confirmation = input("Type CLEAN to continue: ").strip()
        if confirmation != "CLEAN":
            print("Cancelled.")
            raise SystemExit(1)
    for path in entries:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    print("EXP2 outputs cleaned successfully.")


if __name__ == "__main__":
    main()
