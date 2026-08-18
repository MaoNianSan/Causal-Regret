"""Read-only submission-companion validator for the Causal-Regret repository.

Checks that the repository is in the state promised by the paper and by
docs/EXPERIMENT_IO_CONTRACT.md, without running any experiment and without
modifying any artifact.

Exit code 0 = PASS, 1 = FAIL. Run from the repository root:

    python scripts/validate_submission_repository.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Canonical result roots (paper-facing, paper_result=true).
CANONICAL = {
    "exp1": ROOT / "exp1_alignment_transfer" / "outputs" / "paper_candidate",
    "exp2": (
        ROOT
        / "exp2_real_delayed_conversion_logs"
        / "outputs"
        / "paper"
        / "exp2-full-20260807T111616+0800"
    ),
    "exp3": ROOT / "exp3_sequential_recommendation_delayed_feedback" / "paper_candidate",
    "exp4": (
        ROOT
        / "exp4_controlled_route_audit"
        / "outputs"
        / "runs"
        / "full_20260817T071019Z_7d7146b7"
    ),
}

# Publication bundle figure IDs and the five per-figure artifacts.
MAIN_FIGURES = {
    "exp1": "fig_exp1_alignment_transfer",
    "exp2": "figure_exp2_attribution_sensitivity",
    "exp3": "exp3_main_score_gap_ranking",
    "exp4": "fig_exp4_route_alignment_and_audit_reliability",
}
PUB = ROOT / "publication" / "CR-EXP-OUTPUT-V1"
EXT_SUFFIX = {
    "pdf": ".pdf",
    "svg": ".svg",
    "png": ".png",
    "data": ".csv",
    "metadata": ".json",
}

# Paper-facing long-form main-figure CSVs (publication bundle, standardized schema).
MAIN_CSV = {
    "exp1": PUB / "exp1_alignment_transfer" / "figures" / "main" / "data" / "fig_exp1_alignment_transfer.csv",
    "exp2": PUB / "exp2_real_delayed_conversion_logs" / "figures" / "main" / "data" / "figure_exp2_attribution_sensitivity.csv",
    "exp3": PUB / "exp3_sequential_recommendation_delayed_feedback" / "figures" / "main" / "data" / "exp3_main_score_gap_ranking.csv",
    "exp4": PUB / "exp4_controlled_route_audit" / "figures" / "main" / "data" / "fig_exp4_route_alignment_and_audit_reliability.csv",
}

REQUIRED_LONG_FORM_COLUMNS = [
    "metric_id",
    "estimand_id",
    "condition_id",
    "series_id",
    "point_estimate",
    "interval_lower",
    "interval_upper",
]

CHECK_BASENAME = {
    "exp1": "fig_exp1_alignment_transfer",
    "exp2": "figure_exp2_attribution_sensitivity",
    "exp3": "exp3_main_score_gap_ranking",
    "exp4": "fig_exp4_route_alignment_and_audit_reliability",
}

UNCERTAINTY_FILES = {
    # publication metadata JSON with uncertainty semantics
    "exp2": PUB / "exp2_real_delayed_conversion_logs" / "figures" / "main" / "metadata" / "figure_exp2_attribution_sensitivity.json",
    "exp3": PUB / "exp3_sequential_recommendation_delayed_feedback" / "figures" / "main" / "metadata" / "exp3_main_score_gap_ranking.json",
    "exp4": PUB / "exp4_controlled_route_audit" / "figures" / "main" / "metadata" / "fig_exp4_route_alignment_and_audit_reliability.json",
}

EXPERIMENT_DIR = {
    "exp1": "exp1_alignment_transfer",
    "exp2": "exp2_real_delayed_conversion_logs",
    "exp3": "exp3_sequential_recommendation_delayed_feedback",
    "exp4": "exp4_controlled_route_audit",
}

# Canonical IDs as they appear in README.md and docs/PAPER_RESULTS.md.
README_CANONICAL_TOKENS = {
    "exp1": "exp1_alignment_transfer/outputs/paper_candidate/",
    "exp2": "exp2-full-20260807T111616+0800",
    "exp3": "exp3-full-20260807T072340Z",
    "exp4": "full_20260817T071019Z_7d7146b7",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(checks: list[tuple[str, bool, str]]) -> bool:
    all_ok = True
    for name, ok, detail in checks:
        all_ok = all_ok and ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return all_ok


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    # A. Four canonical result roots exist.
    for key, path in CANONICAL.items():
        checks.append(
            (f"A:{key}_canonical_exists", path.is_dir(), str(path))
        )

    # B. paper_result / promotion status.
    # Exp1
    m1 = (
        read_json(CANONICAL["exp1"] / "exp1_promotion_manifest.json")
        if (CANONICAL["exp1"] / "exp1_promotion_manifest.json").exists()
        else {}
    )
    checks.append(
        ("B:exp1_paper_result", m1.get("paper_result") is True, "exp1_promotion_manifest.json")
    )
    # Exp2
    m2 = (
        read_json(CANONICAL["exp2"] / "run_manifest.json")
        if (CANONICAL["exp2"] / "run_manifest.json").exists()
        else {}
    )
    checks.append(
        ("B:exp2_paper_result", m2.get("paper_result") is True, "exp2 run_manifest.json")
    )
    checks.append(
        (
            "B:exp2_promotion_status",
            m2.get("paper_promotion_status") == "PROMOTED",
            str(m2.get("paper_promotion_status")),
        )
    )
    # Exp3
    m3 = (
        read_json(CANONICAL["exp3"] / "manifest.json")
        if (CANONICAL["exp3"] / "manifest.json").exists()
        else {}
    )
    checks.append(("B:exp3_paper_result", m3.get("paper_result") is True, "exp3 manifest.json"))
    # Exp4
    s4 = (
        read_json(CANONICAL["exp4"] / "logs" / "exp4_result_status.json")
        if (CANONICAL["exp4"] / "logs" / "exp4_result_status.json").exists()
        else {}
    )
    checks.append(("B:exp4_paper_result", s4.get("paper_result") is True, "exp4_result_status.json"))
    checks.append(
        (
            "B:exp4_promotion",
            s4.get("paper_promotion") == "PASS",
            str(s4.get("paper_promotion")),
        )
    )
    checks.append(
        (
            "B:exp4_schema_v3",
            s4.get("result_schema") == "exp4_controlled_route_audit_v3",
            str(s4.get("result_schema")),
        )
    )

    # C. Canonical paper-facing main-figure long-form CSVs and required columns.
    import pandas as pd  # local import keeps the script import-light until used

    for key, path in MAIN_CSV.items():
        if not path.exists():
            checks.append((f"C:{key}_main_csv", False, f"missing {path}"))
            continue
        try:
            frame = pd.read_csv(path)
            missing = [c for c in REQUIRED_LONG_FORM_COLUMNS if c not in frame.columns]
            checks.append(
                (f"C:{key}_main_csv_columns", not missing, f"missing={missing}")
            )
        except Exception as exc:  # noqa: BLE001
            checks.append((f"C:{key}_main_csv_readable", False, str(exc)))

    # D. Publication main figures: pdf/svg/png/csv/json.
    for key, fid in MAIN_FIGURES.items():
        for ext, suffix in EXT_SUFFIX.items():
            path = PUB / EXPERIMENT_DIR[key] / "figures" / "main" / ext / (fid + suffix)
            ok = path.exists() and path.stat().st_size > 0
            checks.append((f"D:{key}_{ext}", ok, str(path)))

    # E. Appendix publication artifacts (>=3 composite PDFs per experiment).
    for key in MAIN_FIGURES:
        appendix_pdfs = list(
            (PUB / EXPERIMENT_DIR[key] / "figures" / "appendix" / "pdf").glob("*.pdf")
        )
        checks.append(
            (f"E:{key}_appendix", len(appendix_pdfs) >= 3, f"{len(appendix_pdfs)} pdfs")
        )
        checks.append(
            (
                f"E:{key}_appendix_manifest",
                (PUB / EXPERIMENT_DIR[key] / "manifests" / "appendix_manifest.json").exists(),
                str(PUB / EXPERIMENT_DIR[key] / "manifests" / "appendix_manifest.json"),
            )
        )

    # F. Overview table (per experiment + at least one overall).
    overview = PUB / EXPERIMENT_DIR["exp1"] / "tables" / "csv" / "tab_experimental_evidence_map.csv"
    checks.append(("F:overview_table", overview.exists(), str(overview)))

    # G. Publication validation = PASS for all four experiments.
    for key in MAIN_FIGURES:
        vp = PUB / EXPERIMENT_DIR[key] / "validation" / "presentation_validation.json"
        passed = False
        if vp.exists():
            v = read_json(vp)
            passed = v.get("passed") is True
        checks.append((f"G:{key}_pub_validation", passed, str(vp)))

    # H. Exp2/Exp3 uncertainty metadata must not present the range as a CI.
    for key in ("exp2", "exp3"):
        path = UNCERTAINTY_FILES[key]
        bad = True
        if path.exists():
            meta = read_json(path)
            text = " ".join(
                str(meta.get(k, ""))
                for k in ("uncertainty_definition", "uncertainty_semantics")
            ).lower()
            claims_ci = ("confidence interval" in text) and ("not a confidence interval" not in text)
            has_range = "sensitivity range" in text or "resampling" in text
            bad = claims_ci or not has_range
        checks.append((f"H:{key}_not_ci", not bad, path.name if path.exists() else "missing"))

    # I. Exp4 main metric metadata = D_pair (not legacy max defect).
    meta4 = (
        read_json(UNCERTAINTY_FILES["exp4"])
        if UNCERTAINTY_FILES["exp4"].exists()
        else {}
    )
    panels = meta4.get("panel_definitions", {})
    panel_a = str(panels.get("a", ""))
    checks.append(
        ("I:exp4_panel_a_dpair", "D_pair" in panel_a and "max" not in panel_a.lower(), panel_a)
    )
    exclusions = meta4.get("presentation_contract", {}).get("panel_a_exclusions", [])
    checks.append(
        (
            "I:exp4_legacy_excluded",
            any("population_action_gap" in str(e) for e in exclusions),
            str(exclusions),
        )
    )

    # J. Source lineage present in publication metadata.
    for key in MAIN_FIGURES:
        meta_path = PUB / EXPERIMENT_DIR[key] / "figures" / "main" / "metadata" / (CHECK_BASENAME[key] + ".json")
        lineage = ""
        if meta_path.exists():
            meta = read_json(meta_path)
            lineage = str(meta.get("scientific_source_lineage", ""))
        checks.append(
            (f"J:{key}_source_lineage", bool(lineage) and lineage != "NA", f"{len(lineage)} chars")
        )

    # K. README / PAPER_RESULTS canonical IDs agree with actual paths.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    paper_results = (ROOT / "docs" / "PAPER_RESULTS.md").read_text(encoding="utf-8")
    for key, token in README_CANONICAL_TOKENS.items():
        checks.append((f"K:README_{key}", token in readme, token))
        checks.append((f"K:PAPER_RESULTS_{key}", token in paper_results, token))

    # L. Publication bundle fully tracked in git.
    git_files = set(
        subprocess.run(
            ["git", "ls-files", "publication/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()
    )
    on_disk = [str(p.relative_to(ROOT)).replace("\\", "/") for p in PUB.rglob("*") if p.is_file()]
    untracked = sorted(set(on_disk) - set(git_files))
    checks.append(("L:pub_all_tracked", not untracked, f"untracked={len(untracked)}"))

    ok = check(checks)
    print("SUBMISSION_REPOSITORY_VALIDATION = " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
