# Output Manifest — Toy delayed-feedback diagnostic

Each execution writes into `outputs/<mode>/`. The runner clears only the selected mode directory before running so stale artifacts cannot satisfy validation.

## Common outputs

- `logs/config_snapshot.yaml`: effective configuration, including mode, seed list, and raw-log policy.
- `logs/run_metadata.json`: execution state. A valid run requires `status: success` and `backend_status: executed`.
- `logs/run_manifest.csv`: one row per seed × delay setting × method run.
- `logs/method_registry.csv`: descriptions of `oracle`, `naive`, and `causal_labelled`.
- `summary/toy_seed_summary.csv`: per seed × delay setting × method outcomes.
- `summary/toy_method_summary.csv`: aggregate final-regret statistics.
- `summary/toy_trajectory_summary.csv`: trajectory means, standard errors, and 95% intervals.
- `figures/toy_selected_trajectories.{pdf,png}` and `figures/toy_full_trajectories.{pdf,png}`.
- `figures/*_trajectories_data.csv`: figure-source tables.

## Fast-only raw diagnostics

`fast` additionally writes:

- `raw/delay_schedule.csv`
- `raw/arrival_log.csv`
- `raw/step_log.csv`
- `raw/diagnostic_step_log.csv`

## Validation

```bash
python self_check.py --mode fast
python self_check.py --mode full
```

The self-check rejects skipped or failed backends, missing/empty files, nonfinite values, incomplete design coverage, invalid delay arithmetic, non-shared fast delay paths, nonzero oracle regret, and zero-delay disagreement between naive and causal-labelled outputs.
