# Experiment 3 — Offline recoverability of a constructed 6h target in KuaiRand logs

## Scope and interpretation boundary

Experiment 3 is an **offline logged-support recoverability diagnostic**, not an online recommendation-policy evaluation. A source event is a standard-feed user--video exposure. For an eligible event at time \(t\), the constructed future-engagement target is

\[
V^{(6h)}_{u,t}
=
0.5\,\mathrm{long\_view}
+1.0\,\mathrm{like}
+1.0\,\mathrm{comment}
+1.0\,\mathrm{forward}
+1.5\,\mathrm{follow},
\qquad
Y^{(6h)}_{u,t}=\log\{1+V^{(6h)}_{u,t}\}.
\]

The target is constructed from later engagement in the same standard-log split. It is **not** an official platform utility, native delayed-conversion label, identified causal effect, off-policy estimate, or online policy value.

## Fixed protocol

- **History split:** `log_standard_4_08_to_4_21_1k.csv`
- **Held-out main split:** `log_standard_4_22_to_5_08_1k.csv`
- **Primary horizon:** 6h
- **Action vocabulary:** 20 most frequent non-missing history tags; residual tags are retained in update accounting but excluded from candidate actions.
- **Decision aggregation:** 1 day.
- **Primary ranking metric:** offline 6h ranking regret under a support-restricted daily action set.
- **Bootstrap:** user-cluster bootstrap; fast uses 100 draws and 3 label-mask trajectories, full uses 1,000 draws and 30 label-mask trajectories.

The standard history split alone defines the action vocabulary and fits the ridge proxy. Main-split proxy features use completed history and earlier main bins only. The carrier route assigns an arriving outcome to the most recent same-user standard exposure at or before arrival.

## Required raw inputs

Place the following files under `inputs/KuaiRand-1K/data/`:

```text
log_standard_4_08_to_4_21_1k.csv
log_standard_4_22_to_5_08_1k.csv
video_features_basic_1k.csv
```

The random-exposure log is optional and is not used in the primary Exp3 target construction.

## Before every rerun

Run the static and temporal checks first:

```bash
python code_check.py
python tests/test_temporal_contracts.py
```

The runner refuses to mix a new run with stale active outputs. When rerunning a mode, pass `--clean-output`; this removes only active artifacts for that mode and preserves `outputs/<mode>/legacy/`.

## Fast run

```bash
python reproduce_fast.py --n-jobs 12 --clean-output
python self_check.py --mode fast
```

When original KuaiRand files are absent, fast mode creates a deterministic synthetic fixture solely for software and figure-contract testing. Such output is always `paper_result=false` and cannot be cited in the paper.

## Full run

```bash
python reproduce_full.py --n-jobs 24 --clean-output
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
python self_check.py --mode full
```

Full mode is blocked if the three required raw inputs are absent. Do not run `build_upload_packages.py` until the final full self-check passes and the manifest reports `paper_result=true`.

To refresh only the final full figure interfaces after a promoted or promotable full run, use:

```bash
python refresh_full_figures.py
```

This reads existing `outputs/full` summaries and metadata, rewrites only active figure bundles and the artifact manifest, and does not rerun `reproduce_full.py`.

## Output contract

Each run writes to `outputs/<mode>/`:

```text
raw/
  sequential_decision_raw.csv
  user_bootstrap_draws.csv
  proxy_calibration_cells_raw.csv
  proxy_calibration_bootstrap_draws.csv
processed/
  action_vocabulary.csv
  fixed_action_bucket_map.csv
  *_processed.parquet or *_processed.csv
  *_source_events_with_targets.parquet or *_source_events_with_targets.csv
  arrival_timeline_audit_sample_<condition>.csv
summaries/
  user_bootstrap_metric_summary.csv
  paired_effect_vs_arrival_time.csv
  paired_effect_vs_history_mean_static.csv
  paired_mechanism_contrast.csv
  oracle_action_dynamics_summary.csv
  proxy_calibration_summary.csv
  arrival_mechanism_summary.csv
tables/
  tbl_app_exp3_proxy_score_quality.csv
  tbl_app_exp3_proxy_static_control.csv
  tbl_app_exp3_source_label_sensitivity.csv
figures/pdf/, figures/png/, figures/data/, figures/metadata/
metadata/
  run_manifest.json
  run_config_snapshot.json
  input_data_manifest.csv
  artifacts_manifest.csv
checks/
  input_schema_report.csv
  code_check_report.csv
  self_check_report.csv
reports/
  experiment_refactor_completion_report.md
```

Every active figure has four synchronized members: PDF, PNG, source-data CSV, and metadata JSON. The only active paper interfaces are:

```text
fig_exp3_long_term_recoverability
fig_app_exp3_horizon_eligibility
```

The arrival-mechanism contrast and source-label coverage curve are audit-only; they are not active paper figures.

The main figure visual contract fixes Panel A to `short_term_ridge_proxy` (`ST ridge`) and Panel B to seven routes in this order: `source_aware_reference`, `partial_source_label_q50`, `partial_source_label_q30`, `partial_source_label_q10`, `history_mean_static`, `short_term_ridge_proxy`, `short_term_composite_surrogate`. The horizon figure marks `6h (primary)` as the prespecified primary horizon and reports right-censoring availability only.

## Result boundary

The permitted conclusion is that a history-fitted short-term proxy can show held-out alignment with the constructed 6h target. A lower point estimate than `history_mean_static` does **not** establish an incremental dynamic decision-level gain when its paired confidence interval spans zero. Do not claim online policy improvement, OPE, causal regret, platform utility evaluation, label sufficiency, or monotonic label-rate recovery.

## Release packaging

After a promoted full run:

```bash
jupyter nbconvert --to notebook --execute notebooks/exp3_figure_release_audit.ipynb --output exp3_figure_release_audit_executed.ipynb --output-dir outputs/full/checks/
python build_upload_packages.py
python verify_release_package.py
```

The release verifier checks active figure bundles, the notebook audit outputs, release-manifest hashes, checksum-index hashes, archive sidecars, and exclusion of raw KuaiRand inputs and full raw event-level outputs.
