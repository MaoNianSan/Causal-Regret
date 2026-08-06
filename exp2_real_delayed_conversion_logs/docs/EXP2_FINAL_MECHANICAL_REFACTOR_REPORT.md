# Exp2 Final Mechanical Refactor Report

Status date: 2026-08-06

## Objective

Complete the final mechanical subdivision of Exp2 v2 so that long implementation
files and orchestration chains are easier to maintain while preserving the frozen
scientific design and every external contract.

```text
SCIENTIFIC_BEHAVIOR_CHANGE=NO
CONFIG_CHANGE=NO
OUTPUT_SCHEMA_CHANGE=NO
RANDOM_SEED_CHANGE=NO
CLI_CHANGE=NO
```

## Frozen Design

The schema version remains `exp2_attribution_sensitivity_v2`. The 7-day primary
candidate window, 30-day long-window robustness, campaign-day decision cells,
50-impression primary threshold, threshold robustness values, Top-k values,
time-decay half-lives, UID resampling contract, common cohort, decision-cell
universe, impression denominator, Kendall support, route order, seeds, and
deterministic ordering were not changed.

The five formal route IDs remain:

- `arrival_time_accounting_anchor`
- `first_click_or_touch`
- `last_click_or_touch`
- `linear_source_cell_credit`
- `time_decay_source_cell_credit`

`em_soft_credit` remains exploratory and disabled by default.

## Structure Before And After

Before this pass, the main implementations were concentrated in eight files from
371 to 657 lines. They are now thin coordinators or compatibility aggregators:

| File | Lines before | Lines after |
|---|---:|---:|
| `exp2_core/reporting/implementation.py` | 657 | 12 |
| `exp2_core/pipeline/run.py` | 605 | 71 |
| `exp2_core/metrics/implementation.py` | 530 | 19 |
| `exp2_core/resampling/uid_bootstrap.py` | 510 | 125 |
| `exp2_core/raw_data.py` | 453 | 65 |
| `exp2_core/validation/implementation.py` | 433 | 93 |
| `exp2_core/robustness/orchestrator.py` | 430 | 76 |
| `exp2_core/routes/implementation.py` | 371 | 90 |

The maximum core file is `exp2_core/cohort.py` at 314 lines. It remains intact
because its manifest construction, exclusion precedence, frozen universe, and
cohort-flow assembly form one cohesive route-independent contract. It is below
the 350-line hard limit. The next-largest core file is `data/ingestion.py` at 282
lines.

## Module Responsibilities

- `reporting/`: main figure, ambiguity figure, appendix figures, source data,
  tables, plotting style, and artifact metadata are separated. Figure labels,
  source schemas, ordering, filenames, and output formats are unchanged.
- `pipeline/`: input, cohort, route, metric, resampling, reporting, validation,
  artifact finalization, and cohort-check stages return explicit objects. `run.py`
  only preserves stage order and failure handling.
- `metrics/`: allocation, ranking, ambiguity, and aggregation own one copy of each
  formula. `implementation.py` only exports the public API.
- `resampling/`: deterministic seeds and sparse state, replicate metrics,
  summaries, audit logic, and orchestration are separated. Seed spawning,
  replicate order, route-pair order, and frozen support are unchanged.
- `data/`: ingestion, time normalization, candidate finalization, temporal audit,
  models, and I/O are separated. `raw_data.py` remains the public entry point.
- `robustness/`: candidate window, support threshold, ranking depth, and decay
  half-life analyses remain independent and are merged in the original order.
- `validation/`: frozen configuration, scientific invariants, artifact and
  resampling checks, and terminology checks are separated without removing a gate.
- `routes/`: primary assignments, exploratory/reference assignments, metadata,
  and credit validation are separated. The route coordinator is 90 lines.

## Public Compatibility

The top-level `cohort.py`, `data_io.py`, `routes.py`, `metrics.py`, `bootstrap.py`,
`targeted.py`, `reporting.py`, `validation.py`, and `runner.py` facades still
import successfully. Existing public `exp2_core` symbols remain available.

The CLI continues to expose exactly `fast`, `full`, and `cohort-check`, with the
same `--config`, `--input`, `--n-bootstrap`, and `--n-jobs` options. Importing all
modules through `pkgutil.walk_packages` succeeds without a circular-import error.

```text
PUBLIC_IMPORT_STATUS=PASS
EXP2_PUBLIC_API_CHANGED=NO
CLI_CHANGE=NO
```

## Behavior Equivalence

Baseline Fast artifact:

```text
exp2-fast-20260806T142102+0800
```

Post-refactor Fast artifact:

```text
exp2-fast-20260806T161319+0800
```

The comparison covered 19 scientific CSV artifacts and six JSON contracts. It
checked exact schemas and row order, canonical-key sorted values, retained journey
IDs, retained UID sets, decision-cell universe, route assignments, allocation
vectors, route credit totals, point metrics, ambiguity metrics, targeted
robustness, figure source data, paper tables, route invariants, scientific
validation, manifest scientific fields, and bootstrap draws.

All compared scientific hashes matched after normalizing only run IDs and other
explicitly volatile metadata. Numeric comparison used `rtol=0` and `atol=1e-12`.

```text
FAST_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
RANDOM_DRAW_EQUIVALENCE_STATUS=PASS
EXP2_SCIENTIFIC_BEHAVIOR_CHANGED=NO
EXP2_RANDOM_STREAM_CHANGED=NO
EXP2_OUTPUT_SCHEMA_CHANGED=NO
```

The ignored comparison report is stored at:

```text
outputs/refactor_audit/fast_equivalence_exp2-fast-20260806T161319+0800.json
```

## Tests And Runs

```text
COMPILEALL_STATUS=PASS
TEST_COUNT=21
TEST_STATUS=PASS
FAST_RUN_ID=exp2-fast-20260806T161319+0800
FAST_STATUS=PASS
COHORT_CHECK_RUN_ID=cohort-check-20260806T161359+0800
COHORT_CHECK_STATUS=PASS
GIT_DIFF_CHECK_STATUS=PASS
```

The tests include compatibility facade imports, all current public symbols, CLI
command names, full module import traversal, maximum file length, duplicate
scientific implementation detection, and legacy identifier detection.

## Real-Data Cohort Gate

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
```

## Scientific And Structural Gates

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
PUBLIC_IMPORT_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
DUPLICATE_IMPLEMENTATION_STATUS=PASS
MAX_FILE_LENGTH_STATUS=PASS
RANDOM_DRAW_EQUIVALENCE_STATUS=PASS
```

The old 2026-07-27 paper output remains untouched and was not used as the v2
behavior baseline.

## Repository Side Effects

This run did not invoke `git commit`, `git push`, create a branch, or modify a
remote. During the long real-data cohort-check, an external concurrent process
advanced `main` to commit `55e4177876a1d90dcf196a15b2898973ef98c93e`
(`exp2v3`) containing the Exp2 code changes. This report records that event; no
reset or history rewrite was attempted. Concurrent Exp3 and Exp4 workspace
changes were left untouched.

## Final Status

```text
EXP2_V2_DESIGN_CHANGED=NO
EXP2_CONFIG_CHANGED=NO
EXP2_SCIENTIFIC_BEHAVIOR_CHANGED=NO
EXP2_OUTPUT_SCHEMA_CHANGED=NO
EXP2_PUBLIC_API_CHANGED=NO
EXP2_RANDOM_STREAM_CHANGED=NO

COMPILEALL_STATUS=PASS
TEST_STATUS=PASS
FAST_STATUS=PASS
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
COHORT_CHECK_STATUS=PASS
TEMPORAL_COVERAGE_STATUS=PASS
PUBLIC_IMPORT_STATUS=PASS
DUPLICATE_IMPLEMENTATION_STATUS=PASS
MAX_FILE_LENGTH_STATUS=PASS
GIT_DIFF_CHECK_STATUS=PASS

FORMAL_EXP2_FULL_STARTED=NO
FORMAL_EXP2_FULL_ALLOWED=YES

FULL_EXP2_RERUN_REQUIRED=YES
GLOBAL_RERUN_REQUIRED=NO
EXP1_RERUN_REQUIRED=NO
EXP3_RERUN_REQUIRED=NO
EXP4_RERUN_REQUIRED=NO

NEXT_ALLOWED_COMMAND=python exp2_real_delayed_conversion_logs/main.py full
```

Formal Exp2 Full was not started.

## Exp2 V3 Final Fix Validation

### Scope And Hard Boundaries

This final pass was limited to `exp2_real_delayed_conversion_logs/`. It did not
modify Exp1, Exp3, Exp4, raw data, LaTeX/PDF sources, or old paper outputs. It did
not run formal Full and did not perform a Git commit, push, branch creation,
checkout, reset, or remote operation.

The Exp2 V3 base remains commit `55e4177876a1d90dcf196a15b2898973ef98c93e`
(`exp2v3`). While the real-data check was running, an external concurrent process
advanced repository `main` and `origin/main` to
`7e1a8ffa58e298930abe2efc3dce61aa226366dd` for an Exp4-only commit. A tree diff
confirmed that the committed Exp2 directory is unchanged between those commits;
no history rewrite was attempted.

### Pre-Fix Audit

The audit found four remaining V3 issues:

1. Fast candidate-window status incorrectly used the primary value `7` for an
   unrun robustness setting.
2. Cohort flow and primary exclusion reasons used different filter orders, and
   the flow omitted the unique-arrival-anchor stage.
3. `temporally_valid_journeys` was backed only by unconditional
   `is_temporally_valid=True`.
4. Twenty imports inside `exp2_core` still routed through top-level compatibility
   facades.

The pre-fix Fast artifact `exp2-fast-20260806T161319+0800` was copied to the
ignored audit directory before editing. The pre-fix engineering baseline was
`21 passed`.

### Candidate-Window Fast Status

Fast status is now configuration-derived. For the frozen configuration, the
primary/reference window remains `7` days and the unrun alternative is `30` days:

```text
targeted_dimension=candidate_window_days
targeted_value=30
analysis_status=NOT_RUN_IN_FAST
```

No column was added to `targeted_robustness.csv`, and Full-mode 7-day versus
30-day computation was not changed.

### Cohort Stage Single Source Of Truth

`exp2_core/cohort_stages.py` now owns one ordered `COHORT_STAGE_SPEC`. Each stage
declares its stage ID, display name, predicate column, exclusion reason, and
execution order. That specification drives:

- cumulative cohort flow;
- first-failure primary exclusion reason;
- ordered all-exclusion reasons;
- exclusion summary;
- final retained mask.

The frozen order is complete lookback, unique UID, single campaign, source-cell
support, unique arrival anchor, and arrival-anchor support. The first failed
predicate is the journey's only primary exclusion reason.

The new reconciliation gate verifies monotone retained counts, per-stage
attrition, exclusion-reason totals, candidate-to-final accounting, and exact
equality between the final retained mask and the conjunction of stage predicates.
It is recorded as `cohort_flow_exclusion_reconciliation=PASS` in Fast scientific
validation.

### Temporal Validity: Scheme B

Raw ingestion applies temporal eligibility before candidates reach `cohort.py`:
valid event and conversion timestamps, nonnegative lag, lag within the maximum
configured candidate window, and conversion no later than the observed exposure
boundary. Temporal-invalid journeys are therefore not recoverable from the
cohort input without redesigning raw ingestion, which this task prohibited.

Scheme B was applied. The fake `temporally_valid_journeys` row and unconditional
`is_temporally_valid` manifest field were removed. Cohort flow now begins with
`candidate_journeys_after_temporal_filters`. Temporal coverage and upstream
exclusion evidence remain independently reported in `temporal_coverage.csv` and
`raw_input_audit.json`. The real-data audit records 806,196 conversion candidates
before timing and 623,402 candidate rows after temporal filtering and exact
deduplication.

### Internal Imports And Public Compatibility

All package-internal imports from `cohort`, `data_io`, `metrics`, and `routes`
facades were changed to package-relative imports. An AST structure test scans all
64 `exp2_core` Python files and rejects future reverse imports through any of the
nine top-level compatibility modules.

The top-level facades remain unchanged and import successfully. Their expected
public symbols, all `exp2_core` modules, and the CLI parser import without a cycle.
The CLI still exposes only `fast`, `full`, and `cohort-check` with the existing
options.

### File-Length And Duplicate-Implementation Audit

There are 64 production Python files under `exp2_core`. The largest is now
`data/ingestion.py` at 282 lines; `cohort.py` is 258 lines and the new
`cohort_stages.py` is 216 lines. Every production file remains below the 350-line
hard limit. The AST duplicate-implementation test and legacy-identifier scan pass.

### Tests And Fast Run

```text
COMPILEALL_STATUS=PASS
TEST_COUNT=26
TEST_STATUS=PASS
IMPORT_CONTRACT_TEST_COUNT=3
STRUCTURE_CONTRACT_TEST_COUNT=4
FAST_RUN_ID=exp2-fast-20260806T165222+0800
FAST_STATUS=PASS
SCIENTIFIC_VALIDATION_STATUS=PASS
COHORT_FLOW_RECONCILIATION_STATUS=PASS
```

The final Fast run retained 810 journeys, 378 UIDs, and 320 eligible cells and
completed all 200 UID-resampling repetitions.

### Fast Behavior Equivalence

Baseline: `exp2-fast-20260806T161319+0800`

Candidate: `exp2-fast-20260806T165222+0800`

The comparison covered 20 CSV artifacts and six JSON contracts. With `rtol=0`
and `atol=1e-12`, retained journey IDs, retained UID sets, eligible cells, route
assignments, credit totals, allocation vectors, allocation TV, Kendall tau-b,
Top-k overlap and disagreement, ambiguity-stratified metrics, figure sources,
table values, route/scientific validations, and all bootstrap draws were equal.

The only allowed differences were the corrected candidate-window status, unified
cohort-flow/exclusion presentation, removal of the synthetic temporal audit flag,
import metadata, and the new reconciliation validation fields.

```text
FAST_BEHAVIOR_EQUIVALENCE_STATUS=PASS
RANDOM_DRAW_EQUIVALENCE_STATUS=PASS
EXP2_SCIENTIFIC_BEHAVIOR_CHANGED=NO
EXP2_RANDOM_STREAM_CHANGED=NO
```

The ignored report is
`outputs/refactor_audit/final_fix_fast_equivalence_exp2-fast-20260806T165222+0800.json`.

### Real-Data Cohort Check

The current CLI contract was used:

```text
python exp2_real_delayed_conversion_logs/main.py cohort-check
```

Run ID: `cohort-check-20260806T165255+0800`

Duration: 707.8 seconds

```text
PRIMARY_7D_RETAINED_JOURNEYS=240981
PRIMARY_7D_RETAINED_UIDS=183533
PRIMARY_7D_ELIGIBLE_CELLS=19307
PRIMARY_7D_AMBIGUITY_RATE=0.19856337221606682

LONG_30D_RETAINED_JOURNEYS=11392
LONG_30D_RETAINED_UIDS=10971
LONG_30D_ELIGIBLE_CELLS=19307
LONG_30D_AMBIGUITY_RATE=0.31337780898876405

COHORT_CHECK_STATUS=PASS
TEMPORAL_COVERAGE_STATUS=PASS
```

All frozen values matched exactly. No expected value, configuration value, or
tolerance was changed.

### Scientific, Terminology, And Artifact Gates

Common cohort, single campaign, complete lookback, unique UID, credit
conservation, single-cell behavior, allocation normalization, frozen denominator,
frozen Kendall support, route totals, Top-k disagreement identity, terminology,
figure-source schema, table schema, manifest/promotion schema, public imports,
internal import direction, duplicate implementation, and maximum file length all
pass. `git diff --check` also passes.

The frozen scientific design, configuration, route definitions, metric
definitions, random stream, CLI, public API, formal scientific schemas, filenames,
and output-directory contract are unchanged. Scheme B removes only the explicitly
invalid `is_temporally_valid` audit column; all remaining journey-manifest columns
retain their prior ordering and values.

### Formal Full Status And Next Command

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
