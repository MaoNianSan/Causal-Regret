# Experiment 2 display-layer repair validation

## Scope

This pass was a pure display-layer and audit-layer repair on an already completed real-data `outputs/fast` run.

It did not rerun:

- `run_precheck.py`
- `construct_timeline.py`
- `run_exp2.py`
- `stats_exp2.py`
- `main.py`
- route assignment
- UID bootstrap
- source-time decision-cell construction
- candidate-window eligibility
- scientific-gate numeric computation

Only figures, tables, figure metadata, self-check audit logic, hash-regression audit files, and documentation were updated.

## Core Hash Regression

Before any figure/table regeneration, protected core output hashes were written to:

```text
outputs/fast/checks/figure_table_repair_core_hashes_before.csv
```

After replotting and table regeneration, protected core output hashes were written to:

```text
outputs/fast/checks/figure_table_repair_core_hashes_after.csv
outputs/fast/checks/figure_table_repair_regression.json
```

Regression result:

```text
same_file_set = true
same_sha256_for_every_core_file = true
figure_table_repair_regression_passed = true
n_core_files_before = 30
n_core_files_after = 30
```

The protected set covers `outputs/fast/processed`, `outputs/fast/summaries`, and stable existing files under `outputs/fast/checks`. Regenerable validation files from this repair (`figure_table_repair_*`, `exp2_self_check_*`, and `code_check_*`) were excluded from the protected hash set so the allowed audit commands could run without falsely changing the core statistics contract.

## Repaired Outputs

- `fig_exp2_attribution_sensitivity` was redrawn with short non-overlapping panel titles and bounded Panel B Top-10 annotations. Marker coordinates, CIs, route order, and annotation values were not changed.
- `fig_app_exp2_source_route_pairwise_overlap` was redrawn from the existing pairwise summary and contains only `first_click`, `last_click`, `linear_attribution`, and `time_decay_soft`. Its metadata now includes `figure_role = appendix_source_route_mechanism_diagnostic`.
- `tbl_app_exp2_source_linked_audit` now includes `candidate_decision_cell_count_p90`, `attribution_nondiscriminative`, and `interpretation_note`.
- Formal appendix tables have CSV, Markdown, and TeX triplets.
- Required docs state that Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity, not causal regret, online policy value, ROI, or deployable policy comparison.

## Commands Run

Allowed display/audit commands only:

```powershell
python plot_exp2.py --config .runtime\config_exp2_fast.yaml
python make_tables_exp2.py --config .runtime\config_exp2_fast.yaml
python self_check.py --mode fast
python code_check.py --mode fast
```

No statistics, route-assignment, timeline, precheck, bootstrap, or full-mode command was run in this repair pass.

## Validation

The final fast self-check passed with 67 checks and 0 failures, including:

```text
[PASS] figure_table_repair_regression
[PASS] main_figure_uses_horizontal_point_range
[PASS] pairwise_heatmap_excludes_arrival_anchor
[PASS] main_figure_panel_titles_do_not_overlap
[PASS] main_figure_annotations_within_axes
[PASS] source_linked_audit_has_nondiscriminative_flag
[PASS] csv_md_tex_table_triplets_exist
[PASS] docs_present_and_updated
```

`python code_check.py --mode fast` also passed, including:

```text
[PASS] formal_latex_figure_interface_nonempty
```

The current fast numeric results can continue to serve as the design-validation basis before any full run. Real full mode was not run.
