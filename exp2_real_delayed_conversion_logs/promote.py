from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def promote_run(project_root: Path, run_id: str) -> Path:
    run_root = project_root / "outputs" / run_id
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Run manifest not found: {manifest_path}")
    manifest = _load_json(manifest_path)

    required = {
        "run_tier": "full",
        "status": "COMPLETE",
        "engineering_status": "PASS",
        "scientific_status": "PASS",
        "primary_full_runs_complete": True,
        "main_figures_reconstructable": True,
        "main_tables_reconstructable": True,
        "claims_within_scope": True,
        "development_override": False,
    }
    failures = {
        key: {"expected": expected, "observed": manifest.get(key)}
        for key, expected in required.items()
        if manifest.get(key) != expected
    }
    if failures:
        raise SystemExit(f"Paper promotion blocked: {failures}")
    if manifest.get("paper_result") is True:
        raise SystemExit("Run is already marked paper_result=true.")

    required_files = [
        run_root / "figures" / "figure_exp2_main.pdf",
        run_root / "figures" / "figure_exp2_main_data.csv",
        run_root / "figures" / "figure_exp2_main_metadata.json",
        run_root / "tables" / "table_exp2_cohort.tex",
        run_root / "tables" / "table_exp2_primary_results.tex",
        run_root / "derived" / "arrival_displacement.csv",
        run_root / "derived" / "source_route_pairwise.csv",
        run_root / "audit" / "self_check.json",
        run_root / "audit" / "bootstrap_audit.json",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise SystemExit(f"Paper promotion blocked; missing artifacts: {missing}")

    paper_root = project_root / "outputs" / "paper" / run_id
    if paper_root.exists():
        raise SystemExit(f"Paper bundle already exists: {paper_root}")
    paper_root.mkdir(parents=True)
    for folder in ("figures", "tables"):
        shutil.copytree(run_root / folder, paper_root / folder)
    for relative in (
        "derived/cohort_summary.csv",
        "derived/arrival_displacement.csv",
        "derived/source_route_pairwise.csv",
        "derived/kendall_support.csv",
        "audit/self_check.json",
        "audit/bootstrap_audit.json",
    ):
        source = run_root / relative
        destination = paper_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    paper_manifest = dict(manifest)
    paper_manifest.update(
        {
            "run_tier": "paper",
            "paper_result": True,
            "source_full_run_id": run_id,
            "paper_promoted_at": datetime.now().astimezone().isoformat(),
            "paper_promotion_status": "PROMOTED",
        }
    )
    with (paper_root / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(paper_manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
    paper_self_check_path = paper_root / "audit" / "self_check.json"
    paper_self_check = _load_json(paper_self_check_path)
    paper_self_check.update(
        {
            "paper_result": True,
            "paper_promotion_status": "PROMOTED",
            "source_full_run_id": run_id,
        }
    )
    paper_self_check.setdefault("checks", []).append(
        {
            "check": "promotion_consistency",
            "status": "PASS",
            "paper_result": True,
            "paper_promotion_status": "PROMOTED",
        }
    )
    with paper_self_check_path.open("w", encoding="utf-8") as handle:
        json.dump(paper_self_check, handle, ensure_ascii=False, indent=2, sort_keys=True)

    promotion_audit = {
        "source_full_run_id": run_id,
        "paper_result": True,
        "paper_promotion_status": "PROMOTED",
        "paper_manifest_status": paper_manifest["paper_promotion_status"],
        "paper_self_check_status": paper_self_check["paper_promotion_status"],
        "promotion_consistency": "PASS",
        "promoted_at": paper_manifest["paper_promoted_at"],
    }
    with (paper_root / "audit" / "promotion_audit.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(promotion_audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return paper_root


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote a validated Experiment 2 full run to a paper-facing bundle."
    )
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    paper_root = promote_run(project_root, args.run_id)
    print(f"Paper bundle promoted: {paper_root}")


if __name__ == "__main__":
    main()
