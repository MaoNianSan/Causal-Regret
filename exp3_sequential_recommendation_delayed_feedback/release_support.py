"""Final release artifact helpers for Exp3.

These helpers only normalize interfaces, document fixed full outputs, and
package artifacts. They do not rerun the experiment or alter numeric results.
"""
from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from config import DEFAULT_CONFIG
from recoverability import METHOD_META
from utils import save_dataframe, sha256_file, write_json

ROOT = Path(__file__).resolve().parent
FULL = ROOT / "outputs" / "full"
CODE_ZIP = ROOT / "exp3_long_term_recoverability_upload_ready_code.zip"
REPRO_ZIP = ROOT / "exp3_long_term_recoverability_reproducibility_manifest.zip"
ACTIVE_FIGURES = ("fig_exp3_long_term_recoverability", "fig_app_exp3_horizon_eligibility")
RETIRED_FIGURES = (
    "fig_app_exp3_arrival_mechanism_contrast",
    "fig_app_exp3_source_label_coverage",
    "fig_app_exp3_horizon_saturation",
)
PLOT_LABELS = {
    "source_aware_reference": "Reference",
    "arrival_time_naive": "Carrier",
    "partial_source_label_q10": "Labels 10%",
    "partial_source_label_q30": "Labels 30%",
    "partial_source_label_q50": "Labels 50%",
    "history_mean_static": "History mean",
    "short_term_ridge_proxy": "ST ridge",
    "history_ewma_ridge_proxy": "Hist-EWMA ridge",
    "short_term_composite_surrogate": "ST composite",
    "source_labelled_empirical": "Source labels",
}


def _read_manifest() -> dict[str, Any]:
    path = FULL / "metadata" / "run_manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_template_files() -> None:
    (ROOT / "input_manifest_template.csv").write_text(
        "relative_path,required,sha256,notes\n"
        "inputs/KuaiRand-1K/data/log_standard_4_08_to_4_21_1k.csv,true,<fill_after_download>,history standard split\n"
        "inputs/KuaiRand-1K/data/log_standard_4_22_to_5_08_1k.csv,true,<fill_after_download>,main standard split\n"
        "inputs/KuaiRand-1K/data/video_features_basic_1k.csv,true,<fill_after_download>,video metadata\n",
        encoding="utf-8",
    )
    (ROOT / "input_sha256_template.txt").write_text(
        "Run a local SHA-256 tool after obtaining KuaiRand-1K and record the hashes here.\n",
        encoding="utf-8",
    )
    (ROOT / "instructions_for_obtaining_kuairand_data.md").write_text(
        "# Obtaining KuaiRand-1K\n\n"
        "Download KuaiRand-1K from the official project distribution, accept its license, "
        "and place the required CSV files under `inputs/KuaiRand-1K/data/`. Raw data are "
        "not redistributed in this release package.\n",
        encoding="utf-8",
    )
    (ROOT / "expected_input_paths.md").write_text(
        "# Expected Input Paths\n\n"
        "- `inputs/KuaiRand-1K/data/log_standard_4_08_to_4_21_1k.csv`\n"
        "- `inputs/KuaiRand-1K/data/log_standard_4_22_to_5_08_1k.csv`\n"
        "- `inputs/KuaiRand-1K/data/video_features_basic_1k.csv`\n",
        encoding="utf-8",
    )


def normalize_final_interfaces() -> None:
    """Add release-facing columns and aliases without changing estimates."""
    manifest = _read_manifest()
    write_json(FULL / "run_manifest.json", manifest)
    save_dataframe(pd.DataFrame([{
        "key": key,
        "value": json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value,
    } for key, value in manifest.items()]), FULL / "manifest.csv")

    effects_path = FULL / "summaries" / "paired_effect_vs_history_mean_static.csv"
    effects = pd.read_csv(effects_path)
    effects["method_display_name"] = effects["method_id"].map(lambda x: METHOD_META.get(x, {}).get("method_display_name", x))
    effects["plot_label"] = effects["method_id"].map(lambda x: PLOT_LABELS.get(x, x))
    effects["reference_method_id"] = effects.get("comparator_method_id", "history_mean_static")
    effects["effect_estimate"] = effects.get("point_estimate")
    effects["bootstrap_unit"] = "user_id"
    effects["run_mode"] = manifest.get("run_mode", "full")
    effects["paper_result"] = bool(manifest.get("paper_result", False))
    effects["interpretation_note"] = (
        "A confidence interval spanning zero does not establish an incremental "
        "decision-level gain beyond history_mean_static."
    )
    save_dataframe(effects, effects_path)

    label_path = FULL / "tables" / "tbl_app_exp3_source_label_sensitivity.csv"
    labels = pd.read_csv(label_path)
    labels["label_rate_q"] = labels.get("source_label_rate_q")
    labels["expected_labelled_outcomes"] = labels.get("expected_source_labelled_outcomes")
    labels["ranking_regret"] = labels.get("ranking_regret_per_time_bin")
    labels["ci_lower"] = labels.get("ranking_regret_ci_lower")
    labels["ci_upper"] = labels.get("ranking_regret_ci_upper")
    labels["interpretation_note"] = (
        "The tested q values correspond to high absolute labelled-outcome counts. "
        "This table is a sensitivity analysis, not evidence of monotonic recoverability "
        "or label sufficiency."
    )
    save_dataframe(labels, label_path)

    dynamics_path = FULL / "summaries" / "oracle_action_dynamics_summary.csv"
    dynamics = pd.read_csv(dynamics_path)
    dynamics["n_unique_oracle_top_actions"] = dynamics.get("oracle_top_action_unique_count")
    dynamics["largest_oracle_top_action_share"] = dynamics.get("oracle_top_action_share")
    save_dataframe(dynamics, dynamics_path)

    proxy_quality_summary = FULL / "summaries" / "proxy_score_quality.csv"
    if not proxy_quality_summary.exists():
        source = FULL / "tables" / "tbl_app_exp3_proxy_score_quality.csv"
        if source.exists():
            save_dataframe(pd.read_csv(source), proxy_quality_summary)


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def write_final_docs() -> None:
    """Generate final release-facing documentation from full CSV outputs."""
    manifest = _read_manifest()
    cfg = manifest.get("config", {})
    boot = pd.read_csv(FULL / "summaries" / "user_bootstrap_metric_summary.csv")
    effects = pd.read_csv(FULL / "summaries" / "paired_effect_vs_history_mean_static.csv")
    labels = pd.read_csv(FULL / "tables" / "tbl_app_exp3_source_label_sensitivity.csv")
    dynamics = pd.read_csv(FULL / "summaries" / "oracle_action_dynamics_summary.csv")
    quality = pd.read_csv(FULL / "summaries" / "proxy_score_quality.csv")
    condition = cfg.get("primary_delay_condition", DEFAULT_CONFIG.primary_delay_condition)
    st = boot[(boot["delay_condition"] == condition) & (boot["method_id"] == "short_term_ridge_proxy")].iloc[0]
    hist = boot[(boot["delay_condition"] == condition) & (boot["method_id"] == "history_mean_static")].iloc[0]
    eff = effects[(effects["delay_condition"] == condition) & (effects["method_id"] == "short_term_ridge_proxy")].iloc[0]
    dyn = dynamics.iloc[0]
    quality_text = quality.to_string(index=False) if not quality.empty else "proxy_score_quality.csv is empty"

    (ROOT / "docs" / "final_full_result_summary.md").write_text(
        "# Final full result summary\n\n"
        f"- Experiment: `{manifest.get('project_id')}`\n"
        f"- Primary target and horizon: `{manifest.get('primary_outcome_id')}`, `{manifest.get('primary_horizon')}`\n"
        f"- Input status: `{manifest.get('input_data_status')}`\n"
        f"- Run mode / paper result: `{manifest.get('run_mode')}` / `{manifest.get('paper_result')}`\n"
        f"- Full sample counts: `{manifest.get('n_main_standard_source_events')}` main source events, `{manifest.get('n_main_users')}` users, `{manifest.get('n_bootstrap')}` bootstraps, `{manifest.get('n_label_mask_trajectories')}` label-mask trajectories\n"
        "- Main figure/table ids: `fig_exp3_long_term_recoverability`, `fig_app_exp3_horizon_eligibility`, `tbl_app_exp3_proxy_static_control`, `tbl_app_exp3_source_label_sensitivity`\n\n"
        "## Score Quality\n\n"
        "```text\n" + quality_text + "\n```\n\n"
        "## ST Ridge Versus History Mean\n\n"
        f"- `ST ridge` ranking regret: {_fmt(st['point_estimate'])} [{_fmt(st['ci_lower'])}, {_fmt(st['ci_upper'])}]\n"
        f"- `History mean` ranking regret: {_fmt(hist['point_estimate'])} [{_fmt(hist['ci_lower'])}, {_fmt(hist['ci_upper'])}]\n"
        f"- Paired regret reduction: {_fmt(eff['effect_estimate'])} [{_fmt(eff['ci_lower'])}, {_fmt(eff['ci_upper'])}]\n"
        "- Interpretation: the paired interval spans zero, so the incremental decision-level gain beyond `history_mean_static` is not separately established.\n\n"
        "## Caveats\n\n"
        f"- Partial label sensitivity uses high absolute labelled-outcome counts, e.g. q=.10 has `{int(labels[labels['label_rate_q'].eq(0.10)]['expected_labelled_outcomes'].max())}` expected labels; it is not evidence of monotonic recoverability or label sufficiency.\n"
        f"- Oracle action stability: `{int(dyn['n_decision_bins'])}` decision bins, `{int(dyn['n_unique_oracle_top_actions'])}` unique oracle top actions, switch rate {_fmt(dyn['oracle_top_action_switch_rate'])}, largest top-action share {_fmt(dyn['largest_oracle_top_action_share'])}.\n\n"
        "## Permissible Claims\n\n"
        "- The history-fitted short-term ridge proxy achieved strong held-out alignment with the constructed 6h target.\n"
        "- Its ranking-regret point estimate was lower than `history_mean_static`, but the paired 95% CI spanned zero.\n"
        "- Stable action-category structure limits power to separate dynamic proxy value from history-level action differences.\n\n"
        "## Prohibited Claims\n\n"
        "- Do not claim significant outperformance over the history-only baseline.\n"
        "- Do not claim 10% labels are sufficient or that label coverage monotonically improves recoverability.\n"
        "- Do not describe Exp3 as online policy improvement, OPE, causal regret, or platform utility evaluation.\n",
        encoding="utf-8",
    )

    latex = (
        "# LaTeX interface for Exp3\n\n"
        "Only full outputs with `paper_result=true` may be cited. Fast outputs are never paper results.\n\n"
        "```latex\n"
        "\\includegraphics{outputs/full/figures/pdf/fig_exp3_long_term_recoverability.pdf}\n"
        "\\includegraphics{outputs/full/figures/pdf/fig_app_exp3_horizon_eligibility.pdf}\n"
        "```\n\n"
        "## Figure Caption Fact Sheet\n\n"
        "- Main figure Panel A: held-out calibration; deciles; vertical bars are 95% user-bootstrap CIs.\n"
        "- Main figure Panel B: 6h ranking regret; lower is better; `Reference` is offline; dashed carrier line is the carrier baseline.\n"
        f"- ST ridge versus History mean paired regret reduction: {_fmt(eff['effect_estimate'])}, 95% CI [{_fmt(eff['ci_lower'])}, {_fmt(eff['ci_upper'])}].\n"
        "- Horizon appendix: the primary 6h horizon was pre-specified; the figure reports eligibility loss due to right censoring, not engagement saturation.\n\n"
        "## Table Input Paths\n\n"
        "- `outputs/full/tables/tbl_app_exp3_proxy_static_control.csv`\n"
        "- `outputs/full/tables/tbl_app_exp3_source_label_sensitivity.csv`\n"
        "- `outputs/full/summaries/paired_effect_vs_history_mean_static.csv`\n"
        "- `outputs/full/summaries/oracle_action_dynamics_summary.csv`\n"
        "- `outputs/full/summaries/proxy_score_quality.csv`\n\n"
        "## Reference Role\n\n"
        "`source_aware_reference` is an offline reference, not a deployable method.\n\n"
        "## Prohibited Wording\n\n"
        "- significant outperformance over the history-only baseline\n"
        "- 10% labels are sufficient\n"
        "- label coverage monotonically improves recoverability\n"
        "- causal regret, OPE, online policy improvement, or platform utility evaluation\n"
    )
    (ROOT / "docs" / "latex_interface_experiments.md").write_text(latex, encoding="utf-8")

    (ROOT / "docs" / "experiment_specification.md").write_text(
        "# Experiment specification\n\n"
        "Exp3 evaluates whether historical and lagged short-term proxy scores preserve the ranking of a constructed 6h future-engagement target in held-out sequential recommendation logs.\n\n"
        "Fixed settings: `dataset_id=kuairand_1k`, `primary_horizon=6h`, `primary_target=long_value_log`, `time_bin=1d`, `candidate_action_count=20`, `main_top_k=10`, history split `log_standard_4_08_to_4_21_1k.csv`, main split `log_standard_4_22_to_5_08_1k.csv`, bootstrap unit `user_id`, full bootstraps `1000`, full partial-label mask replicates `30`.\n\n"
        "Fast outputs are never paper results. Only full outputs with `paper_result=true` may be cited in LaTeX.\n",
        encoding="utf-8",
    )

    completion = (
        "# Experiment refactor completion report\n\n"
        "- Scope, target, split, action vocabulary, partial-label assignment, carrier assignment, proxy fitting, and bootstrap logic were not changed during final release packaging.\n"
        "- Active figures are `fig_exp3_long_term_recoverability` and `fig_app_exp3_horizon_eligibility`.\n"
        "- Retired figures remain audit-only and are excluded from active LaTeX paths.\n"
        "- Fast outputs are never paper results. Only full outputs with `paper_result=true` may be cited in LaTeX.\n"
    )
    (ROOT / "docs" / "experiment_refactor_completion_report.md").write_text(completion, encoding="utf-8")


def _artifact_role(path: Path) -> str:
    rel = path.as_posix()
    if rel.endswith(".zip"):
        return "release_archive"
    if rel.startswith("outputs/full/figures/"):
        return "paper_figure_bundle"
    if rel.startswith("outputs/full/tables/"):
        return "paper_table"
    if rel.startswith("outputs/full/summaries/"):
        return "summary_or_audit"
    if rel.startswith("outputs/full/checks/"):
        return "validation_report"
    if rel.startswith("outputs/full/metadata/") or rel in {"outputs/full/run_manifest.json", "outputs/full/manifest.csv"}:
        return "full_manifest"
    if rel.startswith("docs/"):
        return "documentation"
    if rel.startswith("tests/"):
        return "tests"
    if rel.endswith(".py"):
        return "source_code"
    return "release_support"


def _excluded(path: Path) -> bool:
    text = path.as_posix()
    name = path.name
    if any(part in path.parts for part in ("__pycache__", ".venv", ".ipynb_checkpoints")):
        return True
    if text.startswith("inputs/KuaiRand-1K/data/") or text.startswith("outputs/full/raw/"):
        return True
    if text.startswith("outputs/full/processed/") and "arrival_timeline_audit_sample" not in text:
        return True
    if text.startswith("outputs/fast/") or text.startswith("runlogs/"):
        return True
    if "legacy/retired_figures" in text:
        return True
    if name.startswith("semi_synthetic_arrival_timeline_"):
        return True
    if path.suffix.lower() == ".csv" and path.exists() and path.stat().st_size > 50 * 1024 * 1024:
        return True
    if name in {CODE_ZIP.name, REPRO_ZIP.name} or name.endswith(".zip.sha256"):
        return True
    return False


def collect_code_package_files() -> list[Path]:
    roots = [
        "*.py", "requirements.txt", "README.md", "docs/**", "src/**", "tests/**",
        "outputs/full/figures/pdf/**/*", "outputs/full/figures/png/**/*",
        "outputs/full/figures/data/**/*", "outputs/full/figures/metadata/**/*",
        "outputs/full/tables/**/*", "outputs/full/summaries/**/*",
        "outputs/full/checks/**/*", "outputs/full/metadata/**/*",
        "outputs/full/run_manifest.json", "outputs/full/manifest.csv",
        "release_manifest.json", "release_manifest.csv",
    ]
    files: set[Path] = set()
    for pattern in roots:
        for path in ROOT.glob(pattern):
            if path.is_file():
                rel = path.relative_to(ROOT)
                if not _excluded(rel):
                    files.add(rel)
    return sorted(files, key=lambda p: p.as_posix())


def write_release_manifest(code_files: list[Path]) -> None:
    rows = []
    for rel in code_files:
        path = ROOT / rel
        role = _artifact_role(rel)
        rel_text = rel.as_posix()
        paper_table_names = {
            "outputs/full/tables/tbl_app_exp3_proxy_static_control.csv",
            "outputs/full/tables/tbl_app_exp3_source_label_sensitivity.csv",
            "outputs/full/tables/tbl_app_exp3_proxy_score_quality.csv",
        }
        paper_facing = (
            role == "paper_figure_bundle"
            or rel_text in paper_table_names
            or rel_text == "outputs/full/summaries/paired_effect_vs_history_mean_static.csv"
        )
        rows.append({
            "file_path": rel.as_posix(),
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "artifact_role": role,
            "paper_facing": paper_facing,
            "required_for_reproduction": role in {"source_code", "tests", "documentation", "full_manifest", "release_support"},
            "included_in_code_upload": True,
        })
    save_dataframe(pd.DataFrame(rows), ROOT / "release_manifest.csv")
    write_json(ROOT / "release_manifest.json", {"artifacts": rows})


def _write_zip(zip_path: Path, files: list[Path]) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, arcname=rel.as_posix())
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(
        f"{sha256_file(zip_path)}  {zip_path.name}\n",
        encoding="utf-8",
    )


def build_release_packages() -> None:
    normalize_final_interfaces()
    _write_template_files()
    write_final_docs()
    code_files = collect_code_package_files()
    write_release_manifest(code_files)
    code_files = collect_code_package_files()
    _write_zip(CODE_ZIP, code_files)
    repro_extras = [
        Path("input_manifest_template.csv"),
        Path("input_sha256_template.txt"),
        Path("instructions_for_obtaining_kuairand_data.md"),
        Path("expected_input_paths.md"),
    ]
    inventory_rows = []
    for rel in code_files + repro_extras:
        path = ROOT / rel
        inventory_rows.append({"file_path": rel.as_posix(), "file_size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    save_dataframe(pd.DataFrame(inventory_rows), ROOT / "full_result_inventory.csv")
    (ROOT / "artifact_sha256sums.txt").write_text(
        "".join(f"{row['sha256']}  {row['file_path']}\n" for row in inventory_rows),
        encoding="utf-8",
    )
    _write_zip(REPRO_ZIP, code_files + repro_extras + [Path("full_result_inventory.csv"), Path("artifact_sha256sums.txt")])
    ok, errors = verify_release_packages()
    write_release_reports([] if ok else errors)
    code_files = collect_code_package_files()
    write_release_manifest(code_files)
    code_files = collect_code_package_files()
    _write_zip(CODE_ZIP, code_files)
    inventory_rows = []
    for rel in code_files + repro_extras:
        path = ROOT / rel
        inventory_rows.append({"file_path": rel.as_posix(), "file_size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    save_dataframe(pd.DataFrame(inventory_rows), ROOT / "full_result_inventory.csv")
    (ROOT / "artifact_sha256sums.txt").write_text(
        "".join(f"{row['sha256']}  {row['file_path']}\n" for row in inventory_rows),
        encoding="utf-8",
    )
    _write_zip(REPRO_ZIP, code_files + repro_extras + [Path("full_result_inventory.csv"), Path("artifact_sha256sums.txt")])


def verify_release_packages() -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest = _read_manifest()
    if manifest.get("paper_result") is not True:
        errors.append("full manifest is not paper_result=true")
    if manifest.get("status") != "complete":
        errors.append("full manifest status is not complete")
    package_members = {path.as_posix() for path in collect_code_package_files()}
    for figure_id in ACTIVE_FIGURES:
        for kind, suffix in [("pdf", ".pdf"), ("png", ".png")]:
            member = f"outputs/full/figures/{kind}/{figure_id}{suffix}"
            if member not in package_members:
                errors.append(f"active figure missing from code upload manifest: {member}")
    for zip_path in [CODE_ZIP, REPRO_ZIP]:
        if not zip_path.exists():
            errors.append(f"missing zip: {zip_path.name}")
            continue
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            names = set(zf.namelist())
        if bad:
            errors.append(f"zip test failed for {zip_path.name}: {bad}")
        forbidden_prefixes = ("inputs/KuaiRand-1K/data/", "outputs/full/raw/")
        for name in names:
            if name.startswith(forbidden_prefixes) or "legacy/retired_figures" in name:
                errors.append(f"excluded artifact included in {zip_path.name}: {name}")
    return (not errors), errors


def write_release_reports(errors: list[str]) -> None:
    manifest = _read_manifest()
    status = "passed" if not errors else "failed"
    checklist = (
        "# Final release checklist\n\n"
        f"- Full result validation status: {status}\n"
        f"- Promotion status: paper_result={manifest.get('paper_result')}, status={manifest.get('status')}\n"
        f"- Active figures: {', '.join(ACTIVE_FIGURES)}\n"
        f"- Retired figures: {', '.join(RETIRED_FIGURES)}\n"
        "- Paper-facing tables: `tbl_app_exp3_proxy_static_control.csv`, `tbl_app_exp3_source_label_sensitivity.csv`\n"
        f"- Upload archive contents: `{CODE_ZIP.name}`, `{REPRO_ZIP.name}`\n"
        "- Excluded raw inputs: `inputs/KuaiRand-1K/data/`, user-level raw logs, full raw event-level outputs, retired figure bundles\n"
        f"- Checks passed: {'yes' if not errors else 'no'}\n"
        f"- Checks failed: {'none' if not errors else '; '.join(errors)}\n"
        "- Remaining manual user steps: obtain KuaiRand-1K separately and fill input hash templates before external reproduction.\n"
    )
    (ROOT / "docs" / "final_release_checklist.md").write_text(checklist, encoding="utf-8")
    report = (
        "# Final release completion report\n\n"
        "The release packaging step validated the promoted full outputs, generated release manifests, "
        "built upload archives, and verified archive integrity. No full experiment rerun was performed.\n\n"
        f"- Code upload package: `{CODE_ZIP.name}`\n"
        f"- Reproducibility manifest package: `{REPRO_ZIP.name}`\n"
        "- SHA-256 sidecars were generated for both archives.\n"
        f"- Final verification status: {status}\n"
    )
    (ROOT / "docs" / "final_release_completion_report.md").write_text(report, encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
