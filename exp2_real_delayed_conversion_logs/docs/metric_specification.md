# Exp2 Metric Specification

Exp2 is a logged attribution-sensitivity experiment on observational delayed-conversion logs. It does not estimate causal regret, online policy value, causal effects, ground truth ROI, or deployment performance.

Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity.
It does not estimate causal regret, online policy value, ROI, or a deployable policy comparison.

## Primary Metrics

- `credit_allocation_tv_distance_vs_arrival_anchor`: total-variation distance between a route's normalized source-time decision-cell credit allocation and the constructed `arrival_bin_anchor` allocation.
- `top_k_decision_cell_overlap_vs_arrival_anchor`: set overlap between the route's top-10 source-time decision cells and the arrival-bin anchor's top-10 source-time decision cells.

The arrival-bin anchor is a constructed logged diagnostic allocation, not an observed policy action or policy value estimator.

## Credit Concentration Summary

- `top_k_credited_mass_per_1000_events`
- `top_k_credited_mass_difference_per_1000_events_vs_arrival_anchor`

These fields summarize logged credited mass concentration. They are not utility, welfare, ROI, or online value estimates.

## Appendix Diagnostics

Cost-adjusted scores are diagnostic appendix-only robustness summaries. Source-linked audit, top-k sensitivity, candidate-window sensitivity, and EM assignment diagnostics are table-only diagnostics.

## Delay-composition denominator

`exp2_source_event_delay_profile.csv` is defined over eligible source-event candidate rows in the all-conversion main cohort. The required fields are `n_eligible_source_events` and `source_event_share_percent`. A conversion journey may contribute multiple source events across different delay buckets, so this diagnostic must not be interpreted as a unique-conversion distribution.

## Candidate-window diagnostic runtime contract

Candidate-window sensitivity is an appendix-only common-cohort point-estimate diagnostic. It does not run a separate nested UID bootstrap for every window. The main route-sensitivity summary remains the sole inferential Exp2 object and reports the configured UID-bootstrap confidence intervals. Candidate-window outputs record `window_bootstrap_replicates=0` and `window_uncertainty_status=not_computed_point_estimate_common_cohort_diagnostic`.

