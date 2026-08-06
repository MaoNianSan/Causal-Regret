# Exp2 Pre-Refactor Baseline

This snapshot records the local Exp2 baseline before the v2 design migration.

## BASELINE_TEST_STATUS

- `pytest -q exp2_real_delayed_conversion_logs/tests`: `15 passed` (2026-08-06).
- The baseline test suite exercises route conservation, frozen Kendall support,
  UID-cluster resampling, reporting contracts, and promotion checks.

## BASELINE_FAST_STATUS

- Existing fast output: `outputs/exp2-fast-20260727T100101+0800`.
- Existing fast run is legacy behavior and is not a v2 paper result.

## BASELINE_CONFIG_HASH

- SHA-256 of the pre-refactor `config.yaml`:
  `120FB6EC73E988B32F51C27F0819060372E7CD25C05EE205DD80A477685BAE99`.

## BASELINE_ROUTE_IDS

- `arrival_bin_anchor`
- `first_touch`
- `last_touch`
- `linear_credit`
- `time_decay_credit`

## BASELINE_OUTPUT_SCHEMA

- Primary output used `decision_cell_score`, `ranking_displacement_at_k`,
  `common_active_support_count`, and percentile fields named as CI values.
- Main figure source data did not include Kendall for every comparison row.

## BASELINE_MODULE_LINE_COUNTS

| Module | Lines |
|---|---:|
| `bootstrap.py` | 502 |
| `cohort.py` | 239 |
| `data_io.py` | 437 |
| `metrics.py` | 494 |
| `reporting.py` | 590 |
| `routes.py` | 364 |
| `runner.py` | 446 |
| `targeted.py` | 311 |
| `validation.py` | 407 |

The v2 implementation keeps the mathematical contracts while moving the public
schema to `exp2_attribution_sensitivity_v2` and descriptive UID-resampling ranges.
