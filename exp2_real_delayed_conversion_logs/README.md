# Experiment 2: Attribution Sensitivity in Delayed-Conversion Logs

## 1. Experiment Objective
This experiment measures attribution sensitivity on a fixed delayed-conversion log using multiple route definitions and support-aware diagnostics.

## 2. Scientific Boundary
The experiment is an attribution sensitivity diagnostic. It does not identify a causally correct attribution rule or estimate deployment value, ROI, profit, uplift, or structural causal regret.

## 3. Data and Split
The analysis uses a fixed delayed-conversion log with a frozen decision-cell universe, impression denominator, support thresholds, and UID-resampling procedure. The primary and robustness windows are fixed by the experiment contract.

## 4. Estimand / Metrics
The main estimands are allocation-layer variation, ordering-layer Kendall agreement, head-membership overlap, and ambiguity-stratified mechanism diagnostics. The ranking score is the credited-conversion mass per eligible impression and is not interpreted as a conversion rate or policy value.

## 5. Implementation Contract
The pipeline is organized around cohort construction, routing diagnostics, support checks, table generation, and self-check validation. The route definitions and frozen schema are maintained as part of the scientific contract.

## 6. Output Artifacts
Primary outputs include cohort summaries, comparison tables, ambiguity diagnostics, figures, and the self-check manifest.

## 7. Validation and Self-check
The package validates cohort support, route diagnostics, and self-check outputs before any promotion step. Development overrides and legacy-schema runs are not paper candidates.

## 8. Running Commands
```bash
python -m compileall exp2_real_delayed_conversion_logs
pytest -q exp2_real_delayed_conversion_logs/tests
python exp2_real_delayed_conversion_logs/main.py fast
python exp2_real_delayed_conversion_logs/main.py cohort-check --mode full
python exp2_real_delayed_conversion_logs/main.py full
```

## 9. Known Limitations
Changing the primary window from 30 to 7 days requires a complete Exp2 rerun. Exp2 does not require rerunning Exp1, Exp3, or Exp4.

