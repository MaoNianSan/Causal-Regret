from __future__ import annotations

"""Mark a completed, audited full EXP1 output directory as paper-eligible."""

import argparse
import json
from pathlib import Path

import pandas as pd

from self_check import check_project
from src.runner import PROJECT_ROOT


def _set_csv_flag(path: Path) -> None:
    if not path.exists():
        return
    frame = pd.read_csv(path)
    if "paper_result" in frame.columns:
        frame["paper_result"] = True
        frame.to_csv(path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full",), default="full")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = PROJECT_ROOT / "outputs" / (args.output_tag or args.mode)
    manifest_path = root / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("backend_status") != "completed"
        or manifest.get("mode") != "full"
        or bool(manifest.get("is_smoke"))
    ):
        raise SystemExit("paper finalization requires a completed non-smoke full run")
    if not check_project("full", args.output_tag):
        raise SystemExit("self-check failed; outputs are not paper-eligible")

    for directory in (
        root / "raw",
        root / "summaries",
        root / "tables",
        root / "processed",
    ):
        if directory.exists():
            for path in directory.glob("*.csv"):
                _set_csv_flag(path)

    for path in (root / "figures" / "data").glob("*_data.csv"):
        _set_csv_flag(path)
    for path in (root / "figures" / "metadata").glob("*_metadata.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["paper_result"] = True
        payload["figure_status"] = "paper_eligible"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest["paper_result"] = True
    manifest["paper_result_finalized_at"] = pd.Timestamp.utcnow().isoformat()
    manifest["paper_result_gate"] = (
        "passed: completed full run plus self-check plus explicit finalization"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Paper-result gate passed for {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
