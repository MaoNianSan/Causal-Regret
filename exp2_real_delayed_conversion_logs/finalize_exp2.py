from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.common import load_config, out_dir, save_run_metadata, write_csv


def _fail(message: str) -> None:
    raise RuntimeError(f"Cannot finalize Experiment 2 paper-result bundles: {message}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote validated full-mode figure bundles to paper_result=true."
    )
    parser.add_argument("--config", default="config_exp2.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if str(cfg.get("runtime", {}).get("mode", "")) != "full":
        _fail("finalization is allowed only for runtime.mode=full")

    root = out_dir(cfg, "root")
    checks = root / "checks" / "exp2_self_check_results.csv"
    if not checks.exists():
        _fail(f"missing semantic self-check result: {checks}")
    result = pd.read_csv(checks)
    if result.empty or (result["status"].astype(str) != "PASS").any():
        _fail("semantic self-check has failures")

    data_dir = root / "figures" / "data"
    meta_dir = root / "figures" / "metadata"
    meta_paths = sorted(meta_dir.glob("*_metadata.json"))
    if not meta_paths:
        _fail("no figure metadata files found")

    for meta_path in meta_paths:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        figure_id = str(payload.get("figure_id", ""))
        data_path = data_dir / f"{figure_id}_data.csv"
        if not figure_id or not data_path.exists():
            _fail(f"missing figure data bundle for {figure_id!r}")
        data = pd.read_csv(data_path)
        if "paper_result" not in data.columns:
            _fail(f"figure data lacks paper_result column: {data_path}")
        data["paper_result"] = True
        write_csv(data, data_path)
        payload["paper_result"] = True
        payload["finalized_after_semantic_self_check"] = True
        meta_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    save_run_metadata(
        cfg,
        "paper_result_finalized",
        {"n_figure_bundles": len(meta_paths), "paper_result": True},
    )
    print(
        f"[finalize] promoted {len(meta_paths)} validated full-mode figure bundles",
        flush=True,
    )


if __name__ == "__main__":
    main()
