import argparse
from pathlib import Path

import pandas as pd

DELAYED_SETTINGS = [
    "geom_0.15",
    "mixed_geom_0.6+0.1_w0.2",
    "piece_0.6to0.15",
]
METHODS = ["oracle", "causal_labelled", "naive"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interpret existing Toy outputs without rerunning the experiment."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Toy outputs directory relative to analyze_results.py or absolute path.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "fast"],
        default="full",
        help="Read outputs/full or outputs/fast and write a Markdown report.",
    )
    return parser.parse_args()


def resolve_outputs_root(base: Path, output_dir: str) -> Path:
    path = Path(output_dir)
    return path if path.is_absolute() else (base / path).resolve()


def require_file(path: Path) -> Path:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty required input: {path}")
    return path


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def load_inputs(mode_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_dir = mode_root / "summary"
    figures_dir = mode_root / "figures"
    seed = pd.read_csv(require_file(summary_dir / "toy_seed_summary.csv"))
    method = pd.read_csv(require_file(summary_dir / "toy_method_summary.csv"))
    trajectory = pd.read_csv(require_file(summary_dir / "toy_trajectory_summary.csv"))

    # Read figure-source files as part of the paper-use validation layer.
    pd.read_csv(require_file(figures_dir / "toy_selected_trajectories_data.csv"))
    pd.read_csv(require_file(figures_dir / "toy_full_trajectories_data.csv"))
    return seed, method, trajectory


def final_regret_table(seed: pd.DataFrame) -> pd.DataFrame:
    table = (
        seed.groupby(["delay_setting", "method"], as_index=False)["final_Rc"]
        .mean()
        .pivot(index="delay_setting", columns="method", values="final_Rc")
    )
    return table.reindex(columns=METHODS)


def mean_delay_table(seed: pd.DataFrame) -> pd.Series:
    return seed.groupby("delay_setting")["mean_delay"].mean()


def curve_ordering_table(trajectory: pd.DataFrame) -> pd.DataFrame:
    pivot = trajectory.pivot(
        index=["delay_setting", "t"],
        columns="method",
        values="mean_cumulative_Rc",
    )
    rows = []
    for delay_setting, group in pivot.groupby(level="delay_setting"):
        rows.append(
            {
                "delay_setting": delay_setting,
                "naive_ge_causal_pct": 100.0
                * (group["naive"] >= group["causal_labelled"]).mean(),
                "causal_ge_oracle_pct": 100.0
                * (group["causal_labelled"] >= group["oracle"]).mean(),
            }
        )
    return pd.DataFrame(rows).set_index("delay_setting")


def load_ranking_reversal(
    outputs_root: Path, mode: str, seed: pd.DataFrame
) -> tuple[pd.DataFrame | None, str]:
    """Load diagnostics from the same mode's summary whenever possible.

    Full mode intentionally omits raw trajectories, so silently falling back to
    ``outputs/fast`` can mix an old fast configuration with new full results.
    The per-seed summary now carries the required diagnostics and is therefore
    the authoritative source for both modes.
    """
    summary_columns = {
        "delay_setting",
        "ranking_reversal_rate",
        "source_state_distance_mean",
    }
    if summary_columns.issubset(seed.columns):
        result = seed.groupby("delay_setting", as_index=True).agg(
            ranking_reversal_rate=("ranking_reversal_rate", "mean"),
            mean_source_state_distance=("source_state_distance_mean", "mean"),
        )
        return result, f"`outputs/{mode}/summary/toy_seed_summary.csv`"

    # Backward-compatible fallback for legacy fast runs only. Never use a fast
    # raw log to interpret a full run, because the configurations may differ.
    preferred = outputs_root / mode / "raw" / "arrival_log.csv"
    if mode == "fast" and preferred.exists():
        arrival = pd.read_csv(preferred)
        dedupe_columns = ["delay_setting", "seed", "clock_t", "source_t", "delay_tau"]
        diagnostic = arrival.drop_duplicates(subset=dedupe_columns)
        return (
            pd.DataFrame(
                {
                    "ranking_reversal_rate": diagnostic.groupby("delay_setting")[
                        "ranking_reversal"
                    ].mean(),
                    "mean_source_state_distance": diagnostic.groupby("delay_setting")[
                        "source_state_distance"
                    ].mean(),
                }
            ),
            "`outputs/fast/raw/arrival_log.csv` (legacy fallback)",
        )
    return None, "unavailable because the same-mode summary lacks diagnostics"


def build_report(
    *,
    mode: str,
    seed: pd.DataFrame,
    method: pd.DataFrame,
    trajectory: pd.DataFrame,
    ranking: pd.DataFrame | None,
    ranking_source: str,
) -> str:
    final = final_regret_table(seed)
    delays = mean_delay_table(seed)
    ordering = curve_ordering_table(trajectory)

    zero_gap = abs(
        final.loc["0_delay", "naive"] - final.loc["0_delay", "causal_labelled"]
    )
    delayed_rows = []
    for setting in DELAYED_SETTINGS:
        naive = final.loc[setting, "naive"]
        causal = final.loc[setting, "causal_labelled"]
        oracle = final.loc[setting, "oracle"]
        improvement = 100.0 * (naive - causal) / abs(naive) if naive else 0.0
        delayed_rows.append(
            [
                setting,
                fmt(delays.loc[setting]),
                fmt(oracle),
                fmt(causal),
                fmt(naive),
                fmt(improvement) + "%",
            ]
        )

    final_rows = []
    for setting in final.index:
        final_rows.append(
            [
                setting,
                fmt(delays.loc[setting]),
                fmt(final.loc[setting, "oracle"]),
                fmt(final.loc[setting, "causal_labelled"]),
                fmt(final.loc[setting, "naive"]),
            ]
        )

    ordering_rows = []
    for setting in ordering.index:
        ordering_rows.append(
            [
                setting,
                fmt(ordering.loc[setting, "naive_ge_causal_pct"]) + "%",
                fmt(ordering.loc[setting, "causal_ge_oracle_pct"]) + "%",
            ]
        )

    if ranking is None:
        ranking_section = (
            f"Ranking-reversal diagnostics are {ranking_source}. "
            "Generate fast-mode raw logs only if this auxiliary diagnostic is needed."
        )
        ranking_summary = "Ranking-reversal diagnostics are unavailable."
    else:
        ranking_rows = []
        for setting in ranking.index:
            ranking_rows.append(
                [
                    setting,
                    fmt(100.0 * ranking.loc[setting, "ranking_reversal_rate"]) + "%",
                    fmt(ranking.loc[setting, "mean_source_state_distance"], 4),
                ]
            )
        ranking_section = f"Source: {ranking_source}.\n\n" + markdown_table(
            [
                "Delay setting",
                "Ranking-reversal rate",
                "Mean source-state distance",
            ],
            ranking_rows,
        )
        delayed_ranking = ranking.reindex(DELAYED_SETTINGS)["ranking_reversal_rate"]
        ranking_summary = (
            "Delayed arrivals have non-zero ranking-reversal rates "
            f"({fmt(100.0 * delayed_ranking.min())}% to "
            f"{fmt(100.0 * delayed_ranking.max())}%), supporting the state-mismatch "
            "interpretation."
        )

    delayed_improvements = [
        100.0
        * (final.loc[setting, "naive"] - final.loc[setting, "causal_labelled"])
        / abs(final.loc[setting, "naive"])
        for setting in DELAYED_SETTINGS
    ]
    min_improvement = min(delayed_improvements)
    max_improvement = max(delayed_improvements)
    causal_oracle_gaps = [
        final.loc[setting, "causal_labelled"] - final.loc[setting, "oracle"]
        for setting in DELAYED_SETTINGS
    ]

    paper_sentence = (
        "In the toy diagnostic, naive arrival-time binding agrees with source-labelled "
        f"updating under zero delay (mean final regret gap {fmt(zero_gap)}), but incurs "
        f"substantially larger structural causal regret under delayed feedback: the "
        f"source-labelled EWMA learner reduces final regret by {fmt(min_improvement)}% "
        f"to {fmt(max_improvement)}% across the illustrated delayed settings. The "
        "remaining gap to the full-information oracle reflects learning and information "
        "limits rather than source-action misattribution."
    )

    return f"""# Toy Result Interpretation Report

## Scope

This report reads existing `outputs/{mode}` CSV artifacts. It does not rerun
`main.py`. The Toy experiment is a diagnostic illustration, not a complete
delayed-bandit benchmark or a real-data validation.

Validated inputs include the seed summary, method summary ({len(method)} rows),
trajectory summary, and both figure-source CSV files.

## Result interpretation summary

- **Main mechanism:** Under delayed feedback, naive arrival-time binding has
  higher cumulative structural causal regret than source-labelled updating.
- **Zero-delay sanity:** The mean final-regret gap between `naive` and
  `causal_labelled` is `{fmt(zero_gap)}` under `0_delay`.
- **Delayed mismatch:** Source-labelled updating reduces final regret by
  `{fmt(min_improvement)}%` to `{fmt(max_improvement)}%` relative to `naive`
  across the illustrated delayed settings.
- **Oracle gap:** `causal_labelled` remains above `oracle` by `{fmt(min(causal_oracle_gaps))}`
  to `{fmt(max(causal_oracle_gaps))}` final-regret units in delayed settings.
  This is expected because the labelled learner is a simple EWMA learner, not
  a full-information policy.
- **Ranking reversal:** {ranking_summary}
- **Recommended paper sentence:** {paper_sentence}
- **Do not claim:** The Toy output does not establish real-system
  effectiveness, proxy sufficiency, universal baseline failure, or a formal
  comparison of delay mechanisms at controlled equal mean delay.

## Final cumulative structural causal regret

{markdown_table(["Delay setting", "Mean delay", "Oracle", "Causal-labelled", "Naive"], final_rows)}

## Delayed mismatch effect

{markdown_table(["Delay setting", "Mean delay", "Oracle", "Causal-labelled", "Naive", "Causal-labelled reduction vs naive"], delayed_rows)}

The relative ordering is the important mechanism diagnostic. Absolute values
should not be treated as a benchmark result.

## Trajectory ordering

{markdown_table(["Delay setting", "Time points with naive >= causal-labelled", "Time points with causal-labelled >= oracle"], ordering_rows)}

The curves are interpreted over structural decision time `t`. Persistent
separation supports an accumulated attribution-mismatch explanation. This
report does not infer a formal delay-mechanism comparison because the settings
were not designed as equal-mean-delay controls.

## Ranking reversal diagnostics

{ranking_section}

Ranking reversal means that the optimal action at source time differs from the
optimal action when the feedback arrives. It is auxiliary mechanism evidence:
an old observation can describe a different structural decision state from the
one faced at update time.

## Paper-use guidance

Use the zero-delay result as a sanity check and the delayed naive-versus-labelled
gap as the main appendix illustration. Use ranking reversal as supporting
diagnostic evidence. Explain the labelled-versus-oracle gap as a separation
between attribution correction and full-information optimality.

Do not use this Toy report as a substitute for Experiments 1-4.
"""


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent
    outputs_root = resolve_outputs_root(base, args.output_dir)
    mode_root = outputs_root / args.mode
    seed, method, trajectory = load_inputs(mode_root)
    ranking, ranking_source = load_ranking_reversal(outputs_root, args.mode, seed)
    report = build_report(
        mode=args.mode,
        seed=seed,
        method=method,
        trajectory=trajectory,
        ranking=ranking,
        ranking_source=ranking_source,
    )
    report_dir = mode_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "result_interpretation.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
