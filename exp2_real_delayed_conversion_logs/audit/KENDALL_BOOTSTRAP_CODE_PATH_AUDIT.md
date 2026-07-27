# Kendall Bootstrap Code-Path Audit

## Scope and status

This is the pre-modification code-path audit for `outputs/exp2-full-20260726T235202+0800`. No implementation change had started when this record was written.

## Full-sample path

`main.py` dispatches to `runner.run_experiment`. Runner constructs all route assignments and calls `metrics.compute_primary_metrics`. That function first calls `metrics.build_route_allocations`, which expands every primary route onto the same decision-cell universe, fills absent credits with zero, and defines:

```python
decision_cell_score = credited_conversion_mass / eligible_impression_count
```

For both arrival-anchor comparisons and source-route pairs, `metrics._pair_metrics_from_allocations` calls `metrics.kendall_tau_b`. The full-sample support is the union of cells having positive full-sample credit on either compared route:

```python
active = (full_left_credits > 0) | (full_right_credits > 0)
```

The reported point `common_active_support_count` is therefore a full-sample value. Kendall is evaluated as SciPy tau-b with `nan_policy="omit"`. A support smaller than two returns NaN before the SciPy call.

## Bootstrap path

Runner separately calls `bootstrap.run_uid_cluster_bootstrap`. `bootstrap._build_state` creates one UID-by-cell sparse credit matrix per route on the same sorted decision-cell universe. Each `_run_replicate` draws UID multiplicities, aggregates credits, computes scores using the same eligible-impression denominators, then calls `bootstrap._pair_metrics`.

Inside `_pair_metrics`, support is recomputed for each replicate:

```python
active = (left["credits"] > 0) | (right["credits"] > 0)
```

Consequently, UID resampling can turn full-sample-active cells into joint-zero cells, exclude them from that replicate's Kendall vectors, and reduce or vary `common_active_support_count`. The bootstrap field is dynamic even though it has the same name as the fixed point-result field.

## Consistency checks

- Arrival-anchor and source-route comparisons use the same support logic within each path.
- Both paths align credits to the same decision-cell universe and fill absent mass with zero.
- Both paths define scores as credits divided by eligible impressions.
- Neither path renormalizes Kendall score vectors. Route-total normalization is only used for allocation TV, and positive scalar normalization would not change ranks in any event.
- Both paths request `variant="b"`; Kendall ties are not randomly broken.
- Bootstrap support below two returns NaN. Constant vectors with larger support are passed to SciPy and can return NaN. `_quantile_summary` drops NaNs without reporting their fraction.
- Full-sample and bootstrap Kendall calculations do not share the same metric function: they duplicate the calculation in `metrics.py` and `bootstrap.py`.

## Preliminary conclusion

The implementation does not freeze Kendall support. Replicate-specific support drift is the leading root-cause hypothesis, but code inspection alone is not sufficient to authorize a repair. The existing full artifacts and an A/B recomputation must establish its empirical effect and rule out normalization and tie-degeneracy explanations.
