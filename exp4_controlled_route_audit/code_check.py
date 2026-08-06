"""Compatibility wrapper for v2 static code checks."""

import json
from pathlib import Path

from exp4.outputs.writers import write_json
from exp4.validation.static_checks import run_static_checks


def run(root: Path, run_dir: Path | None = None):
    payload = run_static_checks(root)
    if run_dir is not None:
        write_json(payload, run_dir / "checks" / "exp4_static_code_checks.json")
    return payload


if __name__ == "__main__":
    result = run(Path(__file__).resolve().parent)
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)
