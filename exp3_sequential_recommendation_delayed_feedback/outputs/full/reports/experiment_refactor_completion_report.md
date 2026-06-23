# Experiment 3 completion report

## Status

- Run mode: `full`
- Input status: `real_kuairand_1k`
- Run id: `full_20260622T080140Z_ff80ce71f7`
- Paper-result gate: `false` until `python self_check.py --mode full --promote-paper-result` passes on a real-data full run.
- Primary target: `long_value_log` over the next 6 hours after a main-standard source exposure.

## Implemented design decisions

1. The target is a split-consistent constructed future-engagement outcome from the same standard-log stream. It is not a native KuaiRand delayed-feedback timestamp, platform utility, or causal effect of the source exposure.
2. The random-exposure stream is excluded from the primary target because there is no matched historical random stream for proxy fitting.
3. The fixed action vocabulary is constructed from history only. Missing and residual tags remain in update accounting but are not candidate actions.
4. Arrival-time carrier assignment uses the most recent same-user standard exposure at or before feedback arrival. Future exposures are never used as carriers.
5. Partial source-label routes use deterministic event-level mask trajectories. Labelled outcomes update their source action; unlabelled outcomes update the arrival carrier.
6. Ridge proxy coefficients are fit only on history standard and evaluated on main standard. Main-period proxy states use completed history and earlier main bins only; no full-main fallback statistic is used.
7. User-cluster resampling replays empirical dynamic routes. Partial-label intervals additionally sample from a finite bank of independent event-level mask trajectories. Proxy score paths and candidate support remain fixed.
8. `history_mean_static` ranks actions only by completed-history 6h target means. It is a diagnostic control for stable action-category persistence and never uses main-period short-term signals, arrivals, or labels.
9. The run writes `oracle_action_dynamics_summary.csv`, `paired_mechanism_contrast.csv`, and `paired_effect_vs_history_mean_static.csv`. The latter isolates the paired decision-level comparison of each route against the static history control.
10. The source-label sensitivity result is emitted as a table with the absolute expected number of labelled outcomes rather than as a monotonicity-looking curve. Arrival-mechanism contrasts remain CSV-only audits because the current daily-bin evidence does not support a general mechanism claim.

## Interpretation boundary

The package evaluates offline recoverability of a constructed 6h target on logged support under a semi-synthetic pseudo-arrival mechanism. It does not establish native delayed feedback, online causal policy improvement, off-policy policy value, or an official platform utility.
