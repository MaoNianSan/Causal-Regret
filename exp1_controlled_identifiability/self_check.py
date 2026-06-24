from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import CI_LEVEL, FAST_SEEDS, N_BOOTSTRAP, SEEDS
from src.experiment_contract import INPUT_DATA_STATUS, PRIMARY_METRIC
from src.plot_utils import FIGURE_DATA_COLUMNS
from src.runner import (
    METHODS,
    PRIMARY_MATCHED_SETTINGS,
    PROJECT_ROOT,
    REGIMES,
    SETTINGS,
)

REQUIRED_FIGURES = [
    "fig_exp1_validity_boundary",
    "fig_exp1_same_mean_delay",
    "fig_exp1_attribution_diagnostics",
    "fig_exp1_proxy_quality",
    "fig_app_exp1_selected_trajectories",
    "fig_app_exp1_mismatch_diagnostics",
]


def _safe_text(value: object) -> str:
    return str(value).encode("utf-8", "backslashreplace").decode("utf-8")


def _record(rows: list[dict[str, str]], name: str, ok: bool, detail: str = "") -> bool:
    rows.append(
        {
            "check_name": _safe_text(name),
            "status": "PASSED" if ok else "FAILED",
            "details": _safe_text(detail),
        }
    )
    return bool(ok)


def _nonempty_csv(path: Path) -> bool:
    try:
        return path.exists() and len(pd.read_csv(path)) > 0
    except Exception:
        return False


def check_project(mode: str, output_tag: str | None = None) -> bool:
    root = PROJECT_ROOT / "outputs" / (output_tag or mode)
    (root / "checks").mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    manifest_path = root / "metadata" / "run_manifest.json"
    manifest: dict[str, object] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _record(rows, "run manifest readable", False, repr(exc))
    else:
        _record(rows, "run manifest exists", False, str(manifest_path))

    if manifest:
        _record(
            rows,
            "backend completed",
            manifest.get("backend_status") == "completed",
            str(manifest.get("backend_status")),
        )
        _record(
            rows,
            "run mode matches requested check",
            str(manifest.get("mode")) == str(mode),
            str(manifest.get("mode")),
        )
        _record(
            rows,
            "contextual estimand declared",
            "X_t" in str(manifest.get("information_structure", ""))
            and "conditional" in str(manifest.get("information_structure", "")),
            str(manifest.get("information_structure")),
        )
        _record(
            rows,
            "primary shared-path contract declared",
            "pre-generated" in str(manifest.get("primary_delay_contract", "")),
            str(manifest.get("primary_delay_contract")),
        )
        _record(
            rows,
            "structural EM contract declared",
            "integrates" in str(manifest.get("structural_em_contract", ""))
            and "stationary" in str(manifest.get("structural_em_contract", "")),
            str(manifest.get("structural_em_contract")),
        )
        _record(
            rows,
            "proxy feature-consistency contract declared",
            "saved source-time Kalman"
            in str(manifest.get("proxy_feature_contract", "")),
            str(manifest.get("proxy_feature_contract")),
        )
        _record(
            rows,
            "bootstrap contract",
            int(manifest.get("n_bootstrap", -1)) == N_BOOTSTRAP
            and float(manifest.get("ci_level", -1.0)) == CI_LEVEL,
            f"n_bootstrap={manifest.get('n_bootstrap')}; ci_level={manifest.get('ci_level')}",
        )
        _record(
            rows,
            "input status declared",
            manifest.get("input_data_status") == INPUT_DATA_STATUS,
            str(manifest.get("input_data_status")),
        )
        detailed = bool(manifest.get("detailed_trace_logs", False))
        trace_files = [
            root / "raw" / name
            for name in ("delay_schedule.csv", "arrival_log.csv", "step_log.csv")
        ]
        if detailed:
            _record(
                rows,
                "detailed trace files are populated",
                all(_nonempty_csv(path) for path in trace_files),
                "; ".join(str(path) for path in trace_files),
            )
        else:
            _record(
                rows,
                "summary-only run has no placeholder trace files",
                not any(path.exists() for path in trace_files),
                "; ".join(str(path) for path in trace_files if path.exists()),
            )
        if mode == "fast":
            _record(
                rows,
                "fast result is not paper-marked",
                not bool(manifest.get("paper_result")),
                f"paper_result={manifest.get('paper_result')}",
            )

    expected_seeds = (
        1
        if bool(manifest.get("is_smoke"))
        else len(FAST_SEEDS if mode == "fast" else SEEDS)
    )
    expected_runs = expected_seeds * len(SETTINGS) * len(REGIMES) * len(METHODS)
    seed_path = root / "raw" / "seed_level_results.csv"
    seed = pd.DataFrame()
    if seed_path.exists():
        try:
            seed = pd.read_csv(seed_path)
            required = {
                "seed",
                "delay_setting",
                "setting_id",
                "regime",
                "method",
                "method_id",
                "method_display_name",
                "information_interface",
                "reference_role",
                "deployable",
                "final_Rc",
                "mean_delay",
                "context_observed_by_all",
                "regret_comparator",
                "delay_path_id",
                "state_path_id",
                "effective_feedback_units",
                "n_observed_arrivals",
                "em_delay_likelihood",
                "labelled_feature_alignment_max",
                "run_mode",
                "paper_result",
                "input_data_status",
                "loss_map_mismatch_rate",
                "delta_attr_event_per_arrival",
                "abs_delta_attr_event_per_arrival",
            }
            _record(
                rows,
                "seed summary schema",
                required.issubset(seed.columns),
                f"missing={sorted(required-set(seed.columns))}",
            )
            _record(
                rows,
                "expected run count",
                len(seed) == expected_runs,
                f"expected={expected_runs}; observed={len(seed)}",
            )
            keys = ["seed", "delay_setting", "regime", "method"]
            duplicate_count = int(seed.duplicated(keys).sum())
            _record(
                rows,
                "unique design keys",
                duplicate_count == 0,
                f"duplicates={duplicate_count}",
            )
            _record(
                rows,
                "all learners receive context",
                bool(seed["context_observed_by_all"].astype(bool).all()),
                "context_observed_by_all",
            )
            _record(
                rows,
                "regret comparator is context-information oracle",
                set(seed["regret_comparator"].astype(str))
                == {"context_information_oracle"},
                str(seed["regret_comparator"].drop_duplicates().tolist()),
            )
            _record(
                rows,
                "causal regret finite",
                bool(
                    np.isfinite(pd.to_numeric(seed["final_Rc"], errors="coerce")).all()
                ),
                "final_Rc",
            )
            _record(
                rows,
                "canonical run metadata",
                set(seed["run_mode"].astype(str)) == {mode}
                and set(seed["input_data_status"].astype(str)) == {INPUT_DATA_STATUS},
                f"run_mode={seed['run_mode'].drop_duplicates().tolist()}",
            )
            _record(
                rows,
                "primary metric is declared",
                set(seed["metric_id"].astype(str)) == {PRIMARY_METRIC},
                str(seed["metric_id"].drop_duplicates().tolist()),
            )

            primary = seed[seed["delay_setting"].isin(PRIMARY_MATCHED_SETTINGS)]
            path_count = (
                primary.groupby(["seed", "delay_setting"])["delay_path_id"]
                .nunique()
                .max()
                if not primary.empty
                else np.inf
            )
            _record(
                rows,
                "primary paths shared across methods",
                int(path_count) == 1,
                f"max distinct path IDs={path_count}",
            )
            mean_spread = (
                primary.groupby(["seed", "delay_setting"])["mean_delay"]
                .agg(lambda values: float(np.nanmax(values) - np.nanmin(values)))
                .max()
                if not primary.empty
                else np.inf
            )
            _record(
                rows,
                "primary realised delay unchanged by learner",
                float(mean_spread) < 1e-10,
                f"max method spread={mean_spread}",
            )
            target_gap = (
                primary.groupby(["seed", "delay_setting"])["trace_observed_mean_delay"]
                .first()
                .sub(15.0)
                .abs()
                .max()
                if not primary.empty
                else np.inf
            )
            tolerance = 3.0 if bool(manifest.get("is_smoke")) else 0.75
            _record(
                rows,
                "primary paths calibrated to observed-delay target",
                float(target_gap) <= tolerance,
                f"max |mean-15|={target_gap}; tolerance={tolerance}",
            )

            action_stress = seed[seed["delay_setting"].eq("action_structural_stress")]
            _record(
                rows,
                "action-dependent delay isolated as stress test",
                (
                    bool(action_stress["policy_dependent_delay"].astype(bool).all())
                    if not action_stress.empty
                    else False
                ),
                "policy_dependent_delay",
            )

            equality_methods = {
                "naive",
                "naive_ewma",
                "delayed_ucb",
                "delayed_exp3",
                "sliding_window_W250",
                "anonymous_delayed",
                "causal_em",
                "causal_em_misspecified",
                "proxy",
            }
            fair = seed[seed["method"].isin(equality_methods)].copy()
            delta = (
                pd.to_numeric(fair["effective_feedback_units"], errors="coerce")
                - pd.to_numeric(fair["n_observed_arrivals"], errors="coerce")
            ).abs()
            _record(
                rows,
                "per-arrival feedback-unit accounting",
                bool((delta <= 1e-8).all()),
                f"max |units-arrivals|={float(delta.max()) if len(delta) else np.nan}",
            )

            structural = {
                "state_structural_matched_15",
                "proxy_good_matched_15",
                "proxy_bad_matched_15",
                "action_structural_stress",
            }
            em = seed[
                seed["delay_setting"].isin(structural) & seed["method"].eq("causal_em")
            ]
            _record(
                rows,
                "structural EM uses observable-state integrated likelihood",
                set(em["em_delay_likelihood"].astype(str))
                == {"gaussian_observable_state_integrated_quadrature"},
                str(em["em_delay_likelihood"].drop_duplicates().tolist()),
            )
            ablation = seed[
                seed["delay_setting"].isin(structural)
                & seed["method"].eq("causal_em_misspecified")
            ]
            _record(
                rows,
                "EM ablation is explicitly stationary",
                set(ablation["em_delay_likelihood"].astype(str))
                == {"stationary_geometric_ablation"},
                str(ablation["em_delay_likelihood"].drop_duplicates().tolist()),
            )
            aligned = seed[
                seed["method"].isin(["causal_em", "causal_em_misspecified", "proxy"])
            ]
            alignment = pd.to_numeric(
                aligned["labelled_feature_alignment_max"], errors="coerce"
            )
            _record(
                rows,
                "EM/proxy labelled updates share decision feature space",
                bool((alignment.fillna(np.inf) <= 1e-12).all()),
                f"max discrepancy={float(alignment.max()) if len(alignment) else np.nan}",
            )

            proxy = seed[seed["method"].eq("proxy")]
            _record(
                rows,
                "proxy error is time-averaged and finite",
                bool(
                    pd.to_numeric(proxy["proxy_state_error_mean"], errors="coerce")
                    .notna()
                    .all()
                ),
                f"nonfinite={int(pd.to_numeric(proxy['proxy_state_error_mean'], errors='coerce').isna().sum())}",
            )
            quality = proxy[
                (proxy["regime"].eq("unlabelled"))
                & proxy["delay_setting"].isin(
                    ["proxy_good_matched_15", "proxy_bad_matched_15"]
                )
            ]
            quality_means = (
                quality.groupby("delay_setting")["proxy_state_error_mean"].mean()
                if not quality.empty
                else pd.Series(dtype=float)
            )
            quality_ok = {"proxy_good_matched_15", "proxy_bad_matched_15"}.issubset(
                set(quality_means.index)
            ) and float(quality_means["proxy_bad_matched_15"]) > float(
                quality_means["proxy_good_matched_15"]
            )
            _record(
                rows,
                "proxy quality sweep changes time-averaged state error",
                quality_ok,
                str(quality_means.to_dict()),
            )
        except Exception as exc:
            _record(rows, "seed summary readable", False, repr(exc))
    else:
        _record(rows, "seed summary exists", False, str(seed_path))

    design_path = root / "metadata" / "design_manifest.csv"
    if design_path.exists():
        design = pd.read_csv(design_path)
        _record(
            rows,
            "design manifest expected count",
            len(design) == expected_runs,
            f"expected={expected_runs}; observed={len(design)}",
        )
        _record(
            rows,
            "design manifest contains no failed row",
            set(design.get("status", pd.Series(dtype=str)).astype(str))
            == {"completed"},
            str(design.get("status", pd.Series(dtype=str)).value_counts().to_dict()),
        )
    else:
        _record(rows, "design manifest exists", False, str(design_path))

    summary_path = root / "summaries" / "method_summary.csv"
    if summary_path.exists():
        summary = pd.read_csv(summary_path)
        required_summary = {
            "mean_causal_regret_per_round",
            "ci_lower",
            "ci_upper",
            "ci_level",
            "n_bootstrap",
            "ci_method",
        }
        _record(
            rows,
            "method summary bootstrap schema",
            required_summary.issubset(summary.columns),
            f"missing={sorted(required_summary-set(summary.columns))}",
        )
        _record(
            rows,
            "method summary uses 2000 percentile bootstrap",
            bool(
                (
                    pd.to_numeric(summary["n_bootstrap"], errors="coerce")
                    == N_BOOTSTRAP
                ).all()
            )
            and set(summary["ci_method"].astype(str)) == {"percentile_bootstrap"},
            f"n_bootstrap={summary['n_bootstrap'].drop_duplicates().tolist()}",
        )
    else:
        _record(rows, "method summary exists", False, str(summary_path))

    trajectory = root / "processed" / "selected_trajectory_points.csv"
    _record(
        rows,
        "selected trajectory output exists",
        _nonempty_csv(trajectory),
        str(trajectory),
    )

    figure_ok = True
    missing: list[str] = []
    schema_failures: list[str] = []
    for name in REQUIRED_FIGURES:
        for suffix in (
            f"figures/data/{name}_data.csv",
            f"figures/png/{name}.png",
            f"figures/pdf/{name}.pdf",
            f"figures/metadata/{name}_metadata.json",
        ):
            path = root / suffix
            if not (path.exists() and path.stat().st_size > 0):
                figure_ok = False
                missing.append(suffix)
        data_path = root / "figures" / "data" / f"{name}_data.csv"
        if data_path.exists():
            try:
                columns = set(pd.read_csv(data_path).columns)
                if not set(FIGURE_DATA_COLUMNS).issubset(columns):
                    schema_failures.append(name)
            except Exception:
                schema_failures.append(name)
    _record(rows, "registered figure bundles exist", figure_ok, "; ".join(missing))
    _record(
        rows,
        "figure data follow common schema",
        not schema_failures,
        "; ".join(schema_failures),
    )

    ok = all(row["status"] == "PASSED" for row in rows)
    report = pd.DataFrame(rows)
    report.to_csv(root / "checks" / "self_check_report.csv", index=False)
    with (root / "checks" / "self_check_report.md").open(
        "w", encoding="utf-8"
    ) as handle:
        handle.write("# EXP1 self-check\n\n")
        for row in rows:
            handle.write(f"- [{row['status']}] {row['check_name']}: {row['details']}\n")
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
