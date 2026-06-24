from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.plot_utils import plot_exp1_bundles
from src.runner import (
    PROJECT_ROOT,
    RunOptions,
    _artifact_rows,
    _collect_selected_trajectory_points,
    _enrich_seed_schema,
    _make_summaries,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild EXP1 summaries, appendix tables, figures, and metadata from an existing seed-level CSV."
    )
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()

    root = PROJECT_ROOT / "outputs" / (args.output_tag or args.mode)
    raw_path = root / "raw" / "seed_level_results.csv"
    manifest_path = root / "metadata" / "run_manifest.json"
    if not raw_path.exists() or not manifest_path.exists():
        raise SystemExit(f"missing raw provenance: {raw_path} or {manifest_path}")

    seed = pd.read_csv(raw_path)
    required = {"seed", "delay_setting", "regime", "method", "final_Rc", "T"}
    missing = sorted(required.difference(seed.columns))
    if missing:
        raise SystemExit(f"raw seed-level CSV is incompatible; missing {missing}")

    options = RunOptions(mode=args.mode, raw_log_mode="summary_only", smoke=False, output_tag=args.output_tag)
    if "method_id" not in seed.columns:
        seed = _enrich_seed_schema(seed, options)
        seed.to_csv(raw_path, index=False)

    _make_summaries(seed, root)
    _collect_selected_trajectory_points(options)
    plot_exp1_bundles(seed, root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reused_raw_outputs"] = True
    manifest["paper_result"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    artifacts = _artifact_rows(root)
    pd.DataFrame(artifacts).to_csv(root / "metadata" / "artifacts_manifest.csv", index=False)
    pd.DataFrame(artifacts).to_csv(root / "manifest.csv", index=False)
    (root / "manifest.json").write_text(json.dumps({"artifacts": artifacts}, indent=2), encoding="utf-8")
    print(f"Rebuilt outputs under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
