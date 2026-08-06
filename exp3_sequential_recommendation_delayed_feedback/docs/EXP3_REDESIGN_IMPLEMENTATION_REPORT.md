# Exp3 Redesign Implementation Report

Report date: 2026-08-06 (Asia/Hong_Kong)

## A. Summary

```text
IMPLEMENTATION_STATUS=PASS
SCIENTIFIC_CONTRACT_STATUS=PASS
ENGINEERING_STATUS=PASS
FAST_STATUS=PASS
FULL_RUN_EXECUTED=NO
```

The redesign and contract-completion work is confined to
`exp3_sequential_recommendation_delayed_feedback`. Exp1, Exp2, Exp4, paper
sources, raw KuaiRand inputs, promoted historical outputs, and other project
directories were not modified.

The final real-fast run records source-tree hash
`79c8bf6d6d1b6c2a453bef981f949d8ca097bc58505f99940f421b35b561d1b3`,
which exactly matches the final active source tree.

## B. Files changed

Line counts below compare the repository state at the start of this
contract-completion pass with the final state. Scientific effects describe
whether a file can change an estimand, route fit, schema, or only validation and
presentation.

| File | Lines | Responsibility change | Scientific/schema effect |
|---|---:|---|---|
| `README.md` | 116 -> 156 | Updated executable design and output documentation | Canonical scope and history-common-support CV disclosure |
| `design_contract.py` | 260 -> 291 | Added canonical support metric registration | Emits deprecated `pair_coverage` alias row |
| `docs/EXP3_PRE_MODIFICATION_AUDIT.md` | 58 -> 122 | Added current-head audit before completion edits | Records discovered contract gaps and boundaries |
| `docs/EXP3_SCHEMA_MIGRATION.md` | 90 -> 136 | Extended migration contract | Documents CV support, refit, alias, and target-audit schema |
| `evaluate_recoverability.py` | 199 -> 220 | Kept two-fold orchestration and removed zero-count division warnings | No estimand change beyond the already-required selection-fold fix |
| `plot_appendix_diagnostics.py` | 98 -> 104 | Uses centralized route display metadata | Removes duplicate route naming |
| `plot_appendix_results.py` | 288 -> 187 | Reduced to appendix orchestration | Frozen-table interface unchanged |
| `plot_appendix_support.py` | new -> 162 | Owns full-design support preparation and drawing | Appendix-only, no model fitting or action selection |
| `plot_contract.py` | 128 -> 174 | Centralizes main-figure metric sets and registry validation | Rejects missing/deprecated main metric contracts |
| `plot_score_panel.py` | 28 -> 32 | Uses centralized score metric IDs | Canonical figure naming |
| `plot_gap_panel.py` | 29 -> 33 | Uses centralized gap metric IDs | Canonical figure naming |
| `plot_ranking_panel.py` | 49 -> 53 | Uses centralized ranking metric IDs | Paired gain remains the main ranking contrast |
| `ridge_features.py` | 138 -> 188 | Marks history common-supported cells from both reference folds | CV validation scope now matches the scientific contract |
| `ridge_selection.py` | 129 -> 152 | Filters validation cells to history common support | Can change selected alpha; evaluation remains rejected |
| `route_fitting.py` | 107 -> 131 | Adds explicit full-history final refit contract | Persists refit scope and cell count |
| `run_reporting.py` | 238 -> 280 | Uses centralized route display name | Reporting-only naming correction |
| `self_check_common.py` | new -> 50 | Shared JSON/check/frame comparison primitives | Removes duplicated self-check logic |
| `self_check_contracts.py` | 189 -> 223 | Checks support alias registry and route/support schemas separately | Strengthens independent scientific and engineering gates |
| `self_check_figure_helpers.py` | new -> 146 | Reconstructs appendix figure sources and hashes | Frozen-table-only figure validation |
| `self_check_helpers.py` | 297 -> 185 | Retains non-figure reconstruction helpers and compatibility imports | No estimand change; hard line gate repaired |
| `self_check_redesign.py` | 189 -> 200 | Verifies CV support counts and full-history refit manifest | Independently gates the new Ridge contract |
| `target_audit.py` | 104 -> 187 | Reconstructs component totals inside each six-hour window | Audit schema corrected without changing targets |
| `tests/test_exp3_redesign_contracts.py` | 176 -> 280 | Adds CV support, full refit, positive paired gain, alias, and target-window audits | Old or incomplete implementations fail |
| `tests/test_final_repair_contracts.py` | 116 -> 131 | Updates canonical panel title contract | Presentation contract only |
| `tests/test_main_figure_redesign_contracts.py` | new -> 186 | Adds six required frozen-table/canonical figure tests | Figure/table synchronization gate |
| `tests/test_resampling_redesign_contracts.py` | new -> 163 | Adds no-refit and support/action reconstruction tests | Resampling estimand contract |
| `tests/test_target_and_figure_contracts.py` | 311 -> 275 | Moved unrelated resampling coverage into a focused test module | Hard 300-line gate repaired |

All active Python files are below 300 lines. The largest is
`bootstrap_summary.py` at 296 lines. The 220-line evaluation orchestrator and
291-line declarative metric registry remain below the hard gate; their remaining
size is disclosed rather than hidden through compressed statements.

## C. Scientific changes

### Two-fold contract

- Reference and route actions use the selection fold.
- Route reference-pair gaps use selection-fold route scores.
- Target values and target gaps use the opposite evaluation fold.
- Toy tests force fold-specific route argmax disagreement and fail under the old implementation.

### Ridge selection

- Source config contains only the frozen alpha grid, not a selected alpha.
- Rolling origins use strictly earlier history days for fitting.
- Validation metrics use only history common-supported action cells.
- Values within `1e-4` use the larger alpha.
- Evaluation frames are rejected by the selector.
- Final Ridge fitting uses all available history training cells after selection.

### Metrics, support, target, and figures

- Canonical score, reference-pair gap, ranking, and paired-gain fields are authoritative.
- `pair_coverage` is an explicit deprecated alias of `reference_pair_coverage`.
- Route metadata contains no deployment-value claim.
- The target audit reconstructs component windows, required quantiles, zero rates,
  weighted contributions, right censoring, and the LongView shared-component disclosure.
- The main figure reads frozen tables only and reproduces the canonical primary tables.
- User resampling rebuilds support and selected actions without refitting Ridge.

## D. Tests

```text
python -m compileall .                         PASS
pytest -q                                      PASS (57 passed)
git diff --check                               PASS
```

Synthetic fixture:

```text
FIXTURE_RUN_ID=exp3-fixture-20260806T104135Z
PIPELINE_EXECUTION_STATUS=PASS
INDEPENDENT_SELF_CHECK_STATUS=PASS
PAPER_RESULT=false
SELECTED_RIDGE_ALPHA=0.3
```

Real-data fast:

```text
REAL_FAST_RUN_ID=exp3-fast-20260806T104232Z
PIPELINE_EXECUTION_STATUS=PASS
INDEPENDENT_SELF_CHECK_STATUS=PASS
FINAL_ENGINEERING_STATUS=PASS
SCIENTIFIC_CONTRACT_STATUS=PASS
PAPER_RESULT=false
SELECTED_RIDGE_ALPHA=30.0
SOURCE_TREE_HASH_MATCH=true
```

The real-fast self-check contains 50 passing checks: 32 scientific, 17
engineering, and one paper-boundary check. Two earlier harness-interrupted run
directories remain incomplete and were neither resumed nor used as evidence.

## E. Output contract

Added or strengthened:

```text
tables/exp3_metric_registry.csv
tables/exp3_ridge_history_cv.csv
metadata/exp3_ridge_selection_manifest.json
metadata/exp3_model_manifest.json
tables/exp3_target_component_audit.csv
tables/exp3_gap_error_distribution.csv
tables/exp3_paired_ranking_contrast.csv
diagnostics/exp3_route_selection_diagnostics.csv
figures/data/exp3_main_score_gap_ranking_data.csv
figures/metadata/exp3_main_score_gap_ranking_metadata.json
```

Compatibility aliases remain for one release and are marked deprecated. Old
evaluation arrays, bootstrap chunks, metric registries, or selected-alpha state
cannot be resumed under the redesigned source and schema hashes.

## F. Result changes

Real fast is an engineering/interface result, not a paper result.

| Route | Spearman | MAE | Maximum gap error | Sign agreement | Signed reference-minus-route value | Top-action agreement |
|---|---:|---:|---:|---:|---:|---:|
| Arrival carrier—misbinding control | 0.6920 | 0.1022 | 0.3468 | 0.8654 | 0.0098 | 0.7059 |
| Historical mean | 0.7667 | 0.0856 | 0.2342 | 0.9391 | -0.0398 | 0.8382 |
| Ridge proxy | 0.7190 | 0.0855 | 0.2292 | 0.9373 | -0.0398 | 0.8382 |

- The selected real-fast alpha is `30.0`; seven supported rolling origins were evaluated.
- `ridge_over_historical_paired_value_gain=0.0`; its fast sensitivity range is `[0.0, 0.0]`.
- Active top-6 fast support is complete: action, reference-pair, and audit-unit coverage are `1.0`.
- Formal top-20 preflight is `READY`: action coverage `0.9247`, reference-pair coverage
  `0.9207`, and audit-unit coverage `1.0`.
- This completion pass did not change the primary fast point estimates relative to the
  earlier redesign fast run; it corrected CV support, target-audit, registry, tests,
  structure, and provenance contracts.
- The original pre-redesign Exp3 result remains scientifically changed by the two-fold
  estimand fix, history-only alpha selection, canonical schema, paired contrast,
  resampling summary, and main figure redesign.

## G. Rerun decision

```text
NEXT_ALLOWED_STEP=HUMAN_REVIEW_THEN_NEW_EXP3_FULL_RUN
EXP1_RERUN_REQUIRED=NO
EXP2_RERUN_REQUIRED=NO
EXP3_FULL_RERUN_REQUIRED=YES
EXP4_RERUN_REQUIRED=NO
OTHER_EXPERIMENT_RERUN_REQUIRED=NO
GLOBAL_ALL_EXPERIMENT_RERUN_REQUIRED=NO
```

The old Exp3 full lineage is legacy and cannot be promoted under the redesigned
contract. A formal full must use a new immutable run ID and must not mix old point
estimates, bootstrap chunks, figure tables, or selected-alpha state.

## H. Commands for the user

After human review, the next permitted commands are:

```bash
python main.py full --n-jobs <N>
python main.py self-check --mode full --run-id <new_full_run_id>
```

Promotion and archive remain separate explicit gates after a new full run and
independent full self-check pass. They were not executed here.
