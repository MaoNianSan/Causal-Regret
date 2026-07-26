from __future__ import annotations

"""Independent paper-promotion gate for completed full Exp1 artifacts."""

import argparse
import json
from pathlib import Path
import shutil

from src.derived import write_manuscript_artifacts

import pandas as pd

from src.artifact_io import atomic_write_json, hash_payload, sha256_file, utc_now


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS = PROJECT_ROOT / "outputs"
STATUS = PROJECT_ROOT / "status"


def _change_memo_approved() -> bool:
    memos = sorted(PROJECT_ROOT.glob("CHANGE_MEMO_EXP1_*.md"))
    return all("approved_status: approved" in memo.read_text(encoding="utf-8").lower() for memo in memos)


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


def promote(force: bool = False) -> Path:
    validation_path = STATUS / "full_validation_status.json"
    if not validation_path.exists():
        raise RuntimeError("Paper promotion requires a completed full validation status")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if validation.get("engineering_status") != "PASS" or validation.get("scientific_status") != "PASS":
        raise RuntimeError("Full engineering and scientific status must both be PASS")
    if not _change_memo_approved():
        raise RuntimeError(
            "Paper promotion is blocked: CHANGE_MEMO_EXP1_001 has not been explicitly approved"
        )

    full = OUTPUTS / "full"
    if not full.exists():
        raise RuntimeError("Full output directory is missing")
    fallback_markers = list(full.rglob("*.fallback.json"))
    if fallback_markers:
        raise RuntimeError(
            "Paper promotion is blocked because development CSV parquet fallbacks exist: "
            + ", ".join(str(path) for path in fallback_markers)
        )
    required = [
        full / "raw" / "exp1_path_manifest.parquet",
        full / "raw" / "exp1_route_diagnostic_rounds.parquet",
        full / "raw" / "exp1_learner_consequence_rounds.parquet",
        full / "figures" / "pdf" / "fig_exp1_alignment_transfer.pdf",
        full / "figures" / "data" / "fig_exp1_alignment_transfer_data.csv",
        full / "tables" / "tab_exp1_mechanism_summary.tex",
        full / "checks" / "exp1_validation_report.json",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Paper promotion missing required artifacts: {missing}")

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
    args = parser.parse_args()
    del args.run
    output = promote(force=args.force)
    print("PAPER_PROMOTION_COMPLETE")
    print("paper_result=true")
    print(f"output={output}")


if __name__ == "__main__":
    main()
