# Exp4 v2 Implementation Status

Status date: 2026-08-06  
Schema: `exp4_controlled_route_audit_v2`  
Scope: `exp4_controlled_route_audit` only

## 1. Modified Files

### Added

- `exp4/` v2 package with configuration, simulation, routes, metrics, audit, calibration, modules, execution, outputs, reporting, and validation subpackages.
- `tests/unit`, `tests/integration`, and `tests/regression` coverage.
- `MIGRATION_V1_TO_V2.md`.
- `reports/EXP4_V2_PRE_REFACTOR_AUDIT.md`.
- `reports/EXP4_MANUSCRIPT_MAPPING.md`.
- `reports/EXP4_V2_IMPLEMENTATION_STATUS.md`.

### Modified

- `README.md`, `main.py`, `promote_results.py`, `reproduce_all.py`, and top-level compatibility modules.
- The top-level `config.py`, `simulator.py`, `route_maps.py`, `audit_engine.py`, `aggregate_results.py`, `engine.py`, `run_experiment4.py`, `plot_results.py`, `make_tables.py`, `code_check.py`, `self_check.py`, `write_run_summary.py`, and `io_utils.py` now wrap or re-export the v2 implementation.

### Deleted

- `policies.py`: Exp4 learner/UCB logic was removed from the active experiment because Exp1 owns learner-consequence and regret-transfer evidence.

### Compatibility wrappers

- Existing `python main.py fast`, `python main.py middle`, and `python main.py full` commands use v2 scientific logic.
- Plot, table, validation, aggregation, and report wrappers retain their top-level entry points.
- V1 and legacy outputs remain read-only regression evidence and are rejected by v2 promotion.

## 2. Refactor Result

- Largest pre-refactor file: `audit_engine.py`, 701 lines.
- Largest active v2 file: `exp4/simulation/trajectory.py`, 262 lines.
- Files above 450 lines: 0.
- Largest active function: `generate_structural_trajectory`, 92 lines.
- Active functions above 80 lines: 5; these are cohesive trajectory/module/report orchestration functions, not multi-domain scientific monoliths.
- Authoritative `compute_action_gap_defect` implementations: 1.
- Duplicated scientific logic count: 0 found by static AST/source checks.
- Circular imports: 0 found in the active v2 import graph.
- Dormant oracle registry entries: removed.
- Plotting imports from simulation/routes/audit/calibration engines: 0.

## 3. Tests and Checks

- Compile: PASS, `python -m compileall -q .`.
- Pytest: PASS, 13 passed.
- Static code contract: PASS.
- Engineering validation: PASS for final fast and middle runs.
- Scientific validation: PASS for final fast and middle runs.
- Regression: v1 defect snapshot, schema migration, and v1-output blocking tests PASS.
- `git diff --check`: PASS.
- Lint/type checks: no `ruff`, `mypy`, or `pyright` installation was available; static AST checks and Python compilation were run instead.

Scientific checks passed include source-bound/full-label zero defect, all 45 pairs, positive attribution mass, historical candidate sets, stream independence, label-blind ambiguity, exact Definition 4.3 formula, formal A/B horizons, nested route labels, shared selective masks, IPW positivity, temporal no-leakage, affine parameter recovery, blocked correspondence destruction, calibration/evaluation seed separation, exact mean delay, figure reconstruction, and the Exp1-Exp4 boundary.

## 4. Fast

- Run ID: `fast_20260806T015140Z_b7944cd8`.
- Status: engineering PASS; scientific PASS.
- Schema: `exp4_controlled_route_audit_v2`.
- Artifact completeness: PASS, including 11 figure bundles and all required module/calibration outputs.
- Paper result: `false`.
- Promotion: not run and not allowed for fast.

## 5. Middle

- Run ID: `middle_20260806T015324Z_2f52e832`.
- Status: engineering PASS; scientific PASS.
- Workers: 8.
- Monitored runtime: 570.6 seconds.
- Sampled peak process working set: 348.4 MB.
- Resume test: PASS; 9.99 seconds with completed simulation stages skipped.
- Parallel/serial determinism: exact equality PASS for representative Module A, Module B, and Module C recomputations.
- Route maps: 100 complete Module B/C replications.
- Artifact reconstruction: PASS.
- Paper result: `false`.
- Promotion: not run and not allowed for middle.

## 6. Scientific Implementation

- Module A uses the unique mean per-round maximum action-gap defect and separates optimal-set conflict, pairwise sign disagreement, and margin certificate.
- Attribution uses candidate source proxies and arrival-side signatures generated from the true source state plus frozen noise; the arrival-clock state is not used as the source signature.
- Kernel bandwidth and delay prior are frozen from 20 independent calibration seed IDs.
- Module B stores unit and condition outputs, paired selective masks, Hájek IPW, ESS/support diagnostics, and Monte Carlo error.
- Module C uses contiguous temporal cross-fitting, pair-specific affine fits, explicit `NOT_ESTIMABLE` status, parameter recovery, permutation hashes, and correspondence checks.
- The main figure contains route alignment, audit bias, audit RMSE, and effective support. Module C is reported in the main table.
- Main artifacts contain no learner regret, transfer bound, delay-mechanism comparison, or proxy-impossibility claim.

## 7. Not Executed

```text
FULL_RUN_EXECUTED=NO
PAPER_PROMOTION_EXECUTED=NO
GIT_COMMIT_EXECUTED=NO
GIT_PUSH_EXECUTED=NO
```

## 8. Readiness

```text
CODE_CORRECTNESS=PASS
SCHEMA_V2=PASS
FAST=PASS
MIDDLE=PASS
SCIENTIFIC_INVARIANTS=PASS
PARALLEL_DETERMINISM=PASS
ARTIFACT_RECONSTRUCTION=PASS
EXP1_EXP4_BOUNDARY=PASS
FULL_READY=YES
```

## 9. Next Command

```powershell
python main.py full --n-jobs 8
```
