from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove generated EXP1 output directories without touching source files."
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=None,
        help="Only remove outputs/<tag>. May be given more than once.",
    )
    parser.add_argument(
        "--all", action="store_true", help="Remove every generated output directory."
    )
    args = parser.parse_args()
    if not args.all and not args.tag:
        parser.error("Specify --tag <name> or --all.")
    tags = (
        [path.name for path in OUTPUTS.iterdir() if path.is_dir()]
        if args.all
        else args.tag
    )
    for tag in tags:
        target = OUTPUTS / str(tag)
        if target.exists():
            shutil.rmtree(target)
            print(f"removed {target.relative_to(ROOT)}")
        else:
            print(f"not found {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
