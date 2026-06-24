# EXP1 output contract

This source package is distributed without completed `outputs/fast` or
`outputs/full` results. Standard execution creates outputs only through the
entry points documented in `README.md`.

## Run-level contract

Every run writes:

```text
outputs/<mode>/metadata/run_manifest.json
outputs/<mode>/metadata/run_log.json
outputs/<mode>/metadata/artifacts_manifest.csv
outputs/<mode>/checks/self_check_report.csv
```

The manifest records the contextual comparator, shared-path contract,
finite-horizon matched-delay calibration, EM likelihood identifier, proxy
feature-alignment contract, bootstrap settings, input status, paper-result
status, and raw-log mode.

## Required seed-level result columns

`outputs/<mode>/raw/seed_level_results.csv` includes, at minimum:

```text
experiment_id
subexperiment_id
setting_id
method_id
method_display_name
information_interface
reference_role
diagnostic_only
deployable
metric_id
metric_formula_id
primary_metric
primary_horizon
primary_outcome_id
seed
state_path_id
delay_path_id
label_mask_id
learner_rng_id
run_mode
paper_result
input_data_status
config_hash
```

It also includes contextual-regret, delay-calibration, feedback-accounting,
attribution, proxy, and EM diagnostic columns required by `self_check.py`.

## Required summaries and tables

```text
outputs/<mode>/summaries/seed_summary.csv
outputs/<mode>/summaries/method_summary.csv
outputs/<mode>/summaries/diagnostic_summary.csv
outputs/<mode>/summaries/paired_tests.csv
outputs/<mode>/summaries/bootstrap_ci.csv
outputs/<mode>/summaries/matched_mean_delay_summary.csv
outputs/<mode>/tables/table_exp1_results.csv
outputs/<mode>/tables/table_exp1_diagnostics.csv
outputs/<mode>/tables/table_exp1_matched_delay.csv
outputs/<mode>/tables/tbl_app_exp1_all_method_results.tex
outputs/<mode>/tables/tbl_app_exp1_simulation_settings.tex
outputs/<mode>/tables/tbl_app_exp1_information_interfaces.tex
```

All seed-based uncertainty intervals are percentile bootstrap intervals with
`2000` resamples.

## Required figure bundles

Each registered figure has a PDF, PNG, data CSV, and metadata JSON:

```text
fig_exp1_validity_boundary
fig_exp1_same_mean_delay
fig_exp1_attribution_diagnostics
fig_exp1_proxy_quality
fig_app_exp1_mismatch_diagnostics
fig_app_exp1_selected_trajectories
```

Figure-data CSVs contain the manuscript-interface fields used by the paper
figure contract, including `method_id`, `information_interface`,
`reference_role`, `deployable`, uncertainty fields, `run_mode`, and
`paper_result`.

## Trace logging

Normal fast and full runs use `summary_only` trace mode and do not create
schedule, arrival, or step trace placeholders. A request for
`raw_log_mode=full` with more than one worker is rejected. Detailed traces can
be generated only in a single-worker trace-audit run.
