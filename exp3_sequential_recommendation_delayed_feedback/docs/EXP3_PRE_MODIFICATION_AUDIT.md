# Exp3 Pre-Modification Audit

Audit date: 2026-08-06 (Asia/Hong_Kong)
Project: `exp3_sequential_recommendation_delayed_feedback`

## Source identity

- Git commit at audit start: `339a5d71930a05939f8a98fda3cdda11bbcbd5be`
- Source-tree SHA-256 at audit start: `9985cf74a6e7940366565eaeff53d361afe4ffa4509a5673a3a81699c56d0cf5`
- Worktree status: clean before this audit file was added.

## Active source tree

The active Python implementation contains the following responsibilities:

| Responsibility | Current file | Lines at audit |
|---|---|---:|
| Configuration and output directories | `config.py` | 137 |
| History-only action vocabulary and preprocessing | `preprocess_events.py` | 242 |
| Delayed target and pseudo-arrival construction | `construct_delayed_targets.py` | 199 |
| History support, groups, near-tie and reference design | `audit_design.py` | 205 |
| Historical mean and Ridge route fitting | `proxy_routes.py` | 224 |
| Evaluation arrays | `evaluation_arrays.py` | 107 |
| Score/gap/ranking orchestration | `evaluate_recoverability.py` | 288 |
| Bootstrap execution and summaries | `bootstrap_evaluation.py`, `bootstrap_summary.py` | 243, 263 |
| Main and appendix figures | `plot_main_results.py`, `plot_appendix_results.py` | 356, 370 |
| End-to-end orchestration | `runner.py` | 360 |
| Independent self-check | `self_check.py`, `self_check_helpers.py` | 401, 327 |

Tests at audit start:

- `tests/test_contracts.py`
- `tests/test_final_repair_contracts.py`
- `tests/test_target_and_figure_contracts.py`

## Current frozen configuration and contracts

- History/evaluation logs: `log_standard_4_08_to_4_21_1k.csv` and `log_standard_4_22_to_5_08_1k.csv`.
- Timezone: `Asia/Shanghai`; target horizon: six hours; target interval is implemented as `[t,t+6h)`.
- Full candidate action vocabulary: history-defined top-20; fast uses the prespecified top-6 computational scope.
- Support threshold: 500 events per fold in full and 15 in fast.
- Reference split count: two deterministic user folds.
- Routes: `arrival_carrier`, `history_mean_control`, `ridge_proxy`.
- Ridge source config is currently a fixed `ridge_alpha: float = 4.0`.
- User-cluster bootstrap: 100 fast / 1,000 full; resampling is sensitivity-only and does not claim formal confidence intervals.

## Known implementation locations

- Two-fold route/reference selection and held-out evaluation: `evaluate_recoverability.py`, `compute_metrics`, currently around lines 194-228.
- Current route action bug: `route_values = route_array[d, group_id, evaluation_fold]`; route action and route gap therefore use the evaluation fold.
- Current reference action and held-out target value already use selection/evaluation folds respectively.
- Current support output uses `pair_coverage` in `audit_design.py`, `evaluate_recoverability.py`, `bootstrap_summary.py`, plotting and self-check.
- Current route metadata uses `is_deployable` in `evaluate_recoverability.py` and `proxy_routes.py`.
- Current primary metric columns are legacy names such as `score_spearman_correlation`, `score_calibration_mae`, `heldout_gap_defect`, `gap_sign_agreement`, `cross_fitted_ranking_shortfall`, and `top_action_match_rate`.
- Current figure source inputs: `tables/exp3_primary_route_results.csv`, `tables/exp3_support_coverage.csv`, `checks/exp3_resampling_sensitivity_audit.csv`, and frozen derived tables loaded by `plot_main_results.py`.

## Execution commands and protection

- Compile: `python -m compileall .`
- Unit tests: `pytest -q`
- Synthetic fixture: `python main.py fast --synthetic-fixture --n-jobs 4`, then `python main.py self-check --mode fast --output-dir outputs/<fixture_run_id>`.
- Real fast: `python main.py fast --n-jobs 4`, then `python main.py self-check --mode fast --run-id <real_fast_run_id>`.
- Full, promotion and archive are explicit later gates and are not run during this modification.
- `runner.py` refuses to clean a manifest marked `paper_result`; `clean.py`, `promote.py`, and archival integrity code protect immutable/promoted outputs.

## Files potentially affected by the redesign

`config.py`, `proxy_routes.py`, `evaluate_recoverability.py`, `audit_design.py`, `bootstrap_summary.py`, `bootstrap_evaluation.py`, `plot_main_results.py`, `plot_appendix_results.py`, `runner.py`, `self_check.py`, `self_check_helpers.py`, `run_reporting.py`, `README.md`, tests, and new modules/tables/docs under this Exp3 directory only.

## Baseline decision

Proceed with the attached redesign contract. Preserve target construction, input files,
action vocabulary, support thresholds, six-hour horizon, pseudo-delay range and seeds.
Retain legacy aliases for one compatibility release while making canonical metric and
route metadata names authoritative. Do not run full, promote, archive, or modify Exp1,
Exp2, Exp4, paper sources, raw inputs, or promoted historical outputs.
