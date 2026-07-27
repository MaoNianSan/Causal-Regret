# Kendall Bootstrap Root-Cause Report

## Classification

`MULTIPLE_CAUSES`

The implementation has confirmed replicate-specific support drift, which makes the old Kendall bootstrap estimand inconsistent with the point estimand. After that support error is removed experimentally, a separate percentile-bootstrap distribution shift remains for all six source-route pairs. The latter is a statistical property to report, not a reason to change the frozen interval method.

## Evidence

Variant A reconstructed the existing full run from `route_assignments.parquet`, `journey_manifest.parquet`, and `decision_cell_universe.parquet` using the declared UID seed policy. It reproduced every saved support count and Kendall tau-b draw exactly.

All ten comparisons drifted in all 1,000 replicates. Examples:

| Comparison | Full support | Dynamic min | Dynamic mean | Dynamic max |
| --- | ---: | ---: | ---: | ---: |
| First vs Arrival | 3,866 | 2,898 | 2,967.201 | 3,042 |
| Last vs Arrival | 3,118 | 2,335 | 2,400.685 | 2,464 |
| First vs Last | 4,177 | 3,124 | 3,194.951 | 3,281 |
| Linear vs Time-decay | 5,106 | 3,848 | 3,966.369 | 4,117 |

Variant B used the full-sample union-positive `decision_cell_id` support. For every comparison its support minimum, mean, median, and maximum equaled the full-sample count. It produced no NaN, constant-vector, or zero-mass-vector replicate.

Frozen support moved all four arrival-anchor percentile intervals into alignment with their point estimates. It did not do so for the six source-route pairs. Those fixed-support distributions remain shifted, including First vs Last (point 0.2985, fixed-support 95% CI [0.4075, 0.4503]) and Linear vs Time-decay (point 0.6863, fixed-support 95% CI [0.7808, 0.8045]). This remaining behavior must not be repaired by changing the interval method.

## Hypothesis assessment

- **H1, replicate-specific support drift:** confirmed by code, saved draws, and exact reconstruction.
- **H2, normalization or zero-mass mismatch:** not supported. Both paths align to the same cell universe, fill absent credits with zero, and use `credits / eligible_impressions` as Kendall scores. No replicate had a zero-mass comparison vector.
- **H3, tie degeneracy:** not supported as the failure classification. Tau-b handles ties explicitly, and no replicate was constant or NaN. Zero ties do contribute to the statistic's non-smooth sampling behavior, but there is no degenerate-sample failure.
- **H4, percentile behavior with correct support:** confirmed for the six source-route pairs because their points remain outside the fixed-support percentile intervals.

## Validity impact

The existing full-sample Kendall point estimates remain valid because their code path already used the declared full-sample union-positive support. The old Kendall confidence intervals do not remain valid for that estimand: each replicate silently selected a different support.

Allocation TV, Top-k overlap, ranking displacement, mean journey-assignment TV, route credit conservation, and all corresponding point estimates are unaffected. Their bootstrap calculations never use the Kendall active mask.

## Minimum correction

Freeze each comparison's support as stable decision-cell IDs when constructing bootstrap state. Bootstrap must align UID-resampled credits to the fixed cell universe and evaluate tau-b on that stored support even when some frozen cells become joint zero. It must report support invariance and degeneracy rates, and validation must fail or stop review on support drift or excessive NaN. No cohort, route, metric, bootstrap unit, repetition count, seed, confidence level, or interval method should change.
