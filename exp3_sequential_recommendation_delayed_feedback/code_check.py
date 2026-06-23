"""Static source checks for the Exp3 v5.2 contract."""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
TEXT_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}
FORBIDDEN_TOKENS = [
    "rnn_proxy_history",
    "source_time_labelled",
    "most_recent_touch",
    "next-standard-exposure based",
    "concurrent random-intervention interactions but decision-source",
]
REQUIRED_TOKENS = [
    "fit_ridge_proxy",
    "predict_ridge_proxy",
    "history_mean_static",
    "source_aware_reference",
    "partial_source_label_q10",
    "fig_exp3_long_term_recoverability",
    "fig_app_exp3_horizon_eligibility",
    "paired_effect_vs_history_mean_static",
    "tbl_app_exp3_source_label_sensitivity",
    "paper_result",
    "most_recent_same_user_standard_exposure_at_or_before_arrival",
    "same_split_standard_log_only",
    "history_standard_only",
    "completed_history_plus_earlier_main_bins_only",
    "write_artifact_manifest",
]


def source_files() -> list[Path]:
    return [
        path for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
        and "outputs" not in path.parts and "__pycache__" not in path.parts
    ]


def main() -> int:
    errors: list[str] = []
    files = [path for path in source_files() if path.name != "code_check.py"]
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in files)
    for token in FORBIDDEN_TOKENS:
        if token in all_text:
            errors.append(f"forbidden legacy or misleading token found: {token}")
    for token in REQUIRED_TOKENS:
        if token not in all_text:
            errors.append(f"required contract token absent: {token}")

    for path in ROOT.rglob("*.py"):
        if "outputs" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"syntax error in {path.relative_to(ROOT)}: {exc}")

    proxy_source = (ROOT / "proxy_models.py").read_text(encoding="utf-8")
    if "global_composite = float(main_proxy" in proxy_source or "global_mean = float(proxy_cells" in proxy_source:
        errors.append("proxy fallback still uses a forbidden full-main aggregate")
    if "def history_mean_static_scores" not in proxy_source:
        errors.append("history-only static control is missing")

    bootstrap_source = (ROOT / "bootstrap_analysis.py").read_text(encoding="utf-8")
    for token in ["shared_bootstrap_weights", "paired_mechanism_contrast", "paired_effect_vs_history_mean_static"]:
        if token not in bootstrap_source:
            errors.append(f"bootstrap contract missing: {token}")

    plot_source = (ROOT / "plot_results.py").read_text(encoding="utf-8")
    if "def plot_delay_mechanism_appendix" in plot_source or "def plot_label_coverage_appendix" in plot_source:
        errors.append("retired appendix plots are still active")
    if "def plot_horizon_eligibility" not in plot_source:
        errors.append("horizon eligibility diagnostic is missing")

    self_check = (ROOT / "self_check.py").read_text(encoding="utf-8")
    if "retired figure remains active" not in self_check:
        errors.append("self-check does not guard against stale active retired figures")

    for output_dir in [ROOT / "outputs" / "fast", ROOT / "outputs" / "full"]:
        if output_dir.exists():
            checks_dir = output_dir / "checks"
            checks_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([{
                "check_id": "code_check",
                "status": "failed" if errors else "passed",
                "n_errors": len(errors),
                "details": " | ".join(errors) if errors else "CODE CHECK PASSED",
            }]).to_csv(checks_dir / "code_check_report.csv", index=False)

    if errors:
        print("CODE CHECK FAILED")
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    print("CODE CHECK PASSED")
    print("[PASS] chronology, history-only static control, and paired uncertainty contracts are present")
    print("[PASS] source-label sensitivity is table-only; unsupported active contrast plots are retired")
    print("[PASS] explanatory labels and eligibility diagnostic interfaces are present")
    print("[PASS] all Python modules parse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
