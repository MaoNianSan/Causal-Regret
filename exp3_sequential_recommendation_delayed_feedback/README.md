# Experiment 3: Proxy Score Recovery versus Ranking Recovery

## Scientific scope

Experiment 3 is a logged-support diagnostic using KuaiRand-1K standard
recommendation logs. Its evidence chain is:

\[
\text{score recovery}
\rightarrow
\text{held-out reference-pair gap recovery}
\rightarrow
\text{logged-supported ranking recovery}.
\]

It does not estimate structural causal regret, causal action gaps, off-policy
value, online policy value, deployment performance, or optimal recommendations.

## Frozen design

- History: `log_standard_4_08_to_4_21_1k.csv`
- Evaluation: `log_standard_4_22_to_5_08_1k.csv`
- Time bins: Asia/Shanghai epoch days
- Constructed target: six-hour post-exposure engagement-window target on `[t,t+6h)`
- Candidate actions: history-defined top-20 named tags; fast uses the prespecified top-6 computational scope
- Formal support threshold: 500 events per fold, audit unit, and action
- Audit unit: calendar day by deterministic user hash group
- Reference: deterministic two-fold user split
- Near-tie threshold: frozen from the history gap distribution
- Resampling: 100 user-cluster replications in fast and 1,000 in full

The three routes are:

| Route | Role | Uses predecision-available information | Deployment value estimated |
|---|---|---:|---:|
| Arrival carrier—misbinding control | deliberate source-misbinding control | true | false |
| Historical mean | simple history control | true | false |
| Ridge proxy | history-fitted proxy route | true | false |

## Honest two-fold contract

For each direction `selection_fold -> evaluation_fold`:

1. The reference action is selected from observed target means in the selection fold.
2. Each route action is selected from that route's scores in the same selection fold.
3. Route reference-pair gaps use selection-fold route scores.
4. Target values and target reference-pair gaps use the opposite evaluation fold.

The fold contract is frozen in `design/exp3_design_freeze.json` and independently
reconstructed by self-check.

## Ridge selection

Ridge alpha is selected only from history calendar days by rolling-origin temporal
validation. Training dates are strictly earlier than each validation date, and
validation scores use only history common-supported action cells. The selection
metric is macro supported-cell MAE, and candidates within `1e-4` of the best value
use the larger alpha. The selected value is a run artifact, not source configuration.

```text
tables/exp3_ridge_history_cv.csv
metadata/exp3_ridge_selection_manifest.json
```

Evaluation data cannot be passed to the selector. The selected model is refit on
the complete history split before evaluation scoring.

The target component audit independently reconstructs the six-hour component
windows, reports P0/P25/P50/P75/P90/P95/P99 and the target zero rate, and discloses
that LongView appears in both the constructed target and the observable proxy.

## Canonical outputs

```text
tables/exp3_metric_registry.csv
tables/exp3_primary_route_results.csv
tables/exp3_paired_ranking_contrast.csv
tables/exp3_support_coverage.csv
tables/exp3_gap_error_distribution.csv
tables/exp3_target_component_audit.csv
tables/exp3_ridge_history_cv.csv
diagnostics/exp3_route_selection_diagnostics.csv
```

Primary route metrics include pooled supported-cell Spearman and MAE, maximum
held-out reference-pair gap error, held-out reference-pair sign agreement, signed
cross-fitted reference-minus-route value difference, and top-action agreement with
the fold-selected reference.

The primary paired ranking contrast is:

\[
\text{ridge_over_historical_paired_value_gain}
= L^{Hist} - L^{Ridge}.
\]

Positive values favor Ridge. Negative values favor Historical mean. The signed
per-route value difference may be negative because the fold-selected reference is
not an oracle.

Legacy columns such as `heldout_gap_defect`, `cross_fitted_ranking_shortfall`, and
`pair_coverage` remain for one compatibility release and are marked deprecated in
the metric registry. Reports and figures use canonical names.

## Figures

The main figure is a two-row, three-column presentation of score, reference-pair
gap, and logged-supported ranking recovery:

```text
figures/main/exp3_main_score_gap_ranking.pdf
figures/data/exp3_main_score_gap_ranking_data.csv
figures/metadata/exp3_main_score_gap_ranking_metadata.json
```

The ranking column includes Ridge-over-Historical paired value gain. Calibration,
pair-level gap errors, dependence, support preflight, arrival-carrier diagnostics,
and route-selection concentration are appendix diagnostics sourced only from frozen
tables.

## Resampling interpretation

Full-sample estimates are primary. Open markers and ranges show the empirical
user-resampling sensitivity distribution. They are not confidence intervals and
need not contain the full-sample estimate. Each replication rebuilds user weights,
support, reference actions, route-selected actions, gap metrics, ranking metrics,
and paired contrast while conditioning on the frozen fitted Ridge route.

## Commands

```bash
python -m compileall .
pytest -q

# Explicit software fixture
python main.py fast --synthetic-fixture --n-jobs 4
python main.py self-check --mode fast --output-dir outputs/<fixture_run_id>

# Real-data fast engineering gate
python main.py fast --n-jobs 4
python main.py self-check --mode fast --run-id <real_fast_run_id>
```

Fast is never a paper result. After fast and independent self-check pass, a new
Exp3 full run is required because the two-fold estimand, Ridge selection, primary
schema, paired contrast, bootstrap summary, and main figure changed.

```bash
# Run only after explicit human approval
python main.py full --n-jobs <N>
python main.py self-check --mode full --run-id <new_full_run_id>
python promote.py --run-id <new_full_run_id>
```

Exp1, Exp2, and Exp4 do not need to be rerun. Old promoted Exp3 output remains
immutable legacy evidence and must not be resumed or mixed into a redesigned run.
