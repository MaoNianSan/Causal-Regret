# Experiment 2: Attribution Sensitivity in Delayed-Conversion Logs

Experiment 2 measures within-campaign source-day attribution sensitivity on a
fixed delayed-conversion log. It does not identify a causally correct route or
estimate deployment value, ROI, profit, uplift, or structural causal regret.

## Frozen v2 Design

- Schema: `exp2_attribution_sensitivity_v2`
- Primary candidate window: 7 days
- Long-window robustness: 30 days
- Decision cell: `(campaign_id, source_date_utc)`
- Primary support: at least 50 eligible impressions and 60 eligible cells
- Primary ranking depth: Top-10
- Time-decay half-life: 1.38629436112 days
- Uncertainty summary: empirical 2.5%-97.5% UID-resampling range

All primary routes share the same journey cohort, candidate source cells,
decision-cell universe, impression denominator, Kendall support, and UID draws.

## Routes

1. `arrival_time_accounting_anchor`
2. `first_click_or_touch`
3. `last_click_or_touch`
4. `linear_source_cell_credit`
5. `time_decay_source_cell_credit`

`em_soft_credit` is exploratory and disabled by default. The logged attribution
field is retained only as an audit reference.

## Metrics

- Allocation layer: total variation of credited-conversion allocation shares
- Ordering layer: Kendall's tau-b on frozen union-positive-credit support
- Head-membership diagnostic: Top-k overlap and set disagreement
- Mechanism diagnostic: ambiguity-stratified journey assignment TV

The ranking score is `source_time_credit_score`, defined as credited conversion
mass per eligible impression. It is not named or interpreted as a conversion
rate, utility, or campaign-performance measure.

## Commands

```bash
python -m compileall exp2_real_delayed_conversion_logs
pytest -q exp2_real_delayed_conversion_logs/tests
python exp2_real_delayed_conversion_logs/main.py fast
python exp2_real_delayed_conversion_logs/main.py cohort-check --mode full
```

The formal run is intentionally separate and requires explicit authorization:

```bash
python exp2_real_delayed_conversion_logs/main.py full
```

Fast runs are always `INELIGIBLE_FAST`. Development overrides and legacy-schema
runs cannot be promoted.

## Main Outputs

```text
derived/cohort_flow.csv
derived/cohort_scope.json
derived/temporal_coverage.csv
derived/primary_comparisons.csv
derived/ambiguity_mechanism.csv
derived/targeted_robustness.csv
figures/figure_exp2_attribution_sensitivity_source.csv
figures/figure_exp2_attribution_sensitivity.pdf
tables/table_exp2_cohort_flow.csv
tables/table_exp2_primary_results.csv
audit/self_check.json
run_manifest.json
```

Changing the primary window from 30 to 7 days requires a complete Exp2 rerun.
It does not require rerunning Exp1, Exp3, or Exp4.
