from __future__ import annotations

import json
from pathlib import Path

from promote import promote_run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_promotion_manifest_self_check_and_audit_are_consistent(tmp_path: Path):
    run_id = "exp2-full-test"
    run_root = tmp_path / "outputs" / run_id
    manifest = {
        "run_id": run_id,
        "run_tier": "full",
        "status": "COMPLETE",
        "engineering_status": "PASS",
        "scientific_status": "PASS",
        "primary_full_runs_complete": True,
        "main_figures_reconstructable": True,
        "main_tables_reconstructable": True,
        "claims_within_scope": True,
        "development_override": False,
        "paper_result": False,
        "paper_promotion_status": "PENDING_INDEPENDENT_PROMOTION",
    }
    _write_json(run_root / "run_manifest.json", manifest)
    _write_json(
        run_root / "audit" / "self_check.json",
        {
            "engineering_status": "PASS",
            "scientific_status": "PASS",
            "paper_promotion_status": "PENDING_INDEPENDENT_PROMOTION",
            "checks": [],
        },
    )
    _write_json(run_root / "audit" / "bootstrap_audit.json", {"support_frozen": True})
    required = [
        "figures/figure_exp2_main.pdf",
        "figures/figure_exp2_main_data.csv",
        "figures/figure_exp2_main_metadata.json",
        "tables/table_exp2_cohort.tex",
        "tables/table_exp2_primary_results.tex",
        "derived/cohort_summary.csv",
        "derived/arrival_displacement.csv",
        "derived/source_route_pairwise.csv",
        "derived/kendall_support.csv",
    ]
    for relative in required:
        path = run_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test", encoding="utf-8")

    paper_root = promote_run(tmp_path, run_id)
    paper_manifest = json.loads((paper_root / "run_manifest.json").read_text())
    self_check = json.loads((paper_root / "audit" / "self_check.json").read_text())
    promotion_audit = json.loads(
        (paper_root / "audit" / "promotion_audit.json").read_text()
    )
    for payload in (paper_manifest, self_check, promotion_audit):
        assert payload["paper_result"] is True
        assert payload["paper_promotion_status"] == "PROMOTED"
    assert promotion_audit["promotion_consistency"] == "PASS"
