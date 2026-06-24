"""Release packaging and integrity verification for promoted Exp3 full outputs.

These helpers never rerun the experiment or alter numeric estimates.  They only
assemble release-facing files after a successful full-data promotion.
"""
from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable

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
RELEASE_MANIFEST_FILES = (Path("release_manifest.csv"), Path("release_manifest.json"))
REPRO_EXTRAS = (
    Path("input_manifest_template.csv"),
    Path("input_sha256_template.txt"),
    Path("instructions_for_obtaining_kuairand_data.md"),
    Path("expected_input_paths.md"),
)
REQUIRED_RELEASE_DOCS = (
    Path("docs/final_release_checklist.md"),
    Path("docs/final_release_completion_report.md"),
    Path("docs/final_full_result_summary.md"),
    Path("docs/latex_interface_experiments.md"),
)
REQUIRED_NOTEBOOK_AUDIT_FILES = (
    Path("notebooks/exp3_figure_release_audit.ipynb"),
    Path("notebooks/README.md"),
    Path("outputs/full/checks/figure_release_audit.csv"),
    Path("outputs/full/checks/figure_release_audit.md"),
    Path("outputs/full/checks/exp3_figure_release_audit_executed.ipynb"),
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
    """Add release-facing aliases without changing estimates or figures."""
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
    """Generate release-facing documentation from final full CSV outputs."""
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
        "- The short-term ridge proxy has strong held-out score-level alignment with the constructed 6h target. Its point-estimated ranking regret is lower than the history-only static control, but the paired interval against the static control spans zero under daily aggregation.\n"
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
        "- Main figure Panel A uses held-out prediction deciles.\n"
        "- Main figure Panel A vertical whiskers are 95% user-bootstrap CI.\n"
        "- Main figure Panel B horizontal whiskers are 95% user-bootstrap CI.\n"
        "- Carrier is a baseline assignment route.\n"
        "- Reference is offline and non-deployable.\n"
        "- ST ridge versus History mean paired comparison spans zero.\n"
        f"- ST ridge versus History mean paired regret reduction: {_fmt(eff['effect_estimate'])}, 95% CI [{_fmt(eff['ci_lower'])}, {_fmt(eff['ci_upper'])}].\n"
        "- Horizon figure: 6h is prespecified.\n"
        "- Horizon figure reports right-censoring availability only.\n"
        "- Horizon figure does not establish engagement saturation.\n\n"
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
    (ROOT / "docs" / "experiment_refactor_completion_report.md").write_text(
        "# Experiment refactor completion report\n\n"
        "- Scope, target, split, action vocabulary, partial-label assignment, carrier assignment, proxy fitting, and bootstrap logic were not changed during final release packaging.\n"
        "- Active figures are `fig_exp3_long_term_recoverability` and `fig_app_exp3_horizon_eligibility`.\n"
        "- Retired figures remain audit-only and are excluded from active LaTeX paths.\n"
        "- Fast outputs are never paper results. Only full outputs with `paper_result=true` may be cited in LaTeX.\n",
        encoding="utf-8",
    )


def _artifact_role(path: Path) -> str:
    rel = path.as_posix()
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
    if name in {CODE_ZIP.name, REPRO_ZIP.name, "artifact_sha256sums.txt", "full_result_inventory.csv"}:
        return True
    if name.endswith(".zip.sha256"):
        return True
    return False


def _base_package_files() -> list[Path]:
    patterns = [
        "*.py", "requirements.txt", "README.md", "docs/**", "notebooks/**", "src/**", "tests/**",
        "outputs/full/figures/pdf/**/*", "outputs/full/figures/png/**/*",
        "outputs/full/figures/data/**/*", "outputs/full/figures/metadata/**/*",
        "outputs/full/tables/**/*", "outputs/full/summaries/**/*",
        "outputs/full/checks/**/*", "outputs/full/metadata/**/*",
        "outputs/full/run_manifest.json", "outputs/full/manifest.csv",
    ]
    files: set[Path] = set()
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if path.is_file():
                rel = path.relative_to(ROOT)
                if not _excluded(rel):
                    files.add(rel)
    return sorted(files, key=lambda path: path.as_posix())


def collect_code_package_files(include_release_manifests: bool = True) -> list[Path]:
    """Collect code-upload members without recursively hashing manifest files."""
    files = set(_base_package_files())
    if include_release_manifests:
        for rel in RELEASE_MANIFEST_FILES:
            if (ROOT / rel).exists():
                files.add(rel)
    return sorted(files, key=lambda path: path.as_posix())


def write_release_manifest(manifested_files: Iterable[Path]) -> None:
    """Write an integrity manifest that intentionally excludes its own files."""
    rows = []
    forbidden_self = {path.as_posix() for path in RELEASE_MANIFEST_FILES}
    for rel in sorted(set(manifested_files), key=lambda path: path.as_posix()):
        if rel.as_posix() in forbidden_self:
            raise ValueError("release manifest must not include itself")
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(path)
        role = _artifact_role(rel)
        rel_text = rel.as_posix()
        paper_table_names = {
            "outputs/full/tables/tbl_app_exp3_proxy_static_control.csv",
            "outputs/full/tables/tbl_app_exp3_source_label_sensitivity.csv",
            "outputs/full/tables/tbl_app_exp3_proxy_score_quality.csv",
        }
        rows.append({
            "file_path": rel_text,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "artifact_role": role,
            "paper_facing": role == "paper_figure_bundle" or rel_text in paper_table_names or rel_text == "outputs/full/summaries/paired_effect_vs_history_mean_static.csv",
            "required_for_reproduction": role in {"source_code", "tests", "documentation", "full_manifest", "release_support"},
            "included_in_code_upload": True,
        })
    save_dataframe(pd.DataFrame(rows), ROOT / "release_manifest.csv")
    write_json(ROOT / "release_manifest.json", {"artifacts": rows, "self_reference_excluded": True})


def _write_zip(zip_path: Path, files: Iterable[Path]) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(set(files), key=lambda path: path.as_posix()):
            archive.write(ROOT / rel, arcname=rel.as_posix())
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(
        f"{sha256_file(zip_path)}  {zip_path.name}\n",
        encoding="utf-8",
    )


def _write_inventory(package_files: list[Path]) -> tuple[Path, Path]:
    inventory = ROOT / "full_result_inventory.csv"
    checksum = ROOT / "artifact_sha256sums.txt"
    rows = []
    for rel in sorted(set(package_files), key=lambda path: path.as_posix()):
        path = ROOT / rel
        rows.append({"file_path": rel.as_posix(), "file_size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    save_dataframe(pd.DataFrame(rows), inventory)
    checksum_files = [*package_files, Path("full_result_inventory.csv")]
    lines = []
    for rel in sorted(set(checksum_files), key=lambda path: path.as_posix()):
        lines.append(f"{sha256_file(ROOT / rel)}  {rel.as_posix()}\n")
    checksum.write_text("".join(lines), encoding="utf-8")
    return inventory.relative_to(ROOT), checksum.relative_to(ROOT)


def _build_archives_once() -> None:
    base_files = _base_package_files()
    write_release_manifest(base_files)
    code_files = collect_code_package_files(include_release_manifests=True)
    _write_zip(CODE_ZIP, code_files)
    repro_files = [*code_files, *REPRO_EXTRAS]
    inventory, checksum = _write_inventory(repro_files)
    _write_zip(REPRO_ZIP, [*repro_files, inventory, checksum])


def build_release_packages() -> None:
    """Build final archives twice so final verification reports are included."""
    normalize_final_interfaces()
    _write_template_files()
    write_final_docs()
    write_release_reports(["release package verification pending"])
    _build_archives_once()
    ok, errors = verify_release_packages()
    write_release_reports([] if ok else errors)
    _build_archives_once()
    final_ok, final_errors = verify_release_packages()
    write_release_reports([] if final_ok else final_errors)
    if not final_ok:
        raise RuntimeError("Release package verification failed: " + " | ".join(final_errors))


def _verify_sha_sidecar(zip_path: Path) -> list[str]:
    errors: list[str] = []
    sidecar = zip_path.with_suffix(zip_path.suffix + ".sha256")
    if not sidecar.exists():
        return [f"missing checksum sidecar: {sidecar.name}"]
    tokens = sidecar.read_text(encoding="utf-8").strip().split()
    if len(tokens) != 2 or tokens[1] != zip_path.name:
        return [f"malformed checksum sidecar: {sidecar.name}"]
    if tokens[0] != sha256_file(zip_path):
        errors.append(f"checksum sidecar does not match archive: {zip_path.name}")
    return errors


def _verify_release_manifest() -> list[str]:
    errors: list[str] = []
    csv_path = ROOT / "release_manifest.csv"
    json_path = ROOT / "release_manifest.json"
    if not csv_path.exists() or not json_path.exists():
        return ["release manifest files missing"]
    rows = read_csv_rows(csv_path)
    forbidden_self = {path.as_posix() for path in RELEASE_MANIFEST_FILES}
    for row in rows:
        rel = Path(row["file_path"])
        if rel.as_posix() in forbidden_self:
            errors.append("release manifest incorrectly includes itself")
            continue
        path = ROOT / rel
        if not path.exists():
            errors.append(f"release manifest lists missing file: {rel.as_posix()}")
        elif sha256_file(path) != row["sha256"]:
            errors.append(f"release manifest hash mismatch: {rel.as_posix()}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if payload.get("self_reference_excluded") is not True:
        errors.append("release manifest JSON lacks self-reference exclusion flag")
    return errors


def _verify_artifact_checksum_index() -> list[str]:
    errors: list[str] = []
    path = ROOT / "artifact_sha256sums.txt"
    if not path.exists():
        return ["artifact_sha256sums.txt missing"]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        tokens = line.split(maxsplit=1)
        if len(tokens) != 2:
            errors.append(f"malformed checksum index row: {line}")
            continue
        digest, rel_text = tokens
        if rel_text == "artifact_sha256sums.txt":
            errors.append("artifact_sha256sums.txt must not include itself")
            continue
        artifact = ROOT / rel_text
        if not artifact.exists():
            errors.append(f"checksum index lists missing file: {rel_text}")
        elif sha256_file(artifact) != digest:
            errors.append(f"checksum index hash mismatch: {rel_text}")
    return errors


def _required_figure_members() -> set[str]:
    members: set[str] = set()
    for figure_id in ACTIVE_FIGURES:
        members.update({
            f"outputs/full/figures/pdf/{figure_id}.pdf",
            f"outputs/full/figures/png/{figure_id}.png",
            f"outputs/full/figures/data/{figure_id}_data.csv",
            f"outputs/full/figures/metadata/{figure_id}_metadata.json",
        })
    return members


def verify_release_packages() -> tuple[bool, list[str]]:
    """Verify promoted full artifacts, checksum indices, and both archives."""
    errors: list[str] = []
    try:
        manifest = _read_manifest()
    except FileNotFoundError as exc:
        return False, [f"missing full manifest: {exc}"]
    if manifest.get("paper_result") is not True:
        errors.append("full manifest is not paper_result=true")
    if manifest.get("status") != "complete":
        errors.append("full manifest status is not complete")
    errors.extend(_verify_release_manifest())
    errors.extend(_verify_artifact_checksum_index())

    expected_code = {path.as_posix() for path in collect_code_package_files(include_release_manifests=True)}
    required_members = (
        _required_figure_members()
        | {path.as_posix() for path in REQUIRED_RELEASE_DOCS}
        | {path.as_posix() for path in REQUIRED_NOTEBOOK_AUDIT_FILES}
    )
    audit_path = FULL / "checks" / "figure_release_audit.csv"
    if not audit_path.exists():
        errors.append("figure release audit CSV is missing")
    else:
        audit = pd.read_csv(audit_path)
        if audit.empty or not (audit.get("status", pd.Series(dtype=str)).astype(str) == "passed").all():
            errors.append("figure release audit CSV does not report passed")
    for zip_path, expected in [
        (CODE_ZIP, expected_code),
        (REPRO_ZIP, expected_code | {path.as_posix() for path in REPRO_EXTRAS} | {"full_result_inventory.csv", "artifact_sha256sums.txt"}),
    ]:
        if not zip_path.exists():
            errors.append(f"missing zip: {zip_path.name}")
            continue
        errors.extend(_verify_sha_sidecar(zip_path))
        with zipfile.ZipFile(zip_path) as archive:
            bad_member = archive.testzip()
            names = set(archive.namelist())
        if bad_member:
            errors.append(f"zip test failed for {zip_path.name}: {bad_member}")
        missing = expected - names
        if missing:
            errors.append(f"archive missing required members in {zip_path.name}: {sorted(missing)[:5]}")
        missing_paper = required_members - names
        if missing_paper:
            errors.append(f"archive missing paper-facing members in {zip_path.name}: {sorted(missing_paper)[:5]}")
        for name in names:
            if name.startswith(("inputs/KuaiRand-1K/data/", "outputs/full/raw/")) or "legacy/retired_figures" in name:
                errors.append(f"excluded artifact included in {zip_path.name}: {name}")
    return (not errors), errors


def write_release_reports(errors: list[str]) -> None:
    """Write stable human-readable release reports; no experiment is rerun."""
    manifest = _read_manifest()
    status = "passed" if not errors else "failed"
    checklist = (
        "# Final release checklist\n\n"
        f"- Full result validation status: {status}\n"
        f"- Promotion status: paper_result={manifest.get('paper_result')}, status={manifest.get('status')}\n"
        f"- Active figures: {', '.join(ACTIVE_FIGURES)}\n"
        "- Figure release audit: `outputs/full/checks/figure_release_audit.csv`, `outputs/full/checks/figure_release_audit.md`, `outputs/full/checks/exp3_figure_release_audit_executed.ipynb`\n"
        f"- Retired figures: {', '.join(RETIRED_FIGURES)}\n"
        "- Paper-facing tables: `tbl_app_exp3_proxy_static_control.csv`, `tbl_app_exp3_source_label_sensitivity.csv`, `tbl_app_exp3_proxy_score_quality.csv`\n"
        f"- Upload archive contents: `{CODE_ZIP.name}`, `{REPRO_ZIP.name}`\n"
        "- Excluded raw inputs: `inputs/KuaiRand-1K/data/`, user-level raw logs, full raw event-level outputs, retired figure bundles\n"
        f"- Checks passed: {'yes' if not errors else 'no'}\n"
        f"- Checks failed: {'none' if not errors else '; '.join(errors)}\n"
        "- Remaining manual user steps: obtain KuaiRand-1K separately and fill input hash templates before external reproduction.\n"
    )
    (ROOT / "docs" / "final_release_checklist.md").write_text(checklist, encoding="utf-8")
    report = (
        "# Final release completion report\n\n"
        "The release packaging step validates promoted full outputs, generates release manifests, builds upload archives, and checks archive integrity. No full experiment rerun is performed.\n\n"
        f"- Code upload package: `{CODE_ZIP.name}`\n"
        f"- Reproducibility manifest package: `{REPRO_ZIP.name}`\n"
        "- SHA-256 sidecars are required for both archives.\n"
        f"- Final verification status: {status}\n"
    )
    (ROOT / "docs" / "final_release_completion_report.md").write_text(report, encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
