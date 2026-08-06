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

## Final mechanical subdivision

Status date: 2026-08-06

The final mechanical subdivision moved the long `exp2_core` implementations into
single-responsibility modules without changing the frozen v2 configuration,
scientific formulas, route order, random stream, output schemas, filenames, or CLI.
The compatibility facades and existing public symbols remain available.

Key implementation sizes after subdivision:

| Core implementation | Before | After coordinator/facade |
|---|---:|---:|
| `reporting/implementation.py` | 657 | 12 |
| `pipeline/run.py` | 605 | 71 |
| `metrics/implementation.py` | 530 | 19 |
| `resampling/uid_bootstrap.py` | 510 | 125 |
| `raw_data.py` | 453 | 65 |
| `validation/implementation.py` | 433 | 93 |
| `robustness/orchestrator.py` | 430 | 76 |
| `routes/implementation.py` | 371 | 90 |

The maximum core Python file is `exp2_core/cohort.py` at 314 lines. It remains a
single cohesive cohort builder and is below the 350-line hard limit. Every other
core Python file is at most 282 lines.

```text
COMPILEALL_STATUS=PASS
TEST_COUNT=21
TEST_STATUS=PASS
FAST_RUN_ID=exp2-fast-20260806T161319+0800
FAST_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
RANDOM_DRAW_EQUIVALENCE_STATUS=PASS
COHORT_CHECK_RUN_ID=cohort-check-20260806T161359+0800
COHORT_CHECK_STATUS=PASS
TEMPORAL_COVERAGE_STATUS=PASS
PUBLIC_IMPORT_STATUS=PASS
DUPLICATE_IMPLEMENTATION_STATUS=PASS
MAX_FILE_LENGTH_STATUS=PASS
GIT_DIFF_CHECK_STATUS=PASS
```

The Fast comparison used `exp2-fast-20260806T142102+0800` as the pre-refactor
baseline. Nineteen scientific CSV artifacts and six scientific JSON artifacts
matched in schema, row order, canonical values, and frozen scientific fields.
Retained journey IDs, retained UID sets, route credit totals, and all 200 bootstrap
replicates also matched. Numeric comparison used `rtol=0` and `atol=1e-12`.

Real-data cohort-check results remained exactly frozen:

```text
PRIMARY_7D_RETAINED_JOURNEYS=240981
PRIMARY_7D_RETAINED_UIDS=183533
PRIMARY_7D_ELIGIBLE_CELLS=19307
PRIMARY_7D_AMBIGUITY_RATE=0.19856337221606682
LONG_30D_RETAINED_JOURNEYS=11392
LONG_30D_RETAINED_UIDS=10971
LONG_30D_ELIGIBLE_CELLS=19307
LONG_30D_AMBIGUITY_RATE=0.31337780898876405
```

```text
EXP2_V2_DESIGN_CHANGED=NO
EXP2_CONFIG_CHANGED=NO
EXP2_SCIENTIFIC_BEHAVIOR_CHANGED=NO
EXP2_OUTPUT_SCHEMA_CHANGED=NO
EXP2_PUBLIC_API_CHANGED=NO
EXP2_RANDOM_STREAM_CHANGED=NO
FORMAL_EXP2_FULL_STARTED=NO
FORMAL_EXP2_FULL_ALLOWED=YES
FULL_EXP2_RERUN_REQUIRED=YES
GLOBAL_RERUN_REQUIRED=NO
EXP1_RERUN_REQUIRED=NO
EXP3_RERUN_REQUIRED=NO
EXP4_RERUN_REQUIRED=NO
NEXT_ALLOWED_COMMAND=python exp2_real_delayed_conversion_logs/main.py full
```

No formal Full was started by this validation pass.

## Exp2 V3 final validation

Status date: 2026-08-06

Exp2 V3 base commit: `55e4177876a1d90dcf196a15b2898973ef98c93e`
(`exp2v3`). During the real-data cohort check, an external concurrent process
advanced repository `main` and `origin/main` to `7e1a8ffa58e298930abe2efc3dce61aa226366dd`
for an Exp4-only commit. The committed Exp2 tree is identical between those two
commits. This task did not run a Git commit, push, branch, reset, checkout, or
remote operation.

The final V3 pass made four scoped corrections:

- Fast `candidate_window_days` status now names `30` as the unrun robustness
  alternative. The frozen primary/reference window remains `7`.
- `COHORT_STAGE_SPEC` is the only source for stage order, primary exclusion
  reason, all exclusion reasons, exclusion summary, cumulative flow, and final
  retained mask. A reconciliation gate checks monotonicity, stage attrition,
  reason totals, and final-mask equality.
- Temporal filtering uses Scheme B. Raw ingestion already removes invalid
  timestamps, negative lags, over-window lags, and conversions beyond the
  observed exposure boundary before `cohort.py`. The false
  `temporally_valid_journeys` stage and unconditional `is_temporally_valid=True`
  field were removed. Cohort flow begins with
  `candidate_journeys_after_temporal_filters`; temporal evidence remains in
  `temporal_coverage.csv` and `raw_input_audit.json`.
- All `exp2_core` imports through top-level compatibility facades were replaced
  by package-relative imports. The top-level facades and their public symbols
  remain available.

The frozen scientific design, configuration, formal route IDs, metric formulas,
random seeds, deterministic ordering, CLI, filenames, formal scientific schemas,
figure/table schemas, promotion schema, and output-directory contract did not
change. The requested Scheme-B cleanup removes only the synthetic audit flag
`is_temporally_valid` from `journey_manifest`; all remaining manifest columns keep
their prior order and values.

Current validation evidence:

```text
COMMIT_REFERENCE=55e4177 exp2v3
CURRENT_REPOSITORY_HEAD=7e1a8ff exp4 provenance + lineage + formal-full-ready
MAX_CORE_PYTHON_FILE=exp2_core/data/ingestion.py
MAX_CORE_PYTHON_LINES=282
COMPILEALL_STATUS=PASS
TEST_COUNT=26
TEST_STATUS=PASS
IMPORT_CONTRACT_TEST_COUNT=3
STRUCTURE_CONTRACT_TEST_COUNT=4
FAST_RUN_ID=exp2-fast-20260806T165222+0800
FAST_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
FAST_EQUIVALENCE_CSV_COUNT=20
FAST_EQUIVALENCE_JSON_COUNT=6
RANDOM_DRAW_EQUIVALENCE_STATUS=PASS
COHORT_CHECK_RUN_ID=cohort-check-20260806T165255+0800
COHORT_CHECK_DURATION_SECONDS=707.8
COHORT_CHECK_STATUS=PASS
TEMPORAL_COVERAGE_STATUS=PASS
PUBLIC_IMPORT_STATUS=PASS
INTERNAL_IMPORT_CONTRACT_STATUS=PASS
COHORT_FLOW_RECONCILIATION_STATUS=PASS
DUPLICATE_IMPLEMENTATION_STATUS=PASS
MAX_FILE_LENGTH_STATUS=PASS
SCIENTIFIC_VALIDATION_STATUS=PASS
TERMINOLOGY_STATUS=PASS
ARTIFACT_SCHEMA_STATUS=PASS
GIT_DIFF_CHECK_STATUS=PASS
```

Fast comparison used the ignored pre-fix copy of
`exp2-fast-20260806T161319+0800` as baseline and
`exp2-fast-20260806T165222+0800` as candidate. With `rtol=0` and
`atol=1e-12`, retained journey IDs, retained UID sets, decision cells, route
assignments, route credit totals, allocation vectors, allocation TV, Kendall
tau-b, Top-k overlap/disagreement, ambiguity metrics, figure sources, table
values, scientific validation, and all 200 bootstrap draws were equivalent.
Only the explicitly permitted candidate-window status, cohort-flow/exclusion
presentation, Scheme-B audit-flag removal, import metadata, and added validation
fields differed.

Real-data cohort values remain frozen:

```text
PRIMARY_7D_RETAINED_JOURNEYS=240981
PRIMARY_7D_RETAINED_UIDS=183533
PRIMARY_7D_ELIGIBLE_CELLS=19307
PRIMARY_7D_AMBIGUITY_RATE=0.19856337221606682
LONG_30D_RETAINED_JOURNEYS=11392
LONG_30D_RETAINED_UIDS=10971
LONG_30D_ELIGIBLE_CELLS=19307
LONG_30D_AMBIGUITY_RATE=0.31337780898876405
```

```text
EXP2_V3_FINAL_FIX_COMPLETE=YES

EXP2_SCIENTIFIC_DESIGN_CHANGED=NO
EXP2_CONFIG_CHANGED=NO
EXP2_ROUTE_DEFINITION_CHANGED=NO
EXP2_METRIC_DEFINITION_CHANGED=NO
EXP2_RANDOM_STREAM_CHANGED=NO
EXP2_OUTPUT_SCHEMA_CHANGED=NO
EXP2_CLI_CHANGED=NO
EXP2_PUBLIC_API_CHANGED=NO

FAST_CANDIDATE_WINDOW_STATUS_FIXED=YES
COHORT_STAGE_ORDER_UNIFIED=YES
TEMPORAL_VALIDITY_STAGE_FIXED=YES
INTERNAL_IMPORT_DIRECTION_FIXED=YES
DOCUMENTATION_UPDATED=YES

COMPILEALL_STATUS=PASS
TEST_STATUS=PASS
FAST_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
COHORT_CHECK_STATUS=PASS
TEMPORAL_COVERAGE_STATUS=PASS
PUBLIC_IMPORT_STATUS=PASS
INTERNAL_IMPORT_CONTRACT_STATUS=PASS
COHORT_FLOW_RECONCILIATION_STATUS=PASS
DUPLICATE_IMPLEMENTATION_STATUS=PASS
MAX_FILE_LENGTH_STATUS=PASS
SCIENTIFIC_VALIDATION_STATUS=PASS
TERMINOLOGY_STATUS=PASS
ARTIFACT_SCHEMA_STATUS=PASS
GIT_DIFF_CHECK_STATUS=PASS

FORMAL_EXP2_FULL_STARTED=NO

FULL_EXP2_RERUN_REQUIRED=YES
GLOBAL_RERUN_REQUIRED=NO
EXP1_RERUN_REQUIRED=NO
EXP3_RERUN_REQUIRED=NO
EXP4_RERUN_REQUIRED=NO

FORMAL_EXP2_FULL_ALLOWED=YES
NEXT_ALLOWED_COMMAND=python exp2_real_delayed_conversion_logs/main.py full
```

Formal Exp2 Full was not started.
