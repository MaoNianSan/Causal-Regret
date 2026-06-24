# Exp2 repair notes

## Rerun-readiness repairs

### 1. Clean-run display-hash guard

The runner removes `outputs/<mode>` at the beginning of every fresh run. A fresh run therefore cannot require a prior display-only hash snapshot. The semantic check now treats that snapshot as optional for a clean run and records the display regression as not applicable unless the user deliberately launches a replot-only audit with a before-hash file.

### 2. Delay-composition unit

The main delay-composition panel is a composition of eligible source-event rows, not a unique-conversion distribution. The statistics contract now writes:

```text
n_eligible_source_events
source_event_share_percent
```

This corrects the Panel A denominator and aligns it with the figure caption and paper text.

### 3. UID sentinel integrity

UID values `-1` and `-1.0` now follow the same missingness path as blank or null UIDs. They are excluded before candidate construction, route assignment, and UID-cluster bootstrap. The integrity summary reports the filtered UID sentinel counts.

### 4. Candidate-window diagnostic runtime

Candidate-window sensitivity is appendix-only and reports common-cohort point estimates. It no longer runs a nested UID bootstrap for every window. The main route-sensitivity summary remains the inferential object and uses the configured 200/1000 UID bootstrap replicates in fast/full modes.

The window output explicitly records:

```text
window_bootstrap_replicates=0
window_uncertainty_status=not_computed_point_estimate_common_cohort_diagnostic
```

### 5. Non-destructive semantic checking

A failed manual self-check no longer rewrites existing figure data or metadata. The check reports failure and exits nonzero. Full `paper_result=true` promotion remains gated by the finalizer after a passing semantic check.

### 6. Fixture consistency

The synthetic fixture configuration now uses the production source-time routes, arrival-bin anchor, scientific-gate keys, and current output contracts. The integration runner verifies reproducibility across `--n-jobs=1` and `--n-jobs=4`.

## Rerun requirements

Use the synthetic integration test first, then launch the real fast run. Do not run full until the real fast run has passed `self_check.py` and `code_check.py`.
