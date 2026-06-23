from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import FAST_SEEDS, SEEDS
from src.runner import METHODS, PRIMARY_MATCHED_SETTINGS, PROJECT_ROOT, REGIMES, SETTINGS


def _record(rows: list[dict], name: str, ok: bool, detail: str = "") -> bool:
    rows.append({"check_name": name, "status": "PASSED" if ok else "FAILED", "details": detail})
    return bool(ok)


def check_project(mode: str, output_tag: str | None = None) -> bool:
    root = PROJECT_ROOT / "outputs" / (output_tag or mode)
    (root / "checks").mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    manifest_path = root / "metadata" / "run_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _record(rows, "run manifest readable", False, repr(exc))
    else:
        _record(rows, "run manifest exists", False, str(manifest_path))

    if manifest:
        _record(rows, "backend completed", manifest.get("backend_status") == "completed", str(manifest.get("backend_status")))
        _record(rows, "contextual estimand declared", "X_t" in str(manifest.get("information_structure", "")) and "conditional" in str(manifest.get("information_structure", "")), str(manifest.get("information_structure")))
        _record(rows, "primary shared-path contract declared", "pre-generated" in str(manifest.get("primary_delay_contract", "")), str(manifest.get("primary_delay_contract")))
        _record(rows, "structural EM contract declared", "integrates" in str(manifest.get("structural_em_contract", "")) and "stationary" in str(manifest.get("structural_em_contract", "")), str(manifest.get("structural_em_contract")))
        _record(rows, "proxy feature-consistency contract declared", "saved source-time Kalman" in str(manifest.get("proxy_feature_contract", "")), str(manifest.get("proxy_feature_contract")))
        _record(rows, "no output marked as paper result", not bool(manifest.get("paper_result")), f"paper_result={manifest.get('paper_result')}")

    expected_seeds = 1 if bool(manifest.get("is_smoke")) else len(FAST_SEEDS if mode == "fast" else SEEDS)
    expected_runs = expected_seeds * len(SETTINGS) * len(REGIMES) * len(METHODS)
    seed_path = root / "summaries" / "seed_summary.csv"
    design_path = root / "metadata" / "design_manifest.csv"
    seed = pd.DataFrame()
    if seed_path.exists():
        try:
            seed = pd.read_csv(seed_path)
            required = {"seed", "delay_setting", "regime", "method", "final_Rc", "mean_delay", "context_observed_by_all", "regret_comparator", "delay_path_id", "effective_feedback_units", "n_observed_arrivals", "em_delay_likelihood", "labelled_feature_alignment_max"}
            _record(rows, "seed summary schema", required.issubset(seed.columns), f"missing={sorted(required-set(seed.columns))}")
            _record(rows, "expected run count", len(seed) == expected_runs, f"expected={expected_runs}; observed={len(seed)}")
            design_keys = ["seed", "delay_setting", "regime", "method"]
            duplicate_count = int(seed.duplicated(design_keys).sum())
            _record(rows, "unique design keys", duplicate_count == 0, f"duplicates={duplicate_count}")
            _record(rows, "all learners receive context", bool(seed["context_observed_by_all"].astype(bool).all()), "context_observed_by_all")
            _record(rows, "regret comparator is context-information oracle", set(seed["regret_comparator"].astype(str)) == {"context_information_oracle"}, str(seed["regret_comparator"].unique().tolist()))
            _record(rows, "causal regret finite", np.isfinite(pd.to_numeric(seed["final_Rc"], errors="coerce")).all(), "final_Rc")

            primary = seed[seed["delay_setting"].isin(PRIMARY_MATCHED_SETTINGS)]
            common_path = primary.groupby(["seed", "delay_setting"])["delay_path_id"].nunique().max() if not primary.empty else np.inf
            _record(rows, "primary paths shared across methods", int(common_path) == 1, f"max distinct path IDs={common_path}")
            mean_spread = primary.groupby(["seed", "delay_setting"])["mean_delay"].agg(lambda x: float(np.nanmax(x)-np.nanmin(x))).max() if not primary.empty else np.inf
            _record(rows, "primary realised delay unchanged by learner", float(mean_spread) < 1e-10, f"max method spread={mean_spread}")
            target_gap = primary.groupby(["seed", "delay_setting"])["trace_observed_mean_delay"].first().sub(15.0).abs().max() if not primary.empty else np.inf
            tolerance = 3.0 if bool(manifest.get("is_smoke")) else 0.75
            _record(rows, "primary paths calibrated to observed-delay target", float(target_gap) <= tolerance, f"max |mean-15|={target_gap}; tolerance={tolerance}")
            action_stress = seed[seed["delay_setting"].eq("action_structural_stress")]
            _record(rows, "action-dependent delay isolated as stress test", bool(action_stress["policy_dependent_delay"].astype(bool).all()) if not action_stress.empty else False, "policy_dependent_delay")

            equality_methods = {"naive", "naive_ewma", "delayed_ucb", "delayed_exp3", "sliding_window_W250", "anonymous_delayed", "causal_em", "causal_em_misspecified", "proxy"}
            fair = seed[seed["method"].isin(equality_methods)].copy()
            delta = (pd.to_numeric(fair["effective_feedback_units"], errors="coerce") - pd.to_numeric(fair["n_observed_arrivals"], errors="coerce")).abs()
            _record(rows, "per-arrival feedback-unit accounting", bool((delta <= 1e-8).all()), f"max |units-arrivals|={float(delta.max()) if len(delta) else np.nan}")
            labelled = seed[(seed["method"] == "causal_labeled") & (seed["regime"] == "labelled")]
            delta_labelled = (pd.to_numeric(labelled["effective_feedback_units"], errors="coerce") - pd.to_numeric(labelled["n_observed_arrivals"], errors="coerce")).abs()
            _record(rows, "labelled source learner processes each source outcome", bool((delta_labelled <= 1e-8).all()), f"max discrepancy={float(delta_labelled.max()) if len(delta_labelled) else np.nan}")

            soft = seed[seed["method"].isin(["causal_em", "causal_em_misspecified", "proxy"])]
            metrics = pd.to_numeric(soft["soft_attribution_true_mass"], errors="coerce")
            _record(rows, "soft attribution metrics are posterior-derived", bool(((metrics.dropna() >= 0.0) & (metrics.dropna() <= 1.0)).all()) and int(pd.to_numeric(soft["n_soft_assignment_events"], errors="coerce").fillna(0).sum()) > 0, f"finite posterior metrics={int(metrics.notna().sum())}; events={int(pd.to_numeric(soft['n_soft_assignment_events'], errors='coerce').fillna(0).sum())}")
            structural_em = seed[(seed["delay_setting"].isin(["state_structural_matched_15", "proxy_good_matched_15", "proxy_bad_matched_15", "action_structural_stress"])) & (seed["method"].eq("causal_em"))]
            _record(rows, "structural EM uses observable-state integrated delay likelihood", set(structural_em["em_delay_likelihood"].astype(str)) == {"gaussian_observable_state_integrated_quadrature"}, str(structural_em["em_delay_likelihood"].drop_duplicates().tolist()))
            structural_ablation = seed[(seed["delay_setting"].isin(["state_structural_matched_15", "proxy_good_matched_15", "proxy_bad_matched_15", "action_structural_stress"])) & (seed["method"].eq("causal_em_misspecified"))]
            _record(rows, "EM ablation is explicitly stationary", set(structural_ablation["em_delay_likelihood"].astype(str)) == {"stationary_geometric_ablation"}, str(structural_ablation["em_delay_likelihood"].drop_duplicates().tolist()))
            aligned = seed[seed["method"].isin(["causal_em", "causal_em_misspecified", "proxy"])]
            alignment = pd.to_numeric(aligned["labelled_feature_alignment_max"], errors="coerce")
            _record(rows, "EM/proxy labelled updates share their decision feature space", bool((alignment.fillna(np.inf) <= 1e-12).all()), f"max feature discrepancy={float(alignment.max()) if len(alignment) else np.nan}")
            proxy = seed[seed["method"].eq("proxy")]
            _record(rows, "proxy error is time-averaged and finite", bool(pd.to_numeric(proxy["proxy_state_error_mean"], errors="coerce").notna().all()), f"nonfinite={int(pd.to_numeric(proxy['proxy_state_error_mean'], errors='coerce').isna().sum())}")
            quality = proxy[(proxy["regime"].eq("unlabelled")) & proxy["delay_setting"].isin(["proxy_good_matched_15", "proxy_bad_matched_15"])]
            quality_means = quality.groupby("delay_setting")["proxy_state_error_mean"].mean() if not quality.empty else pd.Series(dtype=float)
            quality_ok = {"proxy_good_matched_15", "proxy_bad_matched_15"}.issubset(set(quality_means.index)) and float(quality_means["proxy_bad_matched_15"]) > float(quality_means["proxy_good_matched_15"])
            _record(rows, "proxy quality sweep changes time-averaged state error", quality_ok, str(quality_means.to_dict()))
        except Exception as exc:
            _record(rows, "seed summary readable", False, repr(exc))
    else:
        _record(rows, "seed summary exists", False, str(seed_path))

    if design_path.exists():
        design = pd.read_csv(design_path)
        _record(rows, "design manifest expected count", len(design) == expected_runs, f"expected={expected_runs}; observed={len(design)}")
        _record(rows, "design manifest contains no failed row", set(design.get("status", pd.Series(dtype=str)).astype(str)) == {"completed"}, str(design.get("status", pd.Series(dtype=str)).value_counts().to_dict()))
    else:
        _record(rows, "design manifest exists", False, str(design_path))

    required_figures = [
        "fig_exp1_validity_boundary", "fig_exp1_same_mean_delay", "fig_exp1_attribution_diagnostics", "fig_exp1_proxy_quality",
    ]
    figure_ok = True
    missing = []
    for name in required_figures:
        for suffix in (f"figures/data/{name}_data.csv", f"figures/png/{name}.png", f"figures/pdf/{name}.pdf", f"figures/metadata/{name}_metadata.json"):
            path = root / suffix
            if not (path.exists() and path.stat().st_size > 0):
                figure_ok = False; missing.append(suffix)
    _record(rows, "registered diagnostic figure bundles exist", figure_ok, "; ".join(missing))

    ok = all(x["status"] == "PASSED" for x in rows)
    report = pd.DataFrame(rows)
    report.to_csv(root / "checks" / "self_check_report.csv", index=False)
    with (root / "checks" / "self_check_report.md").open("w", encoding="utf-8") as fh:
        fh.write("# EXP1 self-check\n\n")
        for row in rows:
            fh.write(f"- [{row['status']}] {row['check_name']}: {row['details']}\n")
    print("[SELF-CHECK PASSED]" if ok else "[SELF-CHECK FAILED]")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("fast", "full"))
    parser.add_argument("--output-tag", default=None)
    args = parser.parse_args()
    return 0 if check_project(args.mode, args.output_tag) else 1


if __name__ == "__main__":
    raise SystemExit(main())
