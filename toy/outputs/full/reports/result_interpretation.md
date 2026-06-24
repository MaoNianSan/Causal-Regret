# Toy Result Interpretation Report

## Scope

This report reads existing `outputs/full` CSV artifacts. It does not rerun
`main.py`. The Toy experiment is a diagnostic illustration, not a complete
delayed-bandit benchmark or a real-data validation.

Validated inputs include the seed summary, method summary (12 rows),
trajectory summary, and both figure-source CSV files.

## Result interpretation summary

- **Main mechanism:** Under delayed feedback, naive arrival-time binding has
  higher cumulative structural causal regret than source-labelled updating.
- **Zero-delay sanity:** The mean final-regret gap between `naive` and
  `causal_labelled` is `0.00` under `0_delay`.
- **Delayed mismatch:** Source-labelled updating reduces final regret by
  `38.35%` to `41.72%` relative to `naive`
  across the illustrated delayed settings.
- **Oracle gap:** `causal_labelled` remains above `oracle` by `334.84`
  to `371.08` final-regret units in delayed settings.
  This is expected because the labelled learner is a simple EWMA learner, not
  a full-information policy.
- **Ranking reversal:** Delayed arrivals have non-zero ranking-reversal rates (23.86% to 29.67%), supporting the state-mismatch interpretation.
- **Recommended paper sentence:** In the toy diagnostic, naive arrival-time binding agrees with source-labelled updating under zero delay (mean final regret gap 0.00), but incurs substantially larger structural causal regret under delayed feedback: the source-labelled EWMA learner reduces final regret by 38.35% to 41.72% across the illustrated delayed settings. The remaining gap to the full-information oracle reflects learning and information limits rather than source-action misattribution.
- **Do not claim:** The Toy output does not establish real-system
  effectiveness, proxy sufficiency, universal baseline failure, or a formal
  comparison of delay mechanisms at controlled equal mean delay.

## Final cumulative structural causal regret

| Delay setting | Mean delay | Oracle | Causal-labelled | Naive |
| --- | --- | --- | --- | --- |
| 0_delay | 0.00 | 0.00 | 284.66 | 284.66 |
| geom_0.15 | 6.67 | 0.00 | 370.93 | 636.51 |
| mixed_geom_0.6+0.1_w0.2 | 8.37 | 0.00 | 371.08 | 601.90 |
| piece_0.6to0.15 | 4.13 | 0.00 | 334.84 | 567.47 |

## Delayed mismatch effect

| Delay setting | Mean delay | Oracle | Causal-labelled | Naive | Causal-labelled reduction vs naive |
| --- | --- | --- | --- | --- | --- |
| geom_0.15 | 6.67 | 0.00 | 370.93 | 636.51 | 41.72% |
| mixed_geom_0.6+0.1_w0.2 | 8.37 | 0.00 | 371.08 | 601.90 | 38.35% |
| piece_0.6to0.15 | 4.13 | 0.00 | 334.84 | 567.47 | 40.99% |

The relative ordering is the important mechanism diagnostic. Absolute values
should not be treated as a benchmark result.

## Trajectory ordering

| Delay setting | Time points with naive >= causal-labelled | Time points with causal-labelled >= oracle |
| --- | --- | --- |
| 0_delay | 100.00% | 100.00% |
| geom_0.15 | 99.95% | 100.00% |
| mixed_geom_0.6+0.1_w0.2 | 99.60% | 100.00% |
| piece_0.6to0.15 | 99.90% | 100.00% |

The curves are interpreted over structural decision time `t`. Persistent
separation supports an accumulated attribution-mismatch explanation. This
report does not infer a formal delay-mechanism comparison because the settings
were not designed as equal-mean-delay controls.

## Ranking reversal diagnostics

Source: `outputs/full/summary/toy_seed_summary.csv`.

| Delay setting | Ranking-reversal rate | Mean source-state distance |
| --- | --- | --- |
| 0_delay | 0.00% | 0.0000 |
| geom_0.15 | 29.67% | 0.1489 |
| mixed_geom_0.6+0.1_w0.2 | 28.31% | 0.1402 |
| piece_0.6to0.15 | 23.86% | 0.1199 |

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
