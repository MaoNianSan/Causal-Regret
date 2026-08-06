"""Compatibility wrapper for v2 engineering and scientific validation."""

import json
from pathlib import Path

from exp4.validation.runner import validate_run


def run(run_dir: Path):
    return validate_run(run_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    engineering, scientific = run(parser.parse_args().run_dir)
    print(json.dumps({"engineering": engineering["status"], "scientific": scientific["status"]}, indent=2))
    if engineering["status"] != "PASS" or scientific["status"] != "PASS":
        raise SystemExit(1)
