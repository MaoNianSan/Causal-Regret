from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run EXP2 semantic self-check for a completed mode."
    )
    parser.add_argument("--mode", required=True, choices=("fast", "full"))
    parser.add_argument(
        "--config", default=None, help="Optional effective configuration path."
    )
    args = parser.parse_args()
    config = (
        Path(args.config)
        if args.config
        else ROOT / ".runtime" / f"config_exp2_{args.mode}.yaml"
    )
    if not config.exists():
        print(
            f"[self_check] missing effective configuration: {config}", file=sys.stderr
        )
        return 2
    return subprocess.run(
        [
            sys.executable,
            "self_check_exp2.py",
            "--config",
            str(config),
            "--mode",
            args.mode,
        ],
        cwd=ROOT,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
