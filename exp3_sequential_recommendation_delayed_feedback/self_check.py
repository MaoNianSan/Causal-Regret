"""Output-level checks and explicit paper-result promotion gate for Exp3."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from config import DEFAULT_CONFIG
from plot_results import plot_all
from utils import save_dataframe, write_artifact_manifest, write_json

ROOT = Path(__file__).resolve().parent
REQUIRED_FIGURES = ["fig_exp3_long_term_recoverability", "fig_app_exp3_horizon_eligibility"]
REQUIRED_METHODS = {
    "source_aware_reference",
    "arrival_time_naive",
    "partial_source_label_q10",
    "partial_source_label_q30",
    "partial_source_label_q50",
    "history_mean_static",
    "history_ewma_ridge_proxy",
    "short_term_ridge_proxy",
    "short_term_composite_surrogate",
}


def _as_bool(value: object) -> bool:
    """Parse CSV/JSON boolean values without treating the string 'False' as true."""
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _figure_status_errors(output_dir: Path, figure_id: str, expected_paper_result: bool) -> list[str]:
    errors: list[str] = []
    paths = {
        "pdf": output_dir / "figures" / "pdf" / f"{figure_id}.pdf",
        "png": output_dir / "figures" / "png" / f"{figure_id}.png",
        "data": output_dir / "figures" / "data" / f"{figure_id}_data.csv",
        "metadata": output_dir / "figures" / "metadata" / f"{figure_id}_metadata.json",
    }
    for name, path in paths.items():
        if not path.exists():
            errors.append(f"missing figure bundle member: {name}={path.relative_to(output_dir)}")
    if errors:
        return errors

    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    if bool(metadata.get("paper_result")) != expected_paper_result:
        errors.append(f"{figure_id} metadata paper_result does not match run manifest")
    data = pd.read_csv(paths["data"])
    if "paper_result" not in data.columns:
        errors.append(f"{figure_id} data lacks paper_result column")
    elif not data.empty and bool(data["paper_result"].map(_as_bool).all()) != expected_paper_result:
        errors.append(f"{figure_id} data paper_result does not match run manifest")
    return errors


def _validate_output(mode: str, promote: bool) -> tuple[dict, list[str]]:
    output_dir = ROOT / "outputs" / mode
    errors: list[str] = []
    manifest_path = output_dir / "metadata" / "run_manifest.json"
    if not manifest_path.exists():
        return {}, ["run manifest missing"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_status = "complete_pending_external_checks" if not manifest.get("paper_result") else "complete"
    if manifest.get("status") != expected_status:
        errors.append(f"run status is {manifest.get('status')!r}, expected {expected_status!r}")
    if mode == "fast" and manifest.get("paper_result"):
        errors.append("fast output must never be paper_result=true")
    for key, expected in {
        "target_context": "same_split_standard_log_only",
        "action_vocabulary_source": "history_standard_only",
        "carrier_rule": "most_recent_same_user_standard_exposure_at_or_before_arrival",
        "main_feature_information": "completed_history_plus_earlier_main_bins_only",
    }.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest {key!r} is not {expected!r}")
    if promote:
        if mode != "full":
            errors.append("only full outputs can be promoted")
        if manifest.get("input_data_status") != "real_kuairand_1k":
            errors.append("promotion requires real KuaiRand-1K input status")

    raw_path = output_dir / "raw" / "sequential_decision_raw.csv"
    if not raw_path.exists():
        errors.append("sequential_decision_raw.csv missing")
    else:
        raw = pd.read_csv(raw_path)
        missing_methods = REQUIRED_METHODS - set(raw["method_id"].dropna().unique())
        if missing_methods:
            errors.append(f"required methods missing: {sorted(missing_methods)}")
        reference = raw[raw["method_id"] == "source_aware_reference"]
        if reference.empty or bool(reference["deployable"].map(_as_bool).any()):
            errors.append("source_aware_reference must be non-deployable")
        if bool(raw["deployable"].map(_as_bool).any()):
            errors.append("Exp3 routes must not be marked deployable under support-restricted offline evaluation")

    for required_summary in [
        output_dir / "summaries" / "paired_mechanism_contrast.csv",
        output_dir / "summaries" / "paired_effect_vs_history_mean_static.csv",
        output_dir / "summaries" / "oracle_action_dynamics_summary.csv",
        output_dir / "tables" / "tbl_app_exp3_source_label_sensitivity.csv",
        output_dir / "tables" / "tbl_app_exp3_proxy_static_control.csv",
    ]:
        if not required_summary.exists() or required_summary.stat().st_size == 0:
            errors.append(f"required v5.2 audit output missing: {required_summary.name}")
    static_effect_path = output_dir / "summaries" / "paired_effect_vs_history_mean_static.csv"
    if static_effect_path.exists():
        static_effect = pd.read_csv(static_effect_path)
        needed = {"method_id", "comparator_method_id", "point_estimate", "ci_lower", "ci_upper"}
        if static_effect.empty or not needed.issubset(static_effect.columns):
            errors.append("paired static-control effect summary is malformed")
        elif not ((static_effect["method_id"] == "short_term_ridge_proxy") & (static_effect["comparator_method_id"] == "history_mean_static")).any():
            errors.append("ST ridge versus history-mean paired effect is missing")

    for retired_id in [
        "fig_app_exp3_arrival_mechanism_contrast",
        "fig_app_exp3_source_label_coverage",
        "fig_app_exp3_horizon_saturation",
    ]:
        active_members = [
            output_dir / "figures" / "pdf" / f"{retired_id}.pdf",
            output_dir / "figures" / "png" / f"{retired_id}.png",
            output_dir / "figures" / "data" / f"{retired_id}_data.csv",
            output_dir / "figures" / "metadata" / f"{retired_id}_metadata.json",
        ]
        if any(member.exists() for member in active_members):
            errors.append(f"retired figure remains active: {retired_id}")

    dynamics_path = output_dir / "summaries" / "oracle_action_dynamics_summary.csv"
    if dynamics_path.exists():
        dynamics = pd.read_csv(dynamics_path)
        required_cols = {"oracle_top_action_unique_count", "oracle_top_action_switch_rate", "oracle_top_action_share"}
        if dynamics.empty or not required_cols.issubset(dynamics.columns):
            errors.append("oracle action dynamics audit is malformed")

    vocabulary_path = output_dir / "processed" / "action_vocabulary.csv"
    if vocabulary_path.exists():
        vocabulary = pd.read_csv(vocabulary_path)
        if "candidate_action" not in vocabulary.columns or int(vocabulary["candidate_action"].sum()) < 10:
            errors.append("history-defined candidate action vocabulary is missing or too small")
    else:
        errors.append("action_vocabulary.csv missing")

    # Before promotion, all generated bundles must remain non-paper. After a
    # successful promotion, the bundles are regenerated and rechecked.
    expected_paper_result = bool(manifest.get("paper_result"))
    for figure_id in REQUIRED_FIGURES:
        errors.extend(_figure_status_errors(output_dir, figure_id, expected_paper_result))
    return manifest, errors


def _write_compatibility_manifests(output_dir: Path, manifest: dict) -> None:
    """Write stable top-level aliases expected by release tooling."""
    write_json(output_dir / "run_manifest.json", manifest)
    rows = [{
        "key": key,
        "value": json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value,
    } for key, value in manifest.items()]
    save_dataframe(pd.DataFrame(rows), output_dir / "manifest.csv")


def _write_self_check_report(output_dir: Path, mode: str, errors: list[str], manifest: dict | None = None) -> None:
    """Write a report that remains consistent after a later promotion step."""
    checks_dir = output_dir / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    paper_result = bool((manifest or {}).get("paper_result", False))
    promotion_status = "already_promoted" if paper_result else "not_promoted"
    save_dataframe(pd.DataFrame([{
        "check_id": "self_check",
        "mode": mode,
        "status": "failed" if errors else "passed",
        "n_errors": len(errors),
        "paper_result": paper_result,
        "promotion_status": promotion_status,
        "details": " | ".join(errors) if errors else "SELF-CHECK PASSED",
    }]), checks_dir / "self_check_report.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("fast", "full"))
    parser.add_argument("--promote-paper-result", action="store_true")
    args = parser.parse_args()
    output_dir = ROOT / "outputs" / args.mode

    manifest, errors = _validate_output(args.mode, args.promote_paper_result)
    _write_self_check_report(output_dir, args.mode, errors, manifest)
    if manifest:
        _write_compatibility_manifests(output_dir, manifest)

    if errors:
        print("SELF-CHECK FAILED")
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    if args.promote_paper_result:
        manifest["paper_result"] = True
        manifest["status"] = "complete"
        manifest["paper_result_promoted_by"] = "self_check.py"
        write_json(output_dir / "metadata" / "run_manifest.json", manifest)
        _write_compatibility_manifests(output_dir, manifest)
        plot_all(
            output_dir,
            args.mode,
            True,
            DEFAULT_CONFIG,
            input_data_status=str(manifest.get("input_data_status", "unknown")),
        )
        write_artifact_manifest(output_dir)
        _, promotion_errors = _validate_output(args.mode, False)
        promoted_manifest = json.loads((output_dir / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
        _write_self_check_report(output_dir, args.mode, promotion_errors, promoted_manifest)
        _write_compatibility_manifests(output_dir, promoted_manifest)
        if promotion_errors:
            print("SELF-CHECK FAILED AFTER PROMOTION")
            for error in promotion_errors:
                print(f"[FAIL] {error}")
            return 1
        print("SELF-CHECK PASSED; full real-data output promoted and figure bundles regenerated.")
        return 0

    print(f"SELF-CHECK PASSED for mode={args.mode}: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
