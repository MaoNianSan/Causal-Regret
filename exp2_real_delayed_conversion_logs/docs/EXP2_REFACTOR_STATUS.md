# Exp2 v2 Refactor Status

Status date: 2026-08-06

## Modification Summary

- Implemented schema `exp2_attribution_sensitivity_v2`.
- Changed the primary candidate window from 30 days to 7 days and retained 30 days as targeted robustness.
- Migrated all new-run route IDs and paper labels to the canonical v2 names.
- Replaced `decision_cell_score` with `source_time_credit_score` and removed ranking-displacement output in favor of `top_k_set_disagreement`.
- Replaced CI-named fields with q025/q500/q975 empirical UID-resampling fields.
- Added cumulative cohort flow, temporal coverage, ambiguity mechanism, targeted robustness, unified main-figure source data, and artifact manifests.
- Disabled exploratory EM execution by default.
- Added `cohort-check --mode full` and preserved the prohibition on automatically running formal full.
- Moved the implementation into `exp2_core/`; legacy top-level imports are thin compatibility facades and do not duplicate scientific code.

## File Changes

### Created

- `exp2_core/` implementation package with cohort, raw-data, route, metric, resampling, robustness, reporting, validation, and pipeline modules.
- `docs/EXP2_PRE_REFACTOR_BASELINE.md`.
- `docs/EXP2_REFACTOR_STATUS.md`.

### Modified

- `config.yaml`, `contracts.py`, `main.py`, `promote.py`, `README.md`, and Exp2 tests.
- Top-level `cohort.py`, `data_io.py`, `routes.py`, `metrics.py`, `bootstrap.py`, `targeted.py`, `reporting.py`, `validation.py`, and `runner.py` are compatibility facades.

### Deleted

- No legacy output directories were deleted.
- No Exp1, Exp3, or Exp4 files were changed by this Exp2 refactor.

## Tests And Runs

```text
COMPILEALL_STATUS=PASS
TEST_COUNT=15
TEST_STATUS=PASS
FAST_RUN_ID=exp2-fast-20260806T142102+0800
FAST_STATUS=PASS
FAST_SCHEMA_STATUS=PASS
COHORT_CHECK_RUN_ID=cohort-check-20260806T140259+0800
COHORT_CHECK_STATUS=PASS
```

Real-data cohort-check results:

```text
PRIMARY_7D_RETAINED_JOURNEYS=240981
PRIMARY_7D_RETAINED_UIDS=183533
PRIMARY_7D_ELIGIBLE_CELLS=19307
PRIMARY_7D_AMBIGUITY_RATE=0.19856337221606682
LONG_30D_RETAINED_JOURNEYS=11392
LONG_30D_RETAINED_UIDS=10971
LONG_30D_ELIGIBLE_CELLS=19307
LONG_30D_AMBIGUITY_RATE=0.31337780898876405
TEMPORAL_COVERAGE_STATUS=PASS
FULL_EXP2_RERUN_ALLOWED=YES
```

## Refactor Metrics

Pre-refactor top-level line counts were recorded as: bootstrap 502, cohort 239, data IO 437, metrics 494, reporting 590, routes 364, runner 446, targeted 311, and validation 407.

After migration, each corresponding top-level compatibility facade is 3-4 lines. Core implementation line counts are:

| Core implementation | Lines |
|---|---:|
| `exp2_core/reporting/implementation.py` | 657 |
| `exp2_core/pipeline/run.py` | 605 |
| `exp2_core/metrics/implementation.py` | 530 |
| `exp2_core/resampling/uid_bootstrap.py` | 510 |
| `exp2_core/raw_data.py` | 453 |
| `exp2_core/robustness/orchestrator.py` | 430 |
| `exp2_core/validation/implementation.py` | 433 |
| `exp2_core/routes/implementation.py` | 371 |
| `exp2_core/cohort.py` | 314 |

The files above 300 lines remain single-source implementation modules because this pass prioritized schema migration and end-to-end reproducibility without introducing a second scientific implementation. Package ownership is separated, top-level duplication is removed, and later mechanical subdivision can occur within `exp2_core` without changing public imports.

```text
MAXIMUM_IMPLEMENTATION_FILE_LINES=657
DUPLICATE_SCIENTIFIC_IMPLEMENTATION=NO
```

## Scientific Gates

```text
COMMON_COHORT_STATUS=PASS
SINGLE_CAMPAIGN_STATUS=PASS
COMPLETE_LOOKBACK_STATUS=PASS
CREDIT_CONSERVATION_STATUS=PASS
SINGLE_CELL_INVARIANT_STATUS=PASS
KENDALL_SUPPORT_STATUS=PASS
NO_CI_TERMINOLOGY_STATUS=PASS
NO_OUT_OF_SCOPE_TERMS_STATUS=PASS
FIGURE_SOURCE_STATUS=PASS
PROMOTION_SCHEMA_STATUS=PASS
```

The latest fast output contains the unified attribution-sensitivity source CSV, ambiguity-mechanism source CSV, PDF/SVG/PNG figures, cohort-flow and primary tables, robustness summary, route invariants, resampling audit, scientific validation, and artifact manifest.

## Rerun Scope

```text
FULL_EXP2_RERUN_REQUIRED=YES
GLOBAL_RERUN_REQUIRED=NO
EXP1_RERUN_REQUIRED=NO
EXP3_RERUN_REQUIRED=NO
EXP4_RERUN_REQUIRED=NO
```

## Next Step

```text
NEXT_ALLOWED_STEP=RUN_FORMAL_EXP2_FULL
```

The formal full run was not started.
