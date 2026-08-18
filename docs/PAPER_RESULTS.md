# Paper Results — Repository Map

This document maps each manuscript item to the repository artifacts that
support it. Figure and table numbering in the manuscript is not treated as
frozen here; entries are labeled by experiment and role (main / appendix),
and the final numbering will be applied at submission time.

Each row gives, where applicable:

- **Scientific question**: what the item supports;
- **Command**: the command that produced the artifact (from the repository
  root; see `REPRODUCE.md`);
- **Canonical run**: the authoritative run that produced the numbers;
- **Source data**: the derived/raw artifact consumed by the figure/table;
- **Final artifact**: the figure/table/check shipped to the paper.

## Experiment 1 — Controlled Alignment and Regret Transfer

Current canonical: `exp1_alignment_transfer/outputs/paper_candidate/` (v1.2).

- Source full run:
  `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00`
  (`exp1_alignment_transfer/outputs/full/`, code_commit `23199c48`)
- Promotion date: 2026-08-18 (CHANGE_MEMO_EXP1_005)
- Engineering / scientific: PASS / PASS; `paper_result=true`
- CR-EXP-OUTPUT-V1 main figure ID: `fig_exp1_alignment_transfer`
- CR-EXP-OUTPUT-V1 publication bundle:
  `publication/CR-EXP-OUTPUT-V1/exp1_alignment_transfer/`

| Manuscript item | Scientific question | Command | Canonical run | Source data | Final artifact |
|---|---|---|---|---|---|
| Exp1 main figure (alignment transfer) | Does action-gap alignment govern structural regret transfer? | `python exp1_alignment_transfer/plot_main.py full` | `outputs/paper_candidate/` | `figures/data/fig_exp1_alignment_transfer_data.csv` | `figures/pdf/fig_exp1_alignment_transfer.pdf` |
| Exp1 appendix (delay survival) | Delay mechanism calibration survival | `python exp1_alignment_transfer/plot_appendix.py full` | `outputs/paper_candidate/` | `figures/data/fig_exp1_delay_survival_data.csv` | `figures/pdf/fig_exp1_delay_verification.pdf` |
| Exp1 appendix (reversal margin) | Reversal margin under alignment | `python exp1_alignment_transfer/plot_appendix.py full` | `outputs/paper_candidate/` | `figures/data/fig_exp1_reversal_margin_data.csv` | `figures/pdf/fig_exp1_reversal_margin.pdf` |
| Exp1 appendix (route trajectory) | Route-level trajectory | `python exp1_alignment_transfer/plot_appendix.py full` | `outputs/paper_candidate/` | `figures/data/fig_exp1_route_trajectory_data.csv` | `figures/pdf/fig_exp1_route_trajectory.pdf` |
| Exp1 appendix (state coupling) | State coupling diagnostic | `python exp1_alignment_transfer/plot_appendix.py full` | `outputs/paper_candidate/` | `figures/data/fig_exp1_state_coupling_data.csv` | (metadata lists appendix set) |
| Exp1 main table (mechanism summary) | Mechanism summary of alignment | `python exp1_alignment_transfer/main.py full` | `outputs/paper_candidate/` | `derived/exp1_primary_summary.csv` | `tables/tab_exp1_mechanism_summary.tex` |
| Exp1 checks | Engineering + scientific status | `python exp1_alignment_transfer/self_check.py full` | `outputs/paper_candidate/` | `derived/*.csv` | `checks/exp1_validation_report.json` |
| Exp1 manuscript values | Numbers quoted in the manuscript | `python exp1_alignment_transfer/promote.py --run full` | `outputs/paper_candidate/` | `derived/exp1_primary_summary.csv` | `manuscript/exp1_manuscript_values.json` |

## Experiment 2 — Attribution Sensitivity in Delayed Conversion Logs

Canonical run: `exp2_real_delayed_conversion_logs/outputs/paper/` (promoted
from `exp2-full-20260807T111616+0800`).

| Manuscript item | Scientific question | Command | Canonical run | Source data | Final artifact |
|---|---|---|---|---|---|
| Exp2 main figure (attribution sensitivity) | Sensitivity of the ranking diagnostic to attribution | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `figures/figure_exp2_attribution_sensitivity_source.csv` | `figures/figure_exp2_attribution_sensitivity.pdf` |
| Exp2 main figure (ambiguity mechanism) | Ambiguity-stratified mechanism | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `figures/figure_exp2_ambiguity_mechanism_source.csv` | `figures/figure_exp2_ambiguity_mechanism.pdf` |
| Exp2 appendix (delay) | Delay appendix | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `figures/figure_exp2_delay_appendix_data.csv` | `figures/figure_exp2_delay_appendix.pdf` |
| Exp2 appendix (pairwise) | Pairwise appendix | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `figures/figure_exp2_pairwise_appendix_data.csv` | `figures/figure_exp2_pairwise_appendix.pdf` |
| Exp2 main table (primary results) | Primary allocation/ordering contrasts | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `derived/primary_comparisons.csv` | `tables/table_exp2_primary_results.tex` |
| Exp2 table (cohort flow) | Cohort construction | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `derived/cohort_flow.csv` | `tables/table_exp2_cohort_flow.tex` |
| Exp2 table (robustness) | 30-day robustness window | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `derived/targeted_robustness.csv` | `tables/table_exp2_robustness_summary.tex` |
| Exp2 appendix table (pairwise) | Pairwise appendix table | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `derived/primary_comparisons.csv` | `tables/table_exp2_pairwise_appendix.tex` |
| Exp2 validation | Scientific validation + promotion audit | `python exp2_real_delayed_conversion_logs/main.py full` | `outputs/paper/exp2-full-20260807T111616+0800/` | `derived/*.csv` | `audit/scientific_validation.json`, `audit/promotion_audit.json` |

## Experiment 3 — Logged-Supported Ranking Recovery

Canonical run: `exp3-full-20260807T072340Z`; paper-facing copy:
`exp3_sequential_recommendation_delayed_feedback/paper_candidate/`.

| Manuscript item | Scientific question | Command | Canonical run | Source data | Final artifact |
|---|---|---|---|---|---|
| Exp3 main figure (score-gap-ranking) | Score -> reference-pair gap -> ranking recovery | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_main_score_gap_ranking_data.csv` | `paper_candidate/figures/main/exp3_main_score_gap_ranking.pdf` |
| Exp3 appendix (score calibration) | Score calibration diagnostic | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_score_calibration_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_score_calibration.pdf` |
| Exp3 appendix (gap error distribution) | Reference-pair gap error distribution | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_gap_error_distribution_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_gap_error_distribution.pdf` |
| Exp3 appendix (support preflight) | Full-design support preflight | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_full_design_support_preflight_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_full_design_support_preflight.pdf` |
| Exp3 appendix (route selection) | Ridge selection concentration | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_route_selection_concentration_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_route_selection_concentration.pdf` |
| Exp3 appendix (dependence/selection) | Dependence and selection structure | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_dependence_and_selection_structure_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_dependence_and_selection_structure.pdf` |
| Exp3 appendix (arrival carrier) | Arrival-carrier diagnostic | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `figures/data/exp3_appendix_arrival_carrier_diagnostic_data.csv` | `paper_candidate/figures/appendix/exp3_appendix_arrival_carrier_diagnostic.pdf` |
| Exp3 main table (primary route results) | Primary pooled supported-cell metrics | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `tables/exp3_primary_route_results.csv` | `paper_candidate/tables/exp3_primary_route_results.csv` |
| Exp3 main table (paired ranking contrast) | Ridge-over-historical paired value gain | `python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12` | `outputs/exp3-full-20260807T072340Z/` | `tables/exp3_paired_ranking_contrast.csv` | `paper_candidate/tables/exp3_paired_ranking_contrast.csv` |
| Exp3 self-check | Independent self-check status | `python exp3_sequential_recommendation_delayed_feedback/main.py self-check --mode full --run-id exp3-full-20260807T072340Z` | `outputs/exp3-full-20260807T072340Z/` | `checks/exp3_self_check.csv` | `checks/exp3_self_check.json` |

## Experiment 4 — Recoverability Boundary Diagnostic

Current canonical:
`exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/`
(result schema `exp4_controlled_route_audit_v3`, `paper_result=true`,
promotion PASS, provenance VERIFIED).

- Source run: `full_20260817T071019Z_7d7146b7` (code_commit `23199c48`,
  formal full, clean worktree at start)
- Engineering / scientific: PASS / PASS; `paper_result=true`
- CR-EXP-OUTPUT-V1 main figure ID:
  `fig_exp4_route_alignment_and_audit_reliability`
- CR-EXP-OUTPUT-V1 publication bundle:
  `publication/CR-EXP-OUTPUT-V1/exp4_controlled_route_audit/`
- Superseded legacy: `full_20260807T045219Z_7eeb2a31` (v2) was the previous
  paper result; it is kept as a legacy run and is no longer the canonical or
  paper-facing result.

| Manuscript item | Scientific question | Command | Canonical run | Source data | Final artifact |
|---|---|---|---|---|---|
| Exp4 main figure (route alignment / audit reliability) | Route-label retention and audit reliability | `python exp4_controlled_route_audit/main.py plot --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | `figures/data/fig_exp4_route_alignment_and_audit_reliability_data.csv` | `figures/pdf/fig_exp4_route_alignment_and_audit_reliability.pdf` |
| Exp4 appendix figures (11) | Module A/B/C diagnostics | `python exp4_controlled_route_audit/main.py plot --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | `figures/data/fig_app_exp4_*.csv` | `figures/pdf/fig_app_exp4_*.pdf` |
| Exp4 main table (calibration controls) | Calibration-family controls | `python exp4_controlled_route_audit/main.py tables --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | `derived/calibration/exp4_proxy_route_calibration.json` | `tables/tbl_exp4_calibration_controls.tex` |
| Exp4 appendix tables | Paired contrasts, parameter recovery, audit performance, etc. | `python exp4_controlled_route_audit/main.py tables --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | `derived/module_*/*.csv` | `tables/tbl_app_exp4_*.tex` |
| Exp4 checks | Scientific / engineering / precision / table checks | `python exp4_controlled_route_audit/main.py validate --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | `derived/*`, `tables/*` | `checks/exp4_scientific_checks.json`, `checks/exp4_engineering_checks.json` |
| Exp4 run summary | Overall run report | `python exp4_controlled_route_audit/main.py report --run-dir outputs/runs/full_20260817T071019Z_7d7146b7` | `outputs/runs/full_20260817T071019Z_7d7146b7/` | all of the above | `reports/exp4_run_summary.md` |

## CR-EXP-OUTPUT-V1 publication bundle

The canonical publication presentation bundle is
`publication/CR-EXP-OUTPUT-V1/` (one subdirectory per experiment). It is
rebuilt from the promoted frozen sources above with:

```bash
python render_presentation.py render --mode publication --exp all
python render_presentation.py validate --mode publication --exp all
```

Each experiment contains `figures/main|appendix/{pdf,svg,png,data,metadata}`,
`tables/{csv,tex,metadata}` (including `tab_experimental_evidence_map`),
`manifests/`, and `validation/`. Publication metadata records
`paper_result=true` and `promotion_status=CANONICAL_PUBLICATION` while keeping
`scientific_source_lineage` and `presentation_source_lineage` separate.
Rebuilding the publication presentation does not rerun any experiment.
