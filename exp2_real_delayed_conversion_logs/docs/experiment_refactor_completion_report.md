# Exp2 source-time decision-cell semantic refactor completion report

## Scope completed

This package implements the second-stage Exp2 correction after the source-time decision-cell action refactor. It preserves:

- all-conversion main cohort;
- unique-labelled audit-only source-linked reference;
- UID-cluster bootstrap;
- source-time `campaign × calendar-day` decision-cell action unit;
- fast/full mode isolation and paper-result finalization gate.

It changes:

- primary figure coordinate from top-k credited-mass displacement to credit-allocation total-variation distance versus the constructed arrival-bin anchor;
- main figure route set by moving EM to appendix diagnostics;
- appendix presentation from redundant source-linked/window/EM figures to tables;
- appendix figure presentation to pairwise source-route TV distance and top-10 overlap heatmaps;
- route display names to disclose click-to-touch fallback;
- scientific degeneracy gate to require divergence among core source routes, not merely a difference from the arrival anchor.

## Current formal objects

### Main

- `fig_exp2_attribution_sensitivity`
- `tbl_exp2_route_sensitivity`

### Appendix

- `fig_app_exp2_source_route_pairwise_overlap`
- source-linked audit table
- top-k sensitivity table
- candidate-window table
- EM allocation-concentration table
- transformed-cost robustness table

## Scientific interpretation boundary

The package supports logged source-time credit-allocation/ranking sensitivity. It does not identify causal regret, online policy value, randomization effects, or economic ROI.

Exp2 evaluates observational logged credit-allocation and source-time decision-cell ranking sensitivity.
It does not estimate causal regret, online policy value, ROI, or a deployable policy comparison.

## Validation status

- Synthetic fixture: passed on 2026-06-22 using `inputs/synthetic_fixture.tsv`.
- Fast synthetic pipeline completed with 200 UID bootstrap replicates, 56 passing semantic checks, figure/table generation, smoke checks, and code check.
- Bootstrap determinism was checked by comparing `--n-jobs=1` and `--n-jobs=4` outputs for the main route summary, raw UID bootstrap replicates, and pairwise source-route overlap.
- Real Criteo full: not run here. The protected `inputs/pcb_dataset_final.tsv` was not overwritten by synthetic validation.
- Required next step: clean real-data fast run from `main.py`, inspect all semantic gates, then run full only if fast passes.

## Files changed in this repair pass

This pass is limited to figure, table, metadata, check, and documentation repair. It does not rerun or modify timeline construction, route assignment, statistics, bootstrap, source-time decision-cell mapping, UID integrity, or scientific gates.

- `plot_exp2.py`
- `make_tables_exp2.py`
- `self_check_exp2.py`
- `code_check.py`
- `README.md`
- `REPAIR_VALIDATION.md`
- `docs/metric_specification.md`
- `docs/output_contract.md`
- `docs/latex_interface_experiments.md`
- `docs/experiment_refactor_completion_report.md`

Synthetic outputs are validation artifacts only. They must not be interpreted as Criteo empirical results or copied into paper-facing real-data outputs.

## 2026-06-24 rerun-readiness repair

The clean-run hash-regression contract, source-event delay-profile denominator, synthetic-fixture configuration, and UID `-1` handling were repaired. The synthetic integration runner executes the corrected fixture twice (`--n-jobs=1` and `--n-jobs=4`) and requires identical UID-bootstrap hashes before a real Criteo run is attempted.

## Candidate-window diagnostic runtime contract

Candidate-window sensitivity is an appendix-only common-cohort point-estimate diagnostic. It does not run a separate nested UID bootstrap for every window. The main route-sensitivity summary remains the sole inferential Exp2 object and reports the configured UID-bootstrap confidence intervals. Candidate-window outputs record `window_bootstrap_replicates=0` and `window_uncertainty_status=not_computed_point_estimate_common_cohort_diagnostic`.

