from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.formal_contract import FORMAL_SETTINGS
from src.plot_utils import plot_exp1_bundles
from src.runner import PROJECT_ROOT, _make_summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild EXP1 summaries, tables, figures, and metadata from existing raw seed-level outputs.")
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    root = PROJECT_ROOT / "outputs" / (args.output_tag or args.mode)
    raw_path = root / "raw" / "seed_level_results.csv"
    manifest_path = root / "metadata" / "run_manifest.json"
    if not raw_path.exists() or not manifest_path.exists():
        raise SystemExit(f"missing raw provenance: {raw_path} or {manifest_path}")
    seed = pd.read_csv(raw_path)
    missing = [s for s in FORMAL_SETTINGS if s not in set(seed.get("setting_id", seed.get("delay_setting", pd.Series(dtype=str))).astype(str))]
    incompatible = []
    if "raw_setting_id" not in seed or "setting_id" not in seed:
        incompatible.append("missing setting_id/raw_setting_id")
    elif not (seed["raw_setting_id"].astype(str) == seed["setting_id"].astype(str)).all():
        incompatible.append("non-identity raw_setting_id")
    if missing or incompatible:
        raise SystemExit(json.dumps({"missing_setting_ids": missing, "incompatible": incompatible}, sort_keys=True))
    seed["run_mode"] = args.mode
    _make_summaries(seed, root)
    plot_exp1_bundles(seed, root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reused_raw_outputs"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

