# Output contract

Every paper-facing figure has four members:

```text
figures/pdf/<figure_id>.pdf
figures/png/<figure_id>.png
figures/data/<figure_id>_data.csv
figures/metadata/<figure_id>_metadata.json
```

`paper_result=false` is mandatory for every fast output. A full output may be
promoted only after:

```bash
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
```

Promotion requires real KuaiRand input hashes. It regenerates all figure CSVs,
metadata JSON, PDFs, PNGs, and the artifact manifest with
`paper_result=true`; updating the run manifest alone is not sufficient.

The run manifest and figure metadata record at least:

```text
run_id
run_mode
input_data_status
paper_result
config_hash
primary_horizon
primary_outcome_id
target_context
action_vocabulary_source
carrier_rule
main_feature_information
uncertainty_design
n_bootstrap
```

The main Exp3 figure must retain the boundary that it is a support-restricted
offline target-recoverability diagnostic, not OPE or online causal policy
evaluation.


## V5.2 active and retired interfaces

Active figures are:

```text
fig_exp3_long_term_recoverability
fig_app_exp3_horizon_eligibility
```

The former arrival-mechanism contrast, source-label-coverage curve, and
mean-engagement horizon curve are retired from active figure paths. Their
underlying audits remain in `summaries/` or `tables/`; any prior active bundles
are moved to `legacy/retired_figures/v5_2_retired_interface/` before rerendering.

Required V5.2 audit tables are:

```text
summaries/paired_effect_vs_history_mean_static.csv
tables/tbl_app_exp3_proxy_static_control.csv
tables/tbl_app_exp3_source_label_sensitivity.csv
```

The main-figure metadata must record the paired `ST ridge` versus `History mean`
effect and an explicit guide to points, intervals, the carrier baseline, and the
offline reference.

The main-figure source-data CSV and metadata must also satisfy the final visual
contract:

```text
Panel A method_id: short_term_ridge_proxy only
Panel A labels: ST ridge; y = x; Deciles; whiskers: 95% user-bootstrap CI
Panel B order: source_aware_reference, partial_source_label_q50, partial_source_label_q30,
  partial_source_label_q10, history_mean_static, short_term_ridge_proxy,
  short_term_composite_surrogate
Panel B labels: Reference (offline); Carrier baseline; Whiskers: 95% user-bootstrap CI
```

The horizon figure contract fixes the 6h tick label to `6h (primary)`, removes
the single-series legend, labels the prespecified primary horizon inside the
axes, and records that the figure is an availability diagnostic only.

The release-level notebook audit writes:

```text
outputs/full/checks/figure_release_audit.csv
outputs/full/checks/figure_release_audit.md
outputs/full/checks/exp3_figure_release_audit_executed.ipynb
```

These files are required release archive members.

## Rerun integrity

A run does not append to an existing active output tree. If `outputs/<mode>/` contains active artifacts, use the corresponding runner with `--clean-output`; otherwise the runner exits before writing a new manifest. This prevents stale summaries or figure bundles from being mixed with a fresh run.

CSV and JSON artifacts are written atomically. Input paths in `input_data_manifest.csv` are logical paths relative to the detected KuaiRand root rather than machine-specific absolute paths.

After a successful promotion, `checks/self_check_report.csv` must contain:

```text
status=passed
paper_result=True
promotion_status=already_promoted
```
