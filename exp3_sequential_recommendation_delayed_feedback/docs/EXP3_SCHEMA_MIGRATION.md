# Exp3 Schema Migration

## Route metadata

Removed from canonical outputs:

```text
is_deployable
```

Replaced by:

```text
uses_predecision_available_information
deployment_value_estimated
```

No route estimates deployment value.

## Support metadata

Canonical field:

```text
reference_pair_coverage
```

Definition:

```text
(supported_action_count - 1) / (candidate_action_count - 1)
```

`pair_coverage` remains a deprecated compatibility alias for one release. It
does not mean coverage over all unordered action pairs. The metric registry emits
an explicit deprecated alias row whose `canonical_metric_id` is
`reference_pair_coverage`.

## Route metrics

| Deprecated alias | Canonical field |
|---|---|
| `score_spearman_correlation` | `pooled_supported_cell_spearman` |
| `score_calibration_mae` | `pooled_supported_cell_mae` |
| `heldout_gap_defect` | `maximum_heldout_reference_pair_gap_error` |
| `gap_sign_agreement` | `heldout_reference_pair_sign_agreement` |
| `valid_gap_pair_count` | `valid_reference_pair_count` |
| `cross_fitted_ranking_shortfall` | `signed_cross_fitted_reference_minus_route_value_difference` |
| `top_action_match_rate` | `top_action_agreement_with_fold_reference` |

New secondary score fields:

```text
exposure_weighted_supported_cell_mae
within_audit_unit_centered_spearman
calibration_intercept
calibration_slope
```

New secondary gap fields:

```text
mean_absolute_reference_pair_gap_error
p90_absolute_reference_pair_gap_error
near_tie_pair_share
```

## Paired contrast

Old local identifier:

```text
ranking_improvement_vs_history
```

Canonical output:

```text
contrast_id=ridge_over_historical
metric_id=ridge_over_historical_paired_value_gain
full_sample_estimate=L_hist-L_ridge
positive_favors=ridge_proxy
formal_ci_validated=false
```

## Ridge selection

Removed source field:

```text
ridge_alpha=4.0
```

New source contract:

```text
ridge_alpha_grid
ridge_cv_min_train_days
ridge_cv_metric
ridge_cv_tie_tolerance
ridge_cv_tie_break
```

The selected alpha is persisted only in:

```text
tables/exp3_ridge_history_cv.csv
metadata/exp3_ridge_selection_manifest.json
metadata/exp3_model_manifest.json
```

Rolling validation rows are evaluated only on history common-supported action
cells. The final model manifest records `final_refit_scope=full_history_training_cells`.

## Target component audit

`tables/exp3_target_component_audit.csv` now reconstructs component totals inside
each `[t,t+6h)` source window. It reports the complete frozen quantile set, target
zero rate, right-censoring count, component nonzero rates, mean and total weighted
contributions, contribution shares, and the LongView shared-component disclosure.

## Resume compatibility

Redesigned runs freeze and verify:

```text
source-tree hash
config hash
metric registry hash
selected-alpha manifest hash
design contract hash
evaluation-array schema version
```

Legacy Exp3 runs are intentionally incompatible with redesigned
`--resume-bootstrap`.
