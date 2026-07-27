# Exp3 boundary-preserving repair memo — 2026-07-27

## 1. Frozen scientific boundary

This repair does not change the Exp3 question or evidence chain:

1. observable proxy-score recovery;
2. held-out action-gap recovery;
3. offline action-ranking recovery.

The following remain frozen:

- routes: Arrival carrier, Historical mean, Ridge proxy;
- history-only action/group/support design;
- deterministic two-fold user split;
- support-qualified estimands;
- signed ranking shortfall without truncation;
- user-cluster bootstrap conditional on the history-fitted routes;
- no OPE, online policy value, source-label sufficiency, causal action gap, or structural regret claim.

## 2. Scientific implementation repairs

### 2.1 Bootstrap uncertainty

The primary interval is now the basic user-cluster bootstrap interval. Percentile endpoints remain available as diagnostics. Each route/metric records the point estimate, bootstrap mean, median, standard deviation, bias, absolute bias divided by bootstrap SD, both interval definitions, and point-in-interval flags.

Fast warnings are disclosed but do not become paper claims. A full run with any centering warning fails the scientific promotion gate and must be reviewed; the code never forces an interval to contain the point estimate.

### 2.2 Ridge specification

Unfrozen EWMA features were removed. Ridge remains the same model family and alpha, with only:

- action one-hot indicators;
- most recent completed-bin proxy mean;
- log transformed completed-bin count;
- missing-bin indicator.

Action-selection equivalence with Historical mean is reported rather than optimized away.

### 2.3 Full-design support preflight

A real fast run now checks the formal full specification without changing the active fast estimand:

- top 20 history actions;
- candidate group counts 10 then 5;
- 500 events per fold, audit unit, and action.

The replacement appendix figure separates formal support readiness from selected-action exposure-mass coverage. Aggregate support within selected actions is no longer presented as coverage of the full log.

### 2.4 Input and run-lineage disclosure

Boundary quarantine counts and fractions are written into the manifest/report. Self-check resolves the latest successfully completed run, while bootstrap resume resolves the latest run that reached the persisted-array stage. Failed runs cannot shadow a prior successful run.

## 3. Code refactor

Large scientific files were split by responsibility without changing the orchestration framework. New modules include:

- `input_normalization.py`;
- `evaluation_arrays.py`;
- `evaluation_artifacts.py`;
- `bootstrap_intervals.py`;
- `bootstrap_summary.py`;
- `route_diagnostics.py`;
- `support_preflight.py`;
- `run_registry.py`;
- `self_check_helpers.py`.

Every Python source file is below 400 lines. The ten-stage pipeline and command surface remain intact.

## 4. Validation

- `code_check.py`: PASS;
- `pytest`: 18/18 PASS;
- explicit fixture pipeline: PASS;
- fixture self-check: 36/36 PASS;
- fixture bootstrap: 100/100 valid;
- fixture remains `NOT_EVALUATED_FAST_FIXTURE` and cannot be promoted.

The package does not certify new real-data fast values because the raw KuaiRand inputs are intentionally absent. A clean real fast must be rerun after installing this repair.
