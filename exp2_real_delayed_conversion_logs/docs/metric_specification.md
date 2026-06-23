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
