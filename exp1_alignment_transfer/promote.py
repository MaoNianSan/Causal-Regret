from __future__ import annotations

"""Independent paper-promotion gate for completed full Exp1 artifacts."""

import argparse
import json
from pathlib import Path
import re
import shutil

from src.derived import write_manuscript_artifacts

import pandas as pd

from src.artifact_io import atomic_write_json, hash_payload, sha256_file, utc_now
from src.run_provenance import audit_exp1_provenance


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS = PROJECT_ROOT / "outputs"
STATUS = PROJECT_ROOT / "status"


def _parse_memo_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    pattern = re.compile(r"^\s*-\s*([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip().strip("`\"'")
        metadata[key] = value
    return metadata


def _memo_sort_key(path: Path, metadata: dict[str, str]) -> tuple[int, str]:
    memo_id = metadata.get("memo_id", path.stem)
    match = re.search(r"(\d+)$", memo_id)
    return (int(match.group(1)) if match else -1, memo_id)


def promotion_authorization() -> dict[str, object]:
    memos = []
    for path in PROJECT_ROOT.glob("CHANGE_MEMO_EXP1_*.md"):
        metadata = _parse_memo_metadata(path)
        if metadata.get("experiment_id", "exp1_alignment_transfer") != "exp1_alignment_transfer":
            continue
        memos.append((path, metadata))
    if not memos:
        return {
            "status": "ABSENT",
            "present": False,
            "memo_id": None,
            "reason": "NO_APPLICABLE_CHANGE_MEMO",
        }
    path, metadata = max(memos, key=lambda item: _memo_sort_key(*item))
    approved = metadata.get("approved_status", "").strip().lower() == "approved"
    authorized = (
        metadata.get("paper_promotion_authorized", "").strip().upper() == "YES"
    )
    present = approved and authorized
    return {
        "status": "PRESENT" if present else "ABSENT",
        "present": present,
        "memo_id": metadata.get("memo_id", path.stem),
        "memo_path": path.name,
        "approved_status": metadata.get("approved_status"),
        "paper_promotion_authorized": metadata.get(
            "paper_promotion_authorized"
        ),
        "reason": (
            "EXPLICIT_CURRENT_MEMO_AUTHORIZATION"
            if present
            else "LATEST_APPLICABLE_MEMO_DOES_NOT_AUTHORIZE_PAPER_PROMOTION"
        ),
    }


def _update_csv_paper_flag(path: Path) -> None:
    frame = pd.read_csv(path)
    if "paper_result" in frame.columns:
        frame["paper_result"] = True
    if "run_tier" in frame.columns:
        frame["run_tier"] = "paper"
    frame.to_csv(path, index=False)


def _update_json_paper_flag(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload["paper_result"] = True
        payload["run_tier"] = "paper"
        payload["promoted_at"] = utc_now()
    atomic_write_json(path, payload)


def promotion_provenance_audit(full: Path) -> dict[str, object]:
    """Stage-aware promotion gate; complete-tree equality is not required."""
    audit = audit_exp1_provenance(full, PROJECT_ROOT)
    checks = {
        "simulation_provenance_verified": bool(
            audit["simulation_provenance_verified"]
        ),
        "downstream_provenance_verified": bool(
            audit["downstream_provenance_verified"]
        ),
        "reporting_provenance_verified": bool(
            audit["reporting_provenance_verified"]
        ),
        "reconciliation_present_when_rebuilt": bool(
            not audit["run_lineage_present"]
            or not audit["reconciliation_artifact_present"]
            or audit["reconciliation_artifact_present"]
        ),
    }
    # A fresh inline run needs no reconciliation. A downstream-rebuilt or
    # reused run must have one; the explicit lineage avoids hash-only reuse.
    lineage_path = full / "metadata" / "exp1_run_lineage.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8")) if lineage_path.exists() else {}
    needs_reconciliation = (
        lineage.get("simulation_execution_mode") == "REUSED"
        or lineage.get("downstream_execution_mode") == "REBUILT"
    )
    checks["reconciliation_present_when_rebuilt"] = bool(
        not needs_reconciliation or audit["reconciliation_artifact_present"]
    )
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "decision": audit["decision"],
        "failure_reason": audit["failure_reason"],
        "audit": audit,
    }


def promotion_readiness(full: Path | None = None) -> dict[str, object]:
    """Evaluate every technical promotion gate without mutating any artifact."""
    full = full or OUTPUTS / "full"
    validation_path = STATUS / "full_validation_status.json"
    validation = (
        json.loads(validation_path.read_text(encoding="utf-8"))
        if validation_path.exists()
        else {}
    )
    provenance = (
        promotion_provenance_audit(full)
        if full.exists()
        else {"status": "FAIL", "checks": {}, "failure_reason": "FULL_MISSING"}
    )
    required = [
        full / "raw" / "exp1_path_manifest.parquet",
        full / "raw" / "exp1_route_diagnostic_rounds.parquet",
        full / "raw" / "exp1_learner_consequence_rounds.parquet",
        full / "raw" / "exp1_delay_source_rounds.parquet",
        full / "seed_metrics" / "exp1_route_seed_metrics.parquet",
        full / "seed_metrics" / "exp1_learner_seed_metrics.parquet",
        full / "derived" / "exp1_primary_summary.csv",
        full / "figures" / "pdf" / "fig_exp1_alignment_transfer.pdf",
        full / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv",
        full / "tables" / "tab_exp1_mechanism_summary.tex",
        full / "checks" / "exp1_validation_report.json",
        full / "targeted" / "exp1_targeted_validation_report.json",
        full / "targeted" / "exp1_targeted_theory_exact_shift_sweep.csv",
        full / "targeted" / "exp1_targeted_theory_margin_threshold_sweep.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    fallback_markers = [str(path) for path in full.rglob("*.fallback.json")]
    candidate_sources = [
        full / directory
        for directory in (
            "seed_metrics",
            "derived",
            "figures",
            "tables",
            "manuscript",
            "checks",
            "metadata",
            "targeted",
        )
    ]
    checks = {
        "full_output_exists": full.exists(),
        "full_validation_status_exists": validation_path.exists(),
        "full_validation_engineering_pass": validation.get("engineering_status")
        == "PASS",
        "full_validation_scientific_pass": validation.get("scientific_status")
        == "PASS",
        "stage_aware_provenance_pass": provenance.get("status") == "PASS",
        "scientific_generation_reuse_verified": bool(
            provenance.get("checks", {}).get("simulation_provenance_verified")
        ),
        "aggregation_validation_provenance_verified": bool(
            provenance.get("checks", {}).get("downstream_provenance_verified")
        ),
        "reporting_provenance_verified": bool(
            provenance.get("checks", {}).get("reporting_provenance_verified")
        ),
        "raw_immutability_verified": bool(
            provenance.get("audit", {}).get("raw_scientific_artifacts_unchanged")
        ),
        "required_artifacts_complete": not missing,
        "no_parquet_fallback_markers": not fallback_markers,
        "candidate_source_directories_complete": all(
            path.is_dir() for path in candidate_sources
        ),
    }
    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "technical_promotion_readiness": "PASS" if passed else "FAIL",
        "checks": checks,
        "missing_required_artifacts": missing,
        "fallback_markers": fallback_markers,
        "stage_aware_provenance": provenance,
        "paper_candidate_path": str(OUTPUTS / "paper_candidate"),
        "paper_candidate_exists_and_was_not_modified": (OUTPUTS / "paper_candidate").exists(),
    }


def dry_run_promotion() -> dict[str, object]:
    readiness = promotion_readiness()
    authorization = promotion_authorization()
    ready_except_authorization = (
        readiness["status"] == "PASS" and not authorization["present"]
    )
    return {
        "status": readiness["status"],
        "technical_promotion_readiness": readiness[
            "technical_promotion_readiness"
        ],
        "promotion_authorization": authorization["status"],
        "promotion_ready_except_authorization": ready_except_authorization,
        "actual_promotion_executed": False,
        "paper_result": False,
        "readiness": readiness,
        "authorization": authorization,
    }


def promote(force: bool = False) -> Path:
    full = OUTPUTS / "full"
    readiness = promotion_readiness(full)
    if readiness["status"] != "PASS":
        failed = [
            name for name, passed in readiness["checks"].items() if not passed
        ]
        raise RuntimeError(f"Paper promotion technical gates failed: {failed}")
    authorization = promotion_authorization()
    if not authorization["present"]:
        raise RuntimeError(
            "Paper promotion is blocked by the latest applicable change memo: "
            + str(authorization)
        )
    provenance = readiness["stage_aware_provenance"]

    candidate = OUTPUTS / "paper_candidate"
    if candidate.exists():
        if not force:
            raise FileExistsError("paper_candidate exists; use --force only after review")
        shutil.rmtree(candidate)
    candidate.mkdir(parents=True)
    for directory in ("seed_metrics", "derived", "figures", "tables", "manuscript", "checks", "metadata", "targeted"):
        source = full / directory
        if source.exists():
            shutil.copytree(source, candidate / directory)

    for path in candidate.rglob("*.csv"):
        _update_csv_paper_flag(path)
    for path in candidate.rglob("*.json"):
        try:
            _update_json_paper_flag(path)
        except json.JSONDecodeError:
            pass

    table_csv = candidate / "tables" / "tab_exp1_mechanism_summary.csv"
    if not table_csv.exists():
        raise RuntimeError("Paper candidate mechanism table CSV is missing")
    write_manuscript_artifacts(
        candidate / "manuscript",
        pd.read_csv(table_csv),
        run_tier="paper",
        paper_result=True,
    )
    figure_data = candidate / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv"
    figure_metadata = candidate / "figures" / "metadata" / "fig_exp1_alignment_transfer_metadata.json"
    if figure_data.exists() and figure_metadata.exists():
        payload = json.loads(figure_metadata.read_text(encoding="utf-8"))
        payload["source_figure_data"] = "figures/data/fig_exp1_alignment_transfer_data.csv"
        payload["source_figure_data_sha256"] = sha256_file(figure_data)
        payload["run_tier"] = "paper"
        payload["paper_result"] = True
        atomic_write_json(figure_metadata, payload)

    derived_figure_metadata = candidate / "figures" / "data" / "fig_exp1_alignment_transfer_metadata.json"
    if figure_data.exists() and derived_figure_metadata.exists():
        payload = json.loads(derived_figure_metadata.read_text(encoding="utf-8"))
        payload["source_derived_files"] = [
            "derived/exp1_route_summary.csv",
            "derived/exp1_learner_summary.csv",
            "derived/exp1_actual_learner_contrasts.csv",
        ]
        payload.pop("source_data_hash", None)
        payload["source_data_sha256"] = sha256_file(figure_data)
        payload["run_tier"] = "paper"
        payload["paper_result"] = True
        atomic_write_json(derived_figure_metadata, payload)

    artifact_records = []
    for path in sorted(candidate.rglob("*")):
        if path.is_file():
            artifact_records.append(
                {
                    "path": str(path.relative_to(candidate)),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    manifest = {
        "experiment_id": "exp1_alignment_transfer",
        "run_tier": "paper",
        "paper_result": True,
        "engineering_status": "PASS",
        "scientific_status": "PASS",
        "source_full_output": "outputs/full",
        "stage_aware_provenance": provenance,
        "artifacts": artifact_records,
        "promoted_at": utc_now(),
    }
    atomic_write_json(candidate / "exp1_promotion_manifest.json", manifest)
    atomic_write_json(
        STATUS / "paper_promotion_status.json",
        {
            "stage": "paper_promotion",
            "status": "PASS",
            "paper_result": True,
            "manifest": str(candidate / "exp1_promotion_manifest.json"),
            "generated_at": utc_now(),
        },
    )
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", choices=("full",), default="full")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    del args.run
    if args.dry_run:
        result = dry_run_promotion()
        print(json.dumps(result, indent=2))
        print(
            "TECHNICAL_PROMOTION_READINESS="
            + str(result["technical_promotion_readiness"])
        )
        print("PROMOTION_AUTHORIZATION=" + str(result["promotion_authorization"]))
        if result["promotion_ready_except_authorization"]:
            print("PROMOTION_READY_EXCEPT_AUTHORIZATION")
        print("ACTUAL_PROMOTION_EXECUTED=FALSE")
        return
    output = promote(force=args.force)
    print("PAPER_PROMOTION_COMPLETE")
    print("paper_result=true")
    print(f"output={output}")


if __name__ == "__main__":
    main()
