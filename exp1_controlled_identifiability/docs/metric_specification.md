# EXP1 metric specification

## Primary metric

The primary outcome is contextual structural causal regret per round. At time
`t`, each learner observes the public context `X_t`. Let the conditional risk
of action `a` be the expected state-dependent loss given `X_t`. The comparator
is the action with minimum conditional risk under that same public context.

The run-level result `final_Rc` is the sum of per-step conditional-risk
excesses. The primary reported result is:

```text
causal_regret_per_round = final_Rc / T
```

## Diagnostic metrics

- `mean_delay`: realised observed mean delay for the run.
- `trace_observed_mean_delay`: path-level calibration reference shared across
  methods in policy-independent settings.
- `loss_map_mismatch_rate`: rate at which the arrival-time loss-map comparison
  differs from the source-time comparison.
- `delta_attr_event_per_arrival`: signed event-level attribution distortion.
- `abs_delta_attr_event_per_arrival`: magnitude of event-level attribution
  distortion.
- `source_state_mismatch_mean`: mean source-versus-arrival state discrepancy.
- `soft_attribution_true_mass`: posterior mass assigned to the true source.
- `soft_attribution_top1_accuracy`: top-one source recovery rate.
- `assignment_entropy`: posterior source-assignment entropy.
- `proxy_state_error_mean`: time-averaged state-proxy error.

## Statistical protocol

- Repetition unit: shared simulation seed.
- Fast mode: `3` seeds; full mode: `30` seeds.
- Main uncertainty: percentile bootstrap across seed-level values.
- Bootstrap resamples: `2000`.
- Confidence level: `0.95`.
- Pairwise contrasts are computed within seed.

No diagnostic metric is a substitute for the primary regret metric in the main
Experiment 1 claim.
