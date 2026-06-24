"""Execute the Exp2 synthetic integration test before a real Criteo rerun.

This test intentionally overwrites ``outputs/fast`` because the runner isolates
clean fast outputs.  It validates current configuration aliases, UID ``-1``
filtering, source-event delay semantics, semantic checks, and deterministic
UID bootstrap output across one and four workers.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FIXTURE = ROOT / "inputs" / "synthetic_fixture.tsv"
BOOTSTRAP = ROOT / "outputs" / "fast" / "raw" / "exp2_uid_bootstrap_replicates.csv"
REPORT = ROOT / "tests" / "synthetic_integration_report.json"


def _run(command: list[str]) -> None:
    print("[synthetic_integration]", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fast_command(n_jobs: int) -> list[str]:
    return [
        PYTHON,
        "main.py",
        "--mode",
        "fast",
        "--config",
        "tests/fixture_config.yaml",
        "--input",
        str(FIXTURE),
        "--n-jobs",
        str(n_jobs),
    ]


def main() -> None:
    _run([PYTHON, "tests/generate_synthetic_fixture.py", "--output", str(FIXTURE)])

    _run(_fast_command(1))
    _run([PYTHON, "tests/check_decision_cell_smoke.py", "--output-root", "outputs/fast"])
    hash_jobs_1 = _sha256(BOOTSTRAP)

    _run(_fast_command(4))
    _run([PYTHON, "tests/check_decision_cell_smoke.py", "--output-root", "outputs/fast"])
    hash_jobs_4 = _sha256(BOOTSTRAP)
    if hash_jobs_1 != hash_jobs_4:
        raise RuntimeError(
            "UID bootstrap reproducibility failed: --n-jobs=1 and --n-jobs=4 produced different hashes."
        )

    _run([PYTHON, "self_check.py", "--mode", "fast"])
    _run([PYTHON, "code_check.py", "--mode", "fast"])

    REPORT.write_text(
        json.dumps(
            {
                "status": "passed",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "fixture": str(FIXTURE),
                "bootstrap_sha256_n_jobs_1": hash_jobs_1,
                "bootstrap_sha256_n_jobs_4": hash_jobs_4,
                "bootstrap_hashes_identical": True,
                "notes": "Synthetic-only validation. The final outputs/fast directory contains synthetic, not paper, results.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("[synthetic_integration] passed", flush=True)


if __name__ == "__main__":
    main()
