# Rerun and output inspection guide

## Required execution order

```bash
python code_check.py
python tests/test_temporal_contracts.py
python reproduce_fast.py --n-jobs 12 --clean-output
python self_check.py --mode fast
```

If real KuaiRand inputs are present and the fast outputs are acceptable:

```bash
python reproduce_full.py --n-jobs 24 --clean-output
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
python self_check.py --mode full
```

`--clean-output` is required only when an active output tree already exists. It prevents a new run from mixing with stale raw files, summaries, tables, or figure bundles.

## What to inspect after fast

1. `outputs/fast/metadata/run_manifest.json`
   - `input_data_status` must be `real_kuairand_1k` for a real-data fast run.
   - `paper_result` must be `false`.
   - `status` must be `complete_pending_external_checks`.
2. `outputs/fast/checks/input_schema_report.csv`
   - all three primary inputs must exist and contain the required columns.
3. `outputs/fast/summaries/arrival_mechanism_summary.csv`
   - confirm the two pseudo-arrival conditions have the same marginal delay profile.
4. `outputs/fast/summaries/paired_effect_vs_history_mean_static.csv`
   - use this for the paired short-term-ridge versus static-control comparison.
5. `outputs/fast/figures/png/fig_exp3_long_term_recoverability.png`
   - check labels, CI bars, the offline reference label, and the carrier baseline.

## What to inspect after full

1. `outputs/full/metadata/run_manifest.json`
   - before promotion: `paper_result=false`, `status=complete_pending_external_checks`.
   - after promotion: `paper_result=true`, `status=complete`.
2. `outputs/full/checks/self_check_report.csv`
   - must report `status=passed`.
   - after promotion it must report `promotion_status=already_promoted`.
3. `outputs/full/figures/`
   - both active figure bundles must have PDF, PNG, data CSV, and metadata JSON.
4. `outputs/full/tables/`
   - retain the three paper-facing appendix tables.
5. `outputs/full/metadata/artifacts_manifest.csv`
   - use this as the run-local inventory before release packaging.

## Expected full-run output details

- `sequential_decision_raw.csv`: one row per route, condition, label-mask replication when applicable, and daily decision bin.
- `user_bootstrap_draws.csv`: bootstrap replication-level metric draws; large but required for internal audit.
- `paired_effect_vs_history_mean_static.csv`: paired uncertainty comparison against the static history control.
- `tbl_app_exp3_source_label_sensitivity.csv`: sensitivity table; it must not be interpreted as a monotonicity or sparse-label-sufficiency result.
- `oracle_action_dynamics_summary.csv`: task-stability audit. A small number of oracle actions or a low switch rate limits the ability to isolate dynamic proxy value.

## Failure handling

- A failed run leaves a `run_manifest.json` with `status=failed` and an error string.
- Do not copy partial files from a failed active output tree into a later result directory.
- Correct the failure, then rerun the mode with `--clean-output`.
- Do not rerun full merely to repair release files, documentation, or archive checksums.
