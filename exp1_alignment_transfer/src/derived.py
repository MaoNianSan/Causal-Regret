from __future__ import annotations

"""Seed aggregation, paired bootstrap, figure data, and manuscript artifacts."""

import hashlib
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from config import DISPLAY_NAMES, MECHANISM_ORDER
from src.artifact_io import (
    atomic_write_csv,
    atomic_write_json,
    atomic_write_text,
    sha256_file,
)
from src.contracts import ScientificInvariantError


def _stable_seed(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "little") % (2**32 - 1)


def bootstrap_mean(
    values: Iterable[float],
    repetitions: int,
    ci_level: float,
    key: tuple[object, ...],
) -> dict[str, float | int]:
    values = np.asarray(list(values), dtype=float)
    values = values[np.isfinite(values)]
    n = int(values.size)
    if n == 0:
        return {
            "n_seeds": 0,
            "estimate": np.nan,
            "se": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
        }
    estimate = float(np.mean(values))
    se = float(np.std(values, ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    if n == 1:
        return {
            "n_seeds": n,
            "estimate": estimate,
            "se": se,
            "ci_lower": estimate,
            "ci_upper": estimate,
        }
    rng = np.random.default_rng(_stable_seed("bootstrap", *key, repetitions, ci_level))
    draws = values[rng.integers(0, n, size=(int(repetitions), n))].mean(axis=1)
    alpha = (1.0 - float(ci_level)) / 2.0
    lo, hi = np.quantile(draws, [alpha, 1.0 - alpha])
    return {
        "n_seeds": n,
        "estimate": estimate,
        "se": se,
        "ci_lower": float(lo),
        "ci_upper": float(hi),
    }


def build_route_summary(
    route_seed: pd.DataFrame, repetitions: int, ci_level: float
) -> pd.DataFrame:
    metrics = (
        "generated_mean_delay",
        "alignment_budget_rate",
        "structural_regret_rate",
        "route_regret_rate",
        "transfer_bound_rate",
        "transfer_slack_rate",
        "regret_stability_slack_rate",
        "ranking_reversal_rate",
        "pairwise_sign_disagreement_rate",
        "directed_choice_disagreement_rate",
        "complete_conflict_rate",
        "mean_structural_conflict_margin",
        "min_structural_conflict_margin",
        "mean_route_conflict_margin",
        "min_route_conflict_margin",
        "margin_preservation_rate",
        "mean_reversal_margin",
        "empty_arrival_clock_rate",
        "multiarrival_clock_rate",
        "mean_route_map_age",
    )
    rows = []
    for (mechanism, route), group in route_seed.groupby(
        ["mechanism_id", "route_id"], sort=False
    ):
        for metric in metrics:
            summary = bootstrap_mean(
                group[metric],
                repetitions,
                ci_level,
                ("route", mechanism, route, metric),
            )
            rows.append(
                {
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "route_id": route,
                    "route_display_name": DISPLAY_NAMES[route],
                    "metric_id": metric,
                    **summary,
                    "bootstrap_repetitions": repetitions,
                    "ci_level": ci_level,
                    "run_tier": group["run_tier"].iloc[0],
                    "paper_result": bool(group["paper_result"].iloc[0]),
                }
            )
    return pd.DataFrame(rows)


def build_learner_summary(
    learner_seed: pd.DataFrame, repetitions: int, ci_level: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for (mechanism, binding), group in learner_seed.groupby(
        ["mechanism_id", "feedback_binding_id"], sort=False
    ):
        for metric in ("structural_regret_rate", "context_constrained_regret_rate"):
            summary = bootstrap_mean(
                group[metric],
                repetitions,
                ci_level,
                ("learner", mechanism, binding, metric),
            )
            rows.append(
                {
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "feedback_binding_id": binding,
                    "feedback_binding_display_name": DISPLAY_NAMES[binding],
                    "metric_id": metric,
                    **summary,
                    "bootstrap_repetitions": repetitions,
                    "ci_level": ci_level,
                    "run_tier": group["run_tier"].iloc[0],
                    "paper_result": bool(group["paper_result"].iloc[0]),
                }
            )

    pivot = learner_seed.pivot_table(
        index=["seed", "mechanism_id"],
        columns="feedback_binding_id",
        values="structural_regret_rate",
        aggfunc="first",
    ).reset_index()
    if not {"arrival_clock", "source_round"}.issubset(pivot.columns):
        raise ScientificInvariantError("paired learner seed metrics are incomplete")
    pivot["paired_arrival_minus_source_regret_rate"] = (
        pivot["arrival_clock"] - pivot["source_round"]
    )
    contrast_rows = []
    for mechanism, group in pivot.groupby("mechanism_id", sort=False):
        summary = bootstrap_mean(
            group["paired_arrival_minus_source_regret_rate"],
            repetitions,
            ci_level,
            ("paired_learner", mechanism),
        )
        contrast_rows.append(
            {
                "mechanism_id": mechanism,
                "mechanism_display_name": DISPLAY_NAMES[mechanism],
                "metric_id": "arrival_minus_source_regret_rate",
                **summary,
                "bootstrap_repetitions": repetitions,
                "ci_level": ci_level,
                "run_tier": learner_seed["run_tier"].iloc[0],
                "paper_result": bool(learner_seed["paper_result"].iloc[0]),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(contrast_rows)


def _metric_row(
    summary: pd.DataFrame, mechanism: str, route: str, metric: str
) -> pd.Series:
    subset = summary[
        (summary.mechanism_id == mechanism)
        & (summary.route_id == route)
        & (summary.metric_id == metric)
    ]
    if len(subset) != 1:
        raise ScientificInvariantError(
            f"Expected one summary row for {mechanism}/{route}/{metric}, got {len(subset)}"
        )
    return subset.iloc[0]


def build_figure_data(
    route_summary: pd.DataFrame,
    learner_summary: pd.DataFrame,
    learner_contrasts: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mechanism in MECHANISM_ORDER:
        for metric in (
            "alignment_budget_rate",
            "generated_mean_delay",
            "ranking_reversal_rate",
        ):
            row = _metric_row(route_summary, mechanism, "arrival_assigned", metric)
            rows.append(
                {
                    "figure_id": "fig_exp1_alignment_transfer",
                    "panel_id": "A",
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "series_id": metric,
                    "metric_id": metric,
                    "estimate": row.estimate,
                    "ci_lower": row.ci_lower,
                    "ci_upper": row.ci_upper,
                    "n_seeds": row.n_seeds,
                    "bootstrap_repetitions": row.bootstrap_repetitions,
                    "run_tier": row.run_tier,
                    "paper_result": row.paper_result,
                }
            )
        for metric in ("structural_regret_rate", "transfer_bound_rate"):
            row = _metric_row(route_summary, mechanism, "arrival_assigned", metric)
            rows.append(
                {
                    "figure_id": "fig_exp1_alignment_transfer",
                    "panel_id": "B",
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "series_id": metric,
                    "metric_id": metric,
                    "estimate": row.estimate,
                    "ci_lower": row.ci_lower,
                    "ci_upper": row.ci_upper,
                    "n_seeds": row.n_seeds,
                    "bootstrap_repetitions": row.bootstrap_repetitions,
                    "run_tier": row.run_tier,
                    "paper_result": row.paper_result,
                }
            )
        for binding in ("arrival_clock", "source_round"):
            subset = learner_summary[
                (learner_summary.mechanism_id == mechanism)
                & (learner_summary.feedback_binding_id == binding)
                & (learner_summary.metric_id == "structural_regret_rate")
            ]
            if len(subset) != 1:
                raise ScientificInvariantError(
                    f"Missing learner summary for {mechanism}/{binding}"
                )
            row = subset.iloc[0]
            rows.append(
                {
                    "figure_id": "fig_exp1_alignment_transfer",
                    "panel_id": "C",
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "series_id": binding,
                    "metric_id": "structural_regret_rate",
                    "estimate": row.estimate,
                    "ci_lower": row.ci_lower,
                    "ci_upper": row.ci_upper,
                    "n_seeds": row.n_seeds,
                    "bootstrap_repetitions": row.bootstrap_repetitions,
                    "run_tier": row.run_tier,
                    "paper_result": row.paper_result,
                }
            )
        contrast = learner_contrasts[learner_contrasts.mechanism_id == mechanism]
        if len(contrast) == 1:
            row = contrast.iloc[0]
            rows.append(
                {
                    "figure_id": "fig_exp1_alignment_transfer",
                    "panel_id": "C",
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "series_id": "paired_contrast",
                    "metric_id": "arrival_minus_source_regret_rate",
                    "estimate": row.estimate,
                    "ci_lower": row.ci_lower,
                    "ci_upper": row.ci_upper,
                    "n_seeds": row.n_seeds,
                    "bootstrap_repetitions": row.bootstrap_repetitions,
                    "run_tier": row.run_tier,
                    "paper_result": row.paper_result,
                }
            )
    return pd.DataFrame(rows)


def build_mechanism_table(
    route_summary: pd.DataFrame,
    learner_contrasts: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for mechanism in MECHANISM_ORDER:
        data: dict[str, Any] = {
            "mechanism_id": mechanism,
            "mechanism": DISPLAY_NAMES[mechanism],
        }
        for metric, output in (
            ("generated_mean_delay", "mean_delay"),
            ("alignment_budget_rate", "alignment_budget_rate"),
            ("ranking_reversal_rate", "ranking_reversal_rate"),
            ("margin_preservation_rate", "margin_preservation_rate"),
        ):
            row = _metric_row(route_summary, mechanism, "arrival_assigned", metric)
            data[output] = float(row.estimate)
            data[output + "_ci_lower"] = float(row.ci_lower)
            data[output + "_ci_upper"] = float(row.ci_upper)
        contrast = learner_contrasts[learner_contrasts.mechanism_id == mechanism].iloc[
            0
        ]
        data["arrival_minus_source_regret_rate"] = float(contrast.estimate)
        data["arrival_minus_source_ci_lower"] = float(contrast.ci_lower)
        data["arrival_minus_source_ci_upper"] = float(contrast.ci_upper)
        rows.append(data)
    return pd.DataFrame(rows)


def _format_ci(estimate: float, lower: float, upper: float, digits: int = 3) -> str:
    return f"{estimate:.{digits}f} [{lower:.{digits}f}, {upper:.{digits}f}]"


def write_latex_table(path: Path, table: pd.DataFrame) -> None:
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Mechanism & Mean delay & Alignment budget & Conflict rate & Margin preserved & Arrival $-$ source \\",
        r"\midrule",
    ]
    for row in table.itertuples(index=False):
        lines.append(
            f"{row.mechanism} & "
            f"{_format_ci(row.mean_delay, row.mean_delay_ci_lower, row.mean_delay_ci_upper, 2)} & "
            f"{_format_ci(row.alignment_budget_rate, row.alignment_budget_rate_ci_lower, row.alignment_budget_rate_ci_upper)} & "
            f"{_format_ci(row.ranking_reversal_rate, row.ranking_reversal_rate_ci_lower, row.ranking_reversal_rate_ci_upper)} & "
            f"{_format_ci(row.margin_preservation_rate, row.margin_preservation_rate_ci_lower, row.margin_preservation_rate_ci_upper)} & "
            f"{_format_ci(row.arrival_minus_source_regret_rate, row.arrival_minus_source_ci_lower, row.arrival_minus_source_ci_upper)} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    atomic_write_text(path, "\n".join(lines) + "\n")


def write_manuscript_artifacts(
    output_dir: Path,
    table: pd.DataFrame,
    run_tier: str,
    paper_result: bool,
) -> None:
    values = {
        "run_tier": run_tier,
        "paper_result": bool(paper_result),
        "manuscript_values_available": bool(paper_result),
        "mechanisms": (
            {
                row.mechanism_id: {
                    "mean_delay": row.mean_delay,
                    "alignment_budget_rate": row.alignment_budget_rate,
                    "ranking_reversal_rate": row.ranking_reversal_rate,
                    "margin_preservation_rate": row.margin_preservation_rate,
                    "arrival_minus_source_regret_rate": row.arrival_minus_source_regret_rate,
                }
                for row in table.itertuples(index=False)
            }
            if paper_result
            else {}
        ),
    }
    atomic_write_json(output_dir / "exp1_manuscript_values.json", values)
    macros = [
        "% Auto-generated. Do not edit by hand.",
        f"\\newcommand{{\\ExpOneRunTier}}{{{run_tier}}}",
        f"\\newcommand{{\\ExpOnePaperResult}}{{{'true' if paper_result else 'false'}}}",
    ]
    if paper_result:
        for row in table.itertuples(index=False):
            key = "".join(part.title() for part in row.mechanism_id.split("_"))
            macros.append(
                f"\\newcommand{{\\ExpOne{key}Alignment}}{{{row.alignment_budget_rate:.3f}}}"
            )
            macros.append(
                f"\\newcommand{{\\ExpOne{key}LearnerContrast}}{{{row.arrival_minus_source_regret_rate:.3f}}}"
            )
    else:
        macros.append(
            "% Numerical manuscript macros are withheld until independent paper promotion."
        )
    atomic_write_text(
        output_dir / "exp1_manuscript_macros.tex", "\n".join(macros) + "\n"
    )


def generate_all_derived(
    output_root: Path,
    route_seed: pd.DataFrame,
    learner_seed: pd.DataFrame,
    delay_round: pd.DataFrame,
    route_round: pd.DataFrame,
    repetitions: int,
    ci_level: float,
) -> dict[str, Path]:
    derived_dir = output_root / "derived"
    figure_dir = output_root / "figures" / "data"
    table_dir = output_root / "tables"
    manuscript_dir = output_root / "manuscript"
    for directory in (derived_dir, figure_dir, table_dir, manuscript_dir):
        directory.mkdir(parents=True, exist_ok=True)

    route_summary = build_route_summary(route_seed, repetitions, ci_level)
    learner_summary, contrasts = build_learner_summary(
        learner_seed, repetitions, ci_level
    )
    figure_data = build_figure_data(route_summary, learner_summary, contrasts)
    mechanism_table = build_mechanism_table(route_summary, contrasts)
    delay_survival = build_delay_survival_data(delay_round, repetitions, ci_level)
    state_coupling = build_state_coupling_data(delay_round, repetitions, ci_level)
    reversal_margin_data = build_reversal_margin_data(
        route_round, repetitions, ci_level
    )
    trajectory_data = build_representative_trajectory_data(route_round)

    paths = {
        "route_summary": derived_dir / "exp1_route_summary.csv",
        "learner_summary": derived_dir / "exp1_learner_summary.csv",
        "learner_contrasts": derived_dir / "exp1_actual_learner_contrasts.csv",
        "primary_summary": derived_dir / "exp1_primary_summary.csv",
        "figure_data": figure_dir / "fig_exp1_alignment_transfer_data.csv",
        "mechanism_table_csv": table_dir / "tab_exp1_mechanism_summary.csv",
        "mechanism_table_tex": table_dir / "tab_exp1_mechanism_summary.tex",
        "delay_survival_data": figure_dir / "fig_exp1_delay_survival_data.csv",
        "state_coupling_data": figure_dir / "fig_exp1_state_coupling_data.csv",
        "reversal_margin_data": figure_dir / "fig_exp1_reversal_margin_data.csv",
        "trajectory_data": figure_dir / "fig_exp1_route_trajectory_data.csv",
    }
    atomic_write_csv(paths["route_summary"], route_summary)
    atomic_write_csv(paths["learner_summary"], learner_summary)
    atomic_write_csv(paths["learner_contrasts"], contrasts)
    atomic_write_csv(
        paths["primary_summary"],
        pd.concat(
            [
                route_summary.assign(summary_component="route"),
                learner_summary.assign(summary_component="learner"),
                contrasts.assign(summary_component="paired_contrast"),
            ],
            ignore_index=True,
            sort=False,
        ),
    )
    atomic_write_csv(paths["figure_data"], figure_data)
    atomic_write_csv(paths["mechanism_table_csv"], mechanism_table)
    atomic_write_csv(paths["delay_survival_data"], delay_survival)
    atomic_write_csv(paths["state_coupling_data"], state_coupling)
    atomic_write_csv(paths["reversal_margin_data"], reversal_margin_data)
    atomic_write_csv(paths["trajectory_data"], trajectory_data)
    write_latex_table(paths["mechanism_table_tex"], mechanism_table)
    write_manuscript_artifacts(
        manuscript_dir,
        mechanism_table,
        run_tier=str(route_seed["run_tier"].iloc[0]),
        paper_result=bool(route_seed["paper_result"].iloc[0]),
    )
    metadata = {
        "figure_id": "fig_exp1_alignment_transfer",
        "source_derived_files": [
            str(paths["route_summary"]),
            str(paths["learner_summary"]),
            str(paths["learner_contrasts"]),
        ],
        "source_data_sha256": sha256_file(paths["figure_data"]),
        "panel_definitions": {
            "A": "arrival-route action-gap alignment budget with right-aligned Mean delay and Conflict rate (route-optimal conflict rate) columns",
            "B": "structural regret and regret-transfer upper bound",
            "C": "same contextual Delayed EXP3 under arrival-clock and source-round binding",
        },
        "axis_definitions": {
            "A": "alignment_budget_rate",
            "B": "regret rate",
            "C": "structural_regret_rate",
        },
        "uncertainty_definition": f"{ci_level:.0%} seed bootstrap; {repetitions} repetitions",
        "run_tier": str(route_seed["run_tier"].iloc[0]),
        "paper_result": bool(route_seed["paper_result"].iloc[0]),
    }
    atomic_write_json(
        figure_dir / "fig_exp1_alignment_transfer_metadata.json", metadata
    )
    return paths


def build_delay_survival_data(
    delay_round: pd.DataFrame,
    repetitions: int,
    ci_level: float,
) -> pd.DataFrame:
    evaluation = delay_round[
        delay_round["is_evaluation_source"] == True
    ].copy()  # noqa: E712
    rows: list[dict[str, Any]] = []
    for mechanism in MECHANISM_ORDER:
        group = evaluation[evaluation.mechanism_id == mechanism]
        if group.empty:
            continue
        max_delay = int(group.delay.max())
        for threshold in range(0, max_delay + 1):
            seed_values = (
                group.assign(indicator=group.delay > threshold)
                .groupby("seed", as_index=False)["indicator"]
                .mean()
            )
            summary = bootstrap_mean(
                seed_values.indicator,
                repetitions,
                ci_level,
                ("delay_survival", mechanism, threshold),
            )
            rows.append(
                {
                    "figure_id": "fig_exp1_delay_verification",
                    "panel_id": "A",
                    "mechanism_id": mechanism,
                    "mechanism_display_name": DISPLAY_NAMES[mechanism],
                    "delay_threshold": threshold,
                    "metric_id": "delay_survival_probability",
                    **summary,
                    "bootstrap_repetitions": repetitions,
                    "ci_level": ci_level,
                    "run_tier": group.run_tier.iloc[0],
                    "paper_result": bool(group.paper_result.iloc[0]),
                }
            )
    return pd.DataFrame(rows)


def build_state_coupling_data(
    delay_round: pd.DataFrame,
    repetitions: int,
    ci_level: float,
) -> pd.DataFrame:
    group = delay_round[
        (delay_round.mechanism_id == "state_coupled_delay")
        & (delay_round["is_evaluation_source"] == True)  # noqa: E712
    ].copy()
    if group.empty:
        return pd.DataFrame()
    edges = np.quantile(group.structural_state, np.arange(0, 11) / 10.0)
    edges[0] = -np.inf
    edges[-1] = np.inf
    if np.any(np.diff(edges) <= 0):
        raise ScientificInvariantError(
            "state-coupling decile edges are not strictly increasing"
        )
    group["state_decile"] = (
        np.searchsorted(edges[1:-1], group.structural_state, side="right") + 1
    )
    per_seed = group.groupby(["seed", "state_decile"], as_index=False).agg(
        mean_delay=("delay", "mean"),
        mean_state=("structural_state", "mean"),
    )
    rows = []
    for decile, subset in per_seed.groupby("state_decile", sort=True):
        delay_summary = bootstrap_mean(
            subset.mean_delay,
            repetitions,
            ci_level,
            ("state_coupling", int(decile), "delay"),
        )
        state_summary = bootstrap_mean(
            subset.mean_state,
            repetitions,
            ci_level,
            ("state_coupling", int(decile), "state"),
        )
        rows.append(
            {
                "figure_id": "fig_exp1_delay_verification",
                "panel_id": "B",
                "mechanism_id": "state_coupled_delay",
                "state_decile": int(decile),
                "mean_state": state_summary["estimate"],
                "metric_id": "mean_delay_by_state_decile",
                **delay_summary,
                "bootstrap_repetitions": repetitions,
                "ci_level": ci_level,
                "run_tier": group.run_tier.iloc[0],
                "paper_result": bool(group.paper_result.iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def build_reversal_margin_data(
    route_round: pd.DataFrame,
    repetitions: int,
    ci_level: float,
) -> pd.DataFrame:
    group = route_round[
        (route_round.route_id == "arrival_assigned")
        & (route_round.mechanism_id == "systematic_misbinding")
    ].copy()
    if group.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    per_seed = group.groupby("seed", as_index=False).agg(
        affected_round_fraction=("ranking_reversal", "mean"),
        near_zero_reversal_margin_share=(
            "reversal_margin",
            lambda x: (
                float(np.mean(np.asarray(x)[np.asarray(x) > 0] < 0.05))
                if np.any(np.asarray(x) > 0)
                else 0.0
            ),
        ),
    )
    q10 = (
        group[group.ranking_reversal.astype(bool)]
        .groupby("seed")["reversal_margin"]
        .quantile(0.10)
        .rename("q10_reversal_margin")
        .reset_index()
    )
    per_seed = per_seed.merge(q10, on="seed", how="left").fillna(0.0)
    for metric in (
        "affected_round_fraction",
        "q10_reversal_margin",
        "near_zero_reversal_margin_share",
    ):
        summary = bootstrap_mean(
            per_seed[metric],
            repetitions,
            ci_level,
            ("systematic_reversal_gate", metric),
        )
        rows.append(
            {
                "figure_id": "fig_exp1_reversal_margin",
                "panel_id": "A",
                "mechanism_id": "systematic_misbinding",
                "metric_id": metric,
                **summary,
                "bootstrap_repetitions": repetitions,
                "ci_level": ci_level,
                "run_tier": group.run_tier.iloc[0],
                "paper_result": bool(group.paper_result.iloc[0]),
            }
        )
    reversed_group = group[group.ranking_reversal.astype(bool)]
    for quantile in np.linspace(0.0, 1.0, 21):
        seed_quantiles = reversed_group.groupby("seed")["reversal_margin"].quantile(
            quantile
        )
        summary = bootstrap_mean(
            seed_quantiles,
            repetitions,
            ci_level,
            ("systematic_reversal_distribution", float(quantile)),
        )
        rows.append(
            {
                "figure_id": "fig_exp1_reversal_margin",
                "panel_id": "B",
                "mechanism_id": "systematic_misbinding",
                "metric_id": "reversal_margin_quantile",
                "quantile": float(quantile),
                **summary,
                "bootstrap_repetitions": repetitions,
                "ci_level": ci_level,
                "run_tier": group.run_tier.iloc[0],
                "paper_result": bool(group.paper_result.iloc[0]),
            }
        )
    representative_seed = int(group.seed.min())
    rep = group[group.seed == representative_seed].sort_values("t").copy()
    changes = (
        np.flatnonzero(
            rep.structural_best_action.to_numpy()[1:]
            != rep.structural_best_action.to_numpy()[:-1]
        )
        + 1
    )
    center = int(changes[0]) if changes.size else int(rep.t.median())
    window = rep[(rep.t >= center - 30) & (rep.t <= center + 30)]
    for row in window.itertuples(index=False):
        rows.append(
            {
                "figure_id": "fig_exp1_reversal_margin",
                "panel_id": "C",
                "mechanism_id": "systematic_misbinding",
                "metric_id": "boundary_trajectory",
                "seed": representative_seed,
                "boundary_center": center,
                "t": int(row.t),
                "structural_best_action": int(row.structural_best_action),
                "route_best_action": int(row.route_best_action),
                "ranking_reversal": bool(row.ranking_reversal),
                "reversal_margin": float(row.reversal_margin),
                "run_tier": row.run_tier,
                "paper_result": bool(row.paper_result),
            }
        )
    return pd.DataFrame(rows)


def build_representative_trajectory_data(route_round: pd.DataFrame) -> pd.DataFrame:
    min_seed = int(route_round.seed.min())
    subset = route_round[
        (route_round.seed == min_seed)
        & (route_round.route_id == "arrival_assigned")
        & (
            route_round.mechanism_id.isin(
                ["exact_valid_shift", "systematic_misbinding"]
            )
        )
        & (route_round.t < 150)
    ].copy()
    keep = [
        "seed",
        "mechanism_id",
        "t",
        "structural_best_action",
        "route_best_action",
        "structural_margin",
        "delta_gap",
        "ranking_reversal",
        "route_map_age",
        "arrival_batch_size",
        "run_tier",
        "paper_result",
    ]
    subset = subset[keep]
    subset.insert(0, "figure_id", "fig_exp1_route_trajectory")
    return subset
