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
