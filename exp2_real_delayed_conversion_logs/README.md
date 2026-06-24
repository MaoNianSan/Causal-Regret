# Experiment 2: Source-time Attribution Sensitivity in Delayed Conversion Logs

Experiment 2 is a **logged attribution-sensitivity diagnostic** on the Criteo Attribution Modeling for Bidding conversion log. It asks whether assigning an arriving conversion to different recorded **source-time decision cells** changes (i) the allocation of logged conversion credit and (ii) the induced top-10 decision-cell ranking.

It is **not** online policy evaluation, off-policy value estimation, causal-regret estimation, randomized causal identification, or an economic ROI analysis.

## Why the action unit is a source-time cell

The early campaign-only implementation was scientifically degenerate: retained conversion journeys could contain multiple touches but only one campaign. First, last, linear, time-decay, and EM then became mathematically indistinguishable at the campaign level. More bootstrap replicates could not repair that information collapse.

The primary action is therefore:

```text
campaign_source_day_cell = (mapped campaign, source calendar day)
```

Only candidate impressions carrying the same `conversion_id` are used. The code does not add arbitrary historical exposures from other journeys. This preserves the public log's recorded conversion-path semantics while retaining source time.

## Valid claim and evidence role

The four-experiment evidence chain is:

```text
source binding validity
  -> logged attribution sensitivity
  -> long-term proxy recoverability
  -> recoverability boundary
```

The valid Experiment 2 conclusion is:

> On a common cohort of observed conversion journeys, different rules for assigning an arriving conversion to recorded source-time decision cells can change logged credit allocation and top-10 decision-cell ranking support.

The result is conditional on the observed cohort. It does not imply that a new online policy would obtain the reported credit mass.

## Primary action, routes, and outcome

- **Arrival-bin anchor (diagnostic):** a constructed arrival-bin credit anchor; it is `diagnostic_only=true` and `deployable=false`.
- **First click or touch:** earliest clicked source cell, otherwise earliest source touch.
- **Last click or touch:** latest clicked source cell, otherwise latest source touch.
- **Linear attribution:** equal credit across unique source-time cells.
- **Time-decay attribution:** credit weighted by source-to-conversion recency.
- **EM soft attribution:** computed only as an appendix route-validity diagnostic, not as a main-text comparator.
- **Criteo-attributed cell reference:** unique-labelled audit-only reference; it is not complete source ground truth.

The primary outcome is **binary credited-conversion mass**. Decision cells are ranked by credited mass per eligible cell impression. Criteo's transformed `cost` field appears only in an appendix robustness table and is never interpreted as profit or ROI.

## Main figure

`fig_exp2_attribution_sensitivity` has two panels:

1. source-to-conversion delay composition in the eligible cohort;
2. each route's **credit-allocation total-variation distance from the constructed arrival-bin anchor** versus its **top-10 decision-cell overlap with that anchor**.

This avoids treating route-specific top-k credited mass as a policy utility comparison.

## Appendix outputs

- `fig_app_exp2_source_route_pairwise_overlap`: source-route pairwise TV and top-10 decision-cell overlap heatmaps.
- `tbl_app_exp2_source_linked_audit`: bookkeeping audit for the unique-labelled subset; it may be attribution-nondiscriminative.
- `tbl_app_exp2_top_k_sensitivity`: table-only top-k sensitivity diagnostic; values near the action-cell universe are not robustness evidence.
- `tbl_app_exp2_candidate_window_sensitivity`: common-intersection window diagnostic, reported as a table so coverage and route effects are not conflated.
- `tbl_app_exp2_em_assignment_diagnostic`: EM entropy/concentration audit table.
- `tbl_app_exp2_cost_adjusted_credit_score`: transformed-cost robustness table only.

## Scientific gates

A fast or full run must fail semantic validation when any of the following fails:

1. at least 1% of main-cohort journeys have more than one candidate source-time decision cell;
2. at least one pair among the core source routes (first, last, linear, time decay) has nonzero assignment total-variation distance;
3. at least 0.1% of EM assignments have nonzero entropy;
4. the action-cell universe is strictly larger than the largest top-k cutoff;
5. UID integrity and every candidate-window UID audit have zero missing references and UID mismatches.

These are validity gates, not performance targets.

## Inputs

Place the protected raw file at exactly:

```text
inputs/pcb_dataset_final.tsv
```

The repository excludes the protected input and large processed intermediates. Lightweight saved summaries, figures, tables, checks, metadata, and notebooks are retained for GitHub inspection.

## Run commands

```powershell
# Fast audit: 200 UID bootstrap replicates, always paper_result=false
python main.py --mode fast --n-jobs auto
python self_check.py --mode fast
python code_check.py --mode fast

# Full run: 1,000 UID bootstrap replicates
python main.py --mode full --n-jobs auto
python self_check.py --mode full
python code_check.py --mode full
```

Full-mode figure bundles remain `paper_result=false` until the semantic check passes; `finalize_exp2.py` then promotes them to `paper_result=true`.

## Key outputs

```text
outputs/<mode>/processed/exp2_action_cell_mapping.csv
outputs/<mode>/processed/exp2_conversion_uid_integrity_summary.csv
outputs/<mode>/summaries/exp2_route_sensitivity_summary.csv
outputs/<mode>/summaries/exp2_main_route_divergence_audit.csv
outputs/<mode>/summaries/exp2_source_route_pairwise_overlap.csv
outputs/<mode>/summaries/exp2_candidate_window_sensitivity.csv
outputs/<mode>/summaries/exp2_em_assignment_diagnostic.csv
outputs/<mode>/figures/pdf/fig_exp2_attribution_sensitivity.pdf
outputs/<mode>/figures/pdf/fig_app_exp2_source_route_pairwise_overlap.pdf
outputs/<mode>/checks/exp2_self_check_report.md
```

Read `EXP2_MODIFICATION_RATIONALE_zh.md`, `REPAIR_NOTES.md`, `REPAIR_VALIDATION.md`, and `EXECUTION_GUIDE.md` before launching full mode.

## GitHub packaging notes

### Purpose

Logged delayed-conversion attribution sensitivity diagnostic using externally obtained Criteo data.

### Directory layout

- `src/`: artifact contract, runner, plotting, and summarization helpers.
- `inputs/`: local-only raw Criteo placement notes; protected data files are ignored.
- `ipy/`: GitHub-facing result-check notebook.
- `outputs/`: committed lightweight summaries, figures, tables, checks, metadata, and precheck previews; processed/raw intermediates are ignored.
- `docs/`: metric and paper-interface documentation.

### Input data requirement

Full reproduction requires `inputs/pcb_dataset_final.tsv` or the documented Criteo attribution source file, obtained under the original data license. The data file is not redistributed.

### How to run fast validation

Use `python reproduce_fast.py`, `python self_check.py --mode fast`, and `python code_check.py --mode fast` after placing required data or using the project-supported fixture path.

### How to run full reproduction

Use `python reproduce_full.py`, then `python self_check.py --mode full` and `python code_check.py --mode full`. Full mode requires the external raw Criteo data and was not run during final packaging.

### How to inspect existing results

Open `ipy/exp2_result_check.ipynb` or inspect `outputs/full/summaries/`, `outputs/full/figures/`, `outputs/full/tables/`, `outputs/full/checks/`, and `output_manifest.md`.

### Expected outputs

Expected GitHub-facing outputs are route summaries, precheck summaries, attribution figures, appendix tables, validation checks, metadata, and output manifests.

### What is committed to GitHub

Source code, README/docs, notebooks, run logs when present, manifests, lightweight summaries, figures, tables, checks, metadata, and precheck reports.

### What remains local and why

Criteo raw files, downloaded archives, processed timelines, route assignment intermediates, raw outputs, and cache/runtime state remain local because of size and data-license constraints.

## Clean-rerun safeguards

A clean run does not require a historical figure/table hash snapshot. The display-only SHA256 regression is enforced only when `outputs/<mode>/checks/figure_table_repair_core_hashes_before.csv` is deliberately supplied for a replot-only audit.

The main delay-composition figure is a distribution over eligible source-event rows. Its summary fields are `n_eligible_source_events` and `source_event_share_percent`; it is not a unique-conversion distribution.

UID values `-1` and `-1.0` are treated as missing for UID integrity and bootstrap clustering. Their row and conversion-ID counts are written to `exp2_conversion_uid_integrity_summary.csv`.

Before any real run, execute:

```powershell
python tests\run_synthetic_integration.py
```

This verifies the current fixture contract and identical UID-bootstrap output under `--n-jobs=1` and `--n-jobs=4`.

## Candidate-window diagnostic runtime contract

Candidate-window sensitivity is an appendix-only common-cohort point-estimate diagnostic. It does not run a separate nested UID bootstrap for every window. The main route-sensitivity summary remains the sole inferential Exp2 object and reports the configured UID-bootstrap confidence intervals. Candidate-window outputs record `window_bootstrap_replicates=0` and `window_uncertainty_status=not_computed_point_estimate_common_cohort_diagnostic`.

