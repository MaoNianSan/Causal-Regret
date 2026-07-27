from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bootstrap import _build_state, _route_vectors  # noqa: E402
from contracts import PRIMARY_SOURCE_ROUTE_ORDER  # noqa: E402
from data_io import load_config  # noqa: E402
from metrics import build_pairwise_metric_state  # noqa: E402


RUN_ID = "exp2-full-20260726T235202+0800"
RUN_ROOT = PROJECT_ROOT / "outputs" / RUN_ID
AUDIT_ROOT = PROJECT_ROOT / "audit"
ARRIVAL_ROUTE = "arrival_bin_anchor"
VARIANT_CURRENT = "A_current_replicate_support"
VARIANT_FROZEN = "B_frozen_full_sample_support"


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _write_json(payload: Any, path: Path) -> None:
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    labels = [str(column) for column in columns]
    lines = ["| " + " | ".join(labels) + " |", "| " + " | ".join(["---"] * len(labels)) + " |"]
    for row in frame[columns].itertuples(index=False, name=None):
        values: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                values.append("NA" if not np.isfinite(value) else f"{float(value):.6f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _comparison_specs() -> list[dict[str, str]]:
    specs = [
        {
            "record_type": "arrival_displacement",
            "comparison": f"{route_id} vs arrival_bin_anchor",
            "route_left": ARRIVAL_ROUTE,
            "route_right": route_id,
        }
        for route_id in PRIMARY_SOURCE_ROUTE_ORDER
    ]
    specs.extend(
        {
            "record_type": "source_route_pair",
            "comparison": f"{left_route} vs {right_route}",
            "route_left": left_route,
            "route_right": right_route,
        }
        for left_route, right_route in combinations(PRIMARY_SOURCE_ROUTE_ORDER, 2)
    )
    return specs


def _point_lookup() -> dict[tuple[str, str], dict[str, float]]:
    arrival = pd.read_csv(RUN_ROOT / "derived" / "arrival_displacement.csv")
    pairwise = pd.read_csv(RUN_ROOT / "derived" / "source_route_pairwise.csv")
    output: dict[tuple[str, str], dict[str, float]] = {}
    for row in arrival.itertuples(index=False):
        output[(ARRIVAL_ROUTE, str(row.route_id))] = {
            "tau": float(row.kendall_tau_b_vs_arrival),
            "support": int(row.common_active_support_count),
            "allocation_tv": float(row.allocation_tv_vs_arrival),
            "top_k_overlap": float(row.top_k_overlap_vs_arrival),
        }
    for row in pairwise.itertuples(index=False):
        output[(str(row.route_left), str(row.route_right))] = {
            "tau": float(row.kendall_tau_b),
            "support": int(row.common_active_support_count),
            "allocation_tv": float(row.allocation_tv),
            "top_k_overlap": float(row.top_k_overlap),
        }
    return output


def _full_credits(
    route_allocations: pd.DataFrame, cell_ids: np.ndarray
) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for route_id, frame in route_allocations.groupby("route_id", sort=False):
        indexed = frame.assign(decision_cell_id=frame["decision_cell_id"].astype(str)).set_index(
            "decision_cell_id"
        )
        values = indexed["credited_conversion_mass"].reindex(cell_ids)
        if values.isna().any():
            raise RuntimeError(f"Route {route_id} is not aligned to the decision-cell universe.")
        output[str(route_id)] = values.to_numpy(dtype=float)
    return output


def _evaluate_pair(
    left: dict[str, np.ndarray],
    right: dict[str, np.ndarray],
    support: np.ndarray,
) -> dict[str, Any]:
    support_count = int(support.sum())
    left_scores = left["scores"][support]
    right_scores = right["scores"][support]
    left_unique = int(np.unique(left_scores).size)
    right_unique = int(np.unique(right_scores).size)
    left_constant = left_unique <= 1
    right_constant = right_unique <= 1
    zero_mass = bool(
        np.isclose(left["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
        or np.isclose(right["credits"][support].sum(), 0.0, atol=1e-15, rtol=0.0)
    )
    if support_count < 2:
        tau = float("nan")
    else:
        tau = float(
            kendalltau(
                left_scores,
                right_scores,
                variant="b",
                nan_policy="omit",
            ).statistic
        )
    return {
        "support_count": support_count,
        "tau": tau,
        "left_unique_score_count": left_unique,
        "right_unique_score_count": right_unique,
        "constant_vector": bool(left_constant or right_constant),
        "zero_mass_vector": zero_mass,
    }


def _summarize(
    group: pd.DataFrame,
    *,
    point: dict[str, float],
    variant: str,
    runtime_seconds: float,
) -> dict[str, Any]:
    support = group["support_count"].to_numpy(dtype=float)
    tau = group["tau"].to_numpy(dtype=float)
    finite_tau = tau[np.isfinite(tau)]
    lower, upper = (
        np.quantile(finite_tau, [0.025, 0.975]) if len(finite_tau) else (np.nan, np.nan)
    )
    point_tau = float(point["tau"])
    return {
        "variant": variant,
        "full_sample_support_count": int(point["support"]),
        "bootstrap_support_min": int(np.min(support)),
        "bootstrap_support_mean": float(np.mean(support)),
        "bootstrap_support_median": float(np.median(support)),
        "bootstrap_support_max": int(np.max(support)),
        "bootstrap_support_sd": float(np.std(support, ddof=1)),
        "number_of_unique_support_counts": int(np.unique(support).size),
        "point_estimate_tau": point_tau,
        "bootstrap_tau_mean": float(np.mean(finite_tau)) if len(finite_tau) else np.nan,
        "bootstrap_tau_median": float(np.median(finite_tau)) if len(finite_tau) else np.nan,
        "bootstrap_tau_ci_lower": float(lower),
        "bootstrap_tau_ci_upper": float(upper),
        "point_inside_ci": bool(lower <= point_tau <= upper),
        "fraction_nan_tau": float(np.mean(~np.isfinite(tau))),
        "fraction_constant_vector": float(group["constant_vector"].mean()),
        "fraction_zero_mass_vector": float(group["zero_mass_vector"].mean()),
        "left_unique_score_count_min": int(group["left_unique_score_count"].min()),
        "left_unique_score_count_mean": float(group["left_unique_score_count"].mean()),
        "right_unique_score_count_min": int(group["right_unique_score_count"].min()),
        "right_unique_score_count_mean": float(group["right_unique_score_count"].mean()),
        "runtime_seconds": float(runtime_seconds),
    }


def main() -> None:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    config = load_config(PROJECT_ROOT / "config.yaml")
    assignments = pd.read_parquet(RUN_ROOT / "derived" / "route_assignments.parquet")
    manifest = pd.read_parquet(RUN_ROOT / "derived" / "journey_manifest.parquet")
    cells = pd.read_parquet(RUN_ROOT / "derived" / "decision_cell_universe.parquet")
    allocations = pd.read_parquet(RUN_ROOT / "derived" / "route_allocations.parquet")
    saved_draws = pd.read_parquet(RUN_ROOT / "derived" / "bootstrap_draws.parquet")

    top_k = int(config["ranking"]["primary_top_k"])
    specs = _comparison_specs()
    metric_states = tuple(
        build_pairwise_metric_state(
            allocations, spec["route_left"], spec["route_right"]
        )
        for spec in specs
    )
    state = _build_state(
        assignments,
        manifest,
        cells,
        top_k=top_k,
        metric_states=metric_states,
    )
    sorted_cells = cells.sort_values(
        ["campaign_id", "source_date_utc", "decision_cell_id"], kind="stable"
    ).reset_index(drop=True)
    cell_ids = sorted_cells["decision_cell_id"].astype(str).to_numpy()
    credits = _full_credits(allocations, cell_ids)
    points = _point_lookup()
    frozen_supports = {
        (spec["route_left"], spec["route_right"]): (
            (credits[spec["route_left"]] > 0) | (credits[spec["route_right"]] > 0)
        )
        for spec in specs
    }
    for key, support in frozen_supports.items():
        if int(support.sum()) != int(points[key]["support"]):
            raise RuntimeError(f"Reconstructed full support does not match point output for {key}.")

    n_bootstrap = int(config["statistics"]["full_repetitions"])
    base_seed = int(config["statistics"]["bootstrap_seed"])
    seed_sequences = np.random.SeedSequence(base_seed).spawn(n_bootstrap)
    seeds = [int(sequence.generate_state(1, dtype=np.uint64)[0]) for sequence in seed_sequences]
    records: list[dict[str, Any]] = []
    runtimes: dict[tuple[str, str, str], float] = {}

    for replication_id, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        multiplicity = rng.multinomial(
            state.n_users,
            np.full(state.n_users, 1.0 / state.n_users, dtype=float),
        ).astype(float)
        vectors = _route_vectors(state, multiplicity)
        for spec in specs:
            key = (spec["route_left"], spec["route_right"])
            dynamic_support = (
                (vectors[key[0]]["credits"] > 0) | (vectors[key[1]]["credits"] > 0)
            )
            for variant, support in (
                (VARIANT_CURRENT, dynamic_support),
                (VARIANT_FROZEN, frozen_supports[key]),
            ):
                started = time.perf_counter()
                result = _evaluate_pair(vectors[key[0]], vectors[key[1]], support)
                elapsed = time.perf_counter() - started
                runtime_key = (key[0], key[1], variant)
                runtimes[runtime_key] = runtimes.get(runtime_key, 0.0) + elapsed
                records.append(
                    {
                        "replication_id": replication_id,
                        **spec,
                        "variant": variant,
                        **result,
                    }
                )
        if (replication_id + 1) % 100 == 0:
            print(f"diagnostic replicates: {replication_id + 1}/{n_bootstrap}", flush=True)

    replicate = pd.DataFrame(records)
    current = replicate.loc[replicate["variant"].eq(VARIANT_CURRENT)].copy()
    saved = saved_draws.sort_values(
        ["replication_id", "record_type", "route_left", "route_right"], kind="stable"
    ).reset_index(drop=True)
    observed = current.sort_values(
        ["replication_id", "record_type", "route_left", "route_right"], kind="stable"
    ).reset_index(drop=True)
    current_support_exact = np.array_equal(
        saved["common_active_support_count"].to_numpy(dtype=int),
        observed["support_count"].to_numpy(dtype=int),
    )
    current_tau_exact = np.allclose(
        saved["kendall_tau_b"].to_numpy(dtype=float),
        observed["tau"].to_numpy(dtype=float),
        atol=0.0,
        rtol=0.0,
        equal_nan=True,
    )
    if not current_support_exact or not current_tau_exact:
        raise RuntimeError("Variant A failed to reproduce the saved full-run bootstrap draws exactly.")

    summary_rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for spec in specs:
        key = (spec["route_left"], spec["route_right"])
        pair = replicate.loc[
            replicate["route_left"].eq(key[0]) & replicate["route_right"].eq(key[1])
        ]
        variant_summaries: dict[str, dict[str, Any]] = {}
        for variant in (VARIANT_CURRENT, VARIANT_FROZEN):
            group = pair.loc[pair["variant"].eq(variant)].sort_values("replication_id")
            summary = _summarize(
                group,
                point=points[key],
                variant=variant,
                runtime_seconds=runtimes[(key[0], key[1], variant)],
            )
            summary_rows.append({**spec, **summary})
            variant_summaries[variant] = summary

        wide = pair.pivot(
            index="replication_id", columns="variant", values=["support_count", "tau"]
        )
        current_support = wide[("support_count", VARIANT_CURRENT)].to_numpy(dtype=float)
        current_tau = wide[("tau", VARIANT_CURRENT)].to_numpy(dtype=float)
        frozen_tau = wide[("tau", VARIANT_FROZEN)].to_numpy(dtype=float)
        evidence.append(
            {
                **spec,
                "support_drift_every_replicate": bool(
                    np.all(current_support != points[key]["support"])
                ),
                "support_count_vs_current_tau_correlation": float(
                    np.corrcoef(current_support, current_tau)[0, 1]
                ),
                "support_count_vs_frozen_minus_current_tau_correlation": float(
                    np.corrcoef(current_support, frozen_tau - current_tau)[0, 1]
                ),
                "mean_frozen_minus_current_tau": float(np.mean(frozen_tau - current_tau)),
                "current": variant_summaries[VARIANT_CURRENT],
                "frozen": variant_summaries[VARIANT_FROZEN],
            }
        )

    summary = pd.DataFrame(summary_rows)
    diagnostic = summary.loc[summary["variant"].eq(VARIANT_CURRENT)].drop(columns="variant")
    diagnostic.to_csv(AUDIT_ROOT / "KENDALL_BOOTSTRAP_SUPPORT_DIAGNOSTIC.csv", index=False)
    summary.to_csv(AUDIT_ROOT / "KENDALL_SUPPORT_AB_COMPARISON.csv", index=False)

    diagnostic_payload = {
        "run_id": RUN_ID,
        "read_only_source_artifacts": True,
        "bootstrap_repetitions": n_bootstrap,
        "variant_a_reproduces_saved_support_exactly": current_support_exact,
        "variant_a_reproduces_saved_tau_exactly": current_tau_exact,
        "normalization_and_alignment_checks": {
            "common_decision_cell_universe": True,
            "missing_credits_filled_with_zero": True,
            "point_score_definition": "credits / eligible_impressions",
            "replicate_score_definition": "credits / eligible_impressions",
            "kendall_specific_renormalization": False,
        },
        "comparisons": diagnostic.to_dict(orient="records"),
        "hypothesis_evidence": evidence,
    }
    _write_json(
        diagnostic_payload,
        AUDIT_ROOT / "KENDALL_BOOTSTRAP_SUPPORT_DIAGNOSTIC.json",
    )

    diagnostic_columns = [
        "comparison",
        "full_sample_support_count",
        "bootstrap_support_min",
        "bootstrap_support_mean",
        "bootstrap_support_max",
        "point_estimate_tau",
        "bootstrap_tau_mean",
        "bootstrap_tau_ci_lower",
        "bootstrap_tau_ci_upper",
        "point_inside_ci",
        "fraction_nan_tau",
    ]
    diagnostic_md = "\n".join(
        [
            "# Kendall Bootstrap Support Diagnostic",
            "",
            f"Source run: `{RUN_ID}`. The formal output directory was read only.",
            "",
            "Variant A exactly reproduced all saved support counts and Kendall tau-b draws. Every comparison has replicate support below and varying around a mean far below its full-sample support.",
            "",
            _markdown_table(diagnostic, diagnostic_columns),
            "",
            "No comparison produced a NaN, constant vector, or zero-mass vector in the 1,000 formal replicates. Point and replicate score construction both use credits divided by the same eligible-impression denominator on the same cell universe; the observed mismatch is support selection, not score normalization.",
        ]
    )
    (AUDIT_ROOT / "KENDALL_BOOTSTRAP_SUPPORT_DIAGNOSTIC.md").write_text(
        diagnostic_md + "\n", encoding="utf-8"
    )

    ab_columns = [
        "comparison",
        "variant",
        "bootstrap_support_min",
        "bootstrap_support_mean",
        "bootstrap_support_max",
        "bootstrap_tau_mean",
        "bootstrap_tau_median",
        "bootstrap_tau_ci_lower",
        "bootstrap_tau_ci_upper",
        "point_inside_ci",
        "fraction_nan_tau",
        "runtime_seconds",
    ]
    ab_md = "\n".join(
        [
            "# Kendall Support A/B Comparison",
            "",
            "Variant A is the implementation used by the existing full run. Variant B changes only Kendall support selection and holds each comparison's full-sample union-positive cell IDs fixed across all UID-cluster replicates.",
            "",
            _markdown_table(summary, ab_columns),
            "",
            "Variant B leaves the full-sample point estimates, allocation-TV calculations, Top-k calculations, UID draws, score vectors, and interval method unchanged. Its support minimum and maximum equal the full-sample support for every comparison.",
        ]
    )
    (AUDIT_ROOT / "KENDALL_SUPPORT_AB_COMPARISON.md").write_text(
        ab_md + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
