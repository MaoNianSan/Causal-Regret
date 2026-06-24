"""Refresh promoted full figure interfaces without rerunning Exp3."""
from __future__ import annotations

import json
from pathlib import Path

from config import DEFAULT_CONFIG
from plot_results import plot_all
from utils import write_artifact_manifest, write_json

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "full"


def main() -> int:
    manifest_path = OUTPUT_DIR / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_mode") != "full":
        raise RuntimeError("refresh_full_figures.py only supports mode=full")
    if manifest.get("input_data_status") != "real_kuairand_1k":
        raise RuntimeError("full figure refresh requires real_kuairand_1k input status")
    if manifest.get("status") not in {"complete_pending_external_checks", "complete"}:
        raise RuntimeError(f"full run status is not refreshable: {manifest.get('status')!r}")

    plot_all(
        OUTPUT_DIR,
        "full",
        bool(manifest.get("paper_result", False)),
        DEFAULT_CONFIG,
        input_data_status=str(manifest.get("input_data_status", "unknown")),
    )
    write_artifact_manifest(OUTPUT_DIR)
    write_json(OUTPUT_DIR / "run_manifest.json", manifest)
    print("FULL FIGURE INTERFACES REFRESHED")
    print("paper_result preserved:", bool(manifest.get("paper_result", False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
