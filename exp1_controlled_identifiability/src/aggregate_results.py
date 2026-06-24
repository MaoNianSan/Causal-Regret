"""Rebuild current EXP1 outputs from a completed seed-level result file.

This compatibility entry point supports the documented command
``python -m src.aggregate_results --output-root outputs/<tag>``.  It uses the
current contextual-result schema and does not reference retired scenario IDs
or retired raw-column names.
"""

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


def rebuild(output_root: str | Path) -> Path:
    root = Path(output_root).resolve()
    raw = root / "raw" / "seed_level_results.csv"
    manifest_path = root / "metadata" / "run_manifest.json"
    if not raw.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing current raw provenance: {raw} or {manifest_path}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mode = str(manifest.get("mode") or manifest.get("run_mode") or "")
    if mode not in {"fast", "full"}:
        raise ValueError(f"Manifest has unsupported mode: {mode!r}")

    seed = pd.read_csv(raw)
    required = {"seed", "delay_setting", "regime", "method", "final_Rc", "T"}
    missing = sorted(required.difference(seed.columns))
    if missing:
        raise ValueError(f"Raw seed-level CSV is incompatible; missing {missing}")

    output_tag = root.name if root.parent.name == "outputs" else None
    options = RunOptions(
        mode=mode,
        raw_log_mode="summary_only",
        smoke=bool(manifest.get("is_smoke", False)),
        output_tag=output_tag,
    )
    if "method_id" not in seed.columns:
        seed = _enrich_seed_schema(seed, options)
        seed.to_csv(raw, index=False)

    _make_summaries(seed, root)
    _collect_selected_trajectory_points(options)
    plot_exp1_bundles(seed, root)

    manifest["reused_raw_outputs"] = True
    manifest["paper_result"] = False
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    artifacts = _artifact_rows(root)
    pd.DataFrame(artifacts).to_csv(
        root / "metadata" / "artifacts_manifest.csv", index=False
    )
    pd.DataFrame(artifacts).to_csv(root / "manifest.csv", index=False)
    (root / "manifest.json").write_text(
        json.dumps({"artifacts": artifacts}, indent=2), encoding="utf-8"
    )
    return root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    root = rebuild(args.output_root)
    print(f"Rebuilt outputs under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
