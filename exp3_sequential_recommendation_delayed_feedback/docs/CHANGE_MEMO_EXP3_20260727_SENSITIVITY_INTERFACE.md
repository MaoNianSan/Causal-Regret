# Exp3 2026-07-27 Sensitivity-Only Uncertainty Interface

## Decision

Experiment 3 no longer reports the ordinary user-cluster bootstrap output as a formal confidence interval.

The frozen interface is:

```text
primary result                = full-sample point estimate
resampling unit               = user cluster
resampling reconstruction     = support + reference action + pair set rebuilt
resampling range              = empirical 2.5%--97.5% percentile range
resampling role               = sensitivity only
formal_ci_validated           = false
legacy basic reflection       = audit only
```

This change does not alter the target, the three routes, the history-only design freeze, the two-fold reference construction, support qualification, or any score/gap/ranking point estimand.

## Reason

The delayed target uses highly overlapping six-hour source windows. A positive outcome event can enter many source-event targets, so source-event counts are not independent sample sizes. The gap and ranking diagnostics are also non-smooth because they rebuild support sets, choose a held-out reference action, take maxima over action-gap errors, compare signs, and apply argmax.

In the real fast audit, ordinary user-cluster bootstrap distributions were materially shifted relative to the full-sample statistics. Percentile and basic transformations therefore appeared on opposite sides of the point estimate. The formulas and route/metric mapping reconstructed correctly; the issue was not a plotting or sign error.

## New outputs

```text
tables/exp3_data_dependence_structure.csv
derived/exp3_outcome_reuse_quantiles.csv
diagnostics/exp3_data_dependence_structure.json

derived/exp3_bootstrap_structure_draws.parquet
tables/exp3_resampling_structure_diagnostics.csv
diagnostics/exp3_resampling_structure_diagnostics.json

checks/exp3_resampling_sensitivity_audit.csv
figures/appendix/exp3_appendix_dependence_and_selection_structure.pdf
```

The dependence table reports user counts, source-event counts, positive outcome-event counts, right censoring, outcome-event reuse, mean/median/p90/max source windows per positive outcome event, and events per user.

The resampling-structure table reports how often user resampling changes:

- the support set;
- audit-unit validity;
- the held-out reference action;
- each route's selected action;
- the number of valid action gaps.

## Figure interface

The main figure now distinguishes two objects:

- filled marker: full-sample point estimate;
- open marker and horizontal line: resampling median and empirical 95% sensitivity range.

The line is not an error bar around the filled marker and is not required to contain it. Panel A shows full-sample calibration only; calibration sensitivity remains available in the tables and audit.

## Status semantics

```text
scientific_uncertainty_status = SENSITIVITY_ONLY_ACCEPTED
formal_ci_validated           = false
```

A centering warning remains visible as a diagnostic. It no longer creates a false claim that a formal CI has failed, because no formal CI is asserted. Full readiness still requires input, engineering, scientific-contract, figure-contract, and support-preflight gates.

## Manuscript wording

Suggested methods text:

> We report full-sample recoverability estimates as the primary experimental results. The constructed delayed targets use highly overlapping six-hour source windows, and the gap and ranking diagnostics additionally involve data-dependent support sets, held-out reference-action selection, maxima, signs, and argmax operations. Ordinary user-cluster bootstrap distributions can therefore be materially shifted relative to the full-sample statistic. We report the empirical 2.5%--97.5% user-cluster resampling range only as a sensitivity diagnostic and do not interpret it as a formally validated confidence interval. The appendix reports target-window reuse and support/reference/selection switching under user resampling.

Suggested results text:

> Filled markers denote full-sample estimates. Open markers and horizontal ranges summarize the empirical user-cluster resampling distribution. Separation between the full-sample estimate and the resampling distribution is interpreted as sensitivity of the non-smooth diagnostic to user-level perturbations, not as a plotting error or a confidence-interval exclusion event.

## Boundary

Formal non-regular inference, subsampling calibration, numerical delta methods, and metric-specific confidence procedures remain outside the scope of Exp3. No additional model family or route has been introduced.
