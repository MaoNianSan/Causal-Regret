# Cloud-readable experiment output index

> Machine-readable companion: [`CLOUD_OUTPUT_INDEX.json`](CLOUD_OUTPUT_INDEX.json)
> Per-artifact manifest: [`../cloud_outputs/CLOUD_MANIFEST.json`](../cloud_outputs/CLOUD_MANIFEST.json)
> Exclusion report: [`CLOUD_OUTPUT_EXCLUSIONS.md`](CLOUD_OUTPUT_EXCLUSIONS.md)
>
> Generated: 2026-09-10 · Purpose: make experiment outputs directly readable
> from GitHub/cloud agents. This index changes **no scientific result** and
> performs **no promotion** — it only records where outputs live and what
> evidence tier they belong to.

## How to read this index

- **Evidence tier** — `canonical` (promoted paper result), `accepted_nonpromoted`
  (accepted targeted diagnostics, not a paper result), `presentation` (review/
  presentation material), `audit` (audit/provenance material).
- **Paper-result status** — `true` only for the promoted paper candidates.
  Targeted outputs are always `false`.
- **Canonical source?** — `yes` marks the scientific source of truth;
  `no` marks copies (e.g. the `publication/CR-EXP-OUTPUT-V1` paper-facing copy).

---

## Exp1 — alignment transfer

### Primary paper candidate (canonical, promoted)

| Field | Value |
| --- | --- |
| Repository path | `exp1_alignment_transfer/outputs/paper_candidate/` |
| Evidence tier | `canonical` |
| Paper-result status | `true` |
| Promoted | yes |
| Kind | primary |
| Formats | csv, json, pdf, png, tex |
| Key claim supported | Exp1 primary results (learner summary, route summary, regret-stability utilization) |
| Interpretation boundary | Only these files are the promoted primary Exp1 result |
| Canonical source | yes |

Key files: `derived/exp1_primary_summary.csv`, `derived/exp1_learner_summary.csv`,
`derived/exp1_regret_stability_utilization*.csv`, `checks/exp1_validation_report.json`,
`exp1_promotion_manifest.json`.

### Accepted targeted diagnostics (NOT promoted)

| Field | Value |
| --- | --- |
| Repository path | `exp1_alignment_transfer/outputs/full/targeted/` |
| Evidence tier | `accepted_nonpromoted` |
| Paper-result status | `false` |
| Promoted | no |
| Kind | targeted |
| Formats | csv, json |
| Key claim supported | Targeted cancellation, horizon-route and mean-delay diagnostics (accepted validation-level evidence) |
| Interpretation boundary | Targeted, not canonical primary results; must not be cited as primary paper results |
| Canonical source | yes (accepted targeted diagnostics) |

Key files: `exp1_targeted_cancellation_sweep.csv`,
`exp1_targeted_cancellation_summary.csv`,
`exp1_targeted_cancellation_invariants.json`,
`exp1_targeted_validation_report.json`,
`exp1_targeted_horizon_route_seed_metrics.csv`,
`exp1_targeted_horizon_route_summary.csv`,
`exp1_targeted_horizon_seed_metrics.csv`,
`exp1_targeted_horizon_summary.csv`,
`exp1_targeted_mean_delay_seed_metrics.csv`,
`exp1_targeted_mean_delay_summary.csv`,
`exp1_targeted_theory_exact_shift_sweep.csv`,
`exp1_targeted_theory_margin_threshold_sweep.csv`,
`fig_exp1_targeted_validation_data.csv`.

### Stability utilization (accepted, NOT promoted)

| Field | Value |
| --- | --- |
| Repository path | `exp1_alignment_transfer/outputs/full/derived/exp1_regret_stability_utilization*.csv` |
| Evidence tier | `accepted_nonpromoted` |
| Paper-result status | `false` |
| Promoted | no |
| Kind | targeted |
| Formats | csv |
| Key claim supported | Regret-stability utilization (seed-level and summary) |
| Interpretation boundary | Accepted targeted diagnostic; the promoted copy lives in `outputs/paper_candidate/derived/` |
| Canonical source | full-run source (promoted copy in paper_candidate) |

### Targeted appendix figure

| Field | Value |
| --- | --- |
| Repository path | `exp1_alignment_transfer/outputs/full/figures/` (data/metadata/pdf/png) |
| Evidence tier | `accepted_nonpromoted` |
| Paper-result status | `false` |
| Promoted | no |
| Kind | targeted |
| Formats | csv, json, pdf, png |
| Key claim supported | Targeted cancellation appendix figure and its source data |
| Interpretation boundary | Full-run figure bundle; the promoted paper figures live in `outputs/paper_candidate/figures/` |
| Canonical source | full-run copy (promoted copy in paper_candidate) |

### Full self-check / validation / provenance

| Field | Value |
| --- | --- |
| Repository path | `exp1_alignment_transfer/outputs/full/checks/`, `.../metadata/`, `.../seed_metrics/`, `.../tables/`, `.../manuscript/` |
| Evidence tier | `accepted_nonpromoted` |
| Paper-result status | `false` |
| Promoted | no |
| Kind | validation / provenance |
| Formats | json, csv, tex |
| Key claim supported | Full-run audit (`exp1_v12_full_output_audit.json`), validation report, stage provenance, mechanism summary table, seed metrics |
| Interpretation boundary | Validation-level; paper candidates remain in `paper_candidate/` |
| Canonical source | yes (full-run records) |

---

## Exp2 — real delayed-conversion logs

### Canonical paper run

| Field | Value |
| --- | --- |
| Repository path | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` |
| Evidence tier | `canonical` |
| Paper-result status | `true` |
| Promoted | yes |
| Kind | primary |
| Formats | csv, json, tex, pdf, png, svg |
| Key claim supported | Attribution sensitivity, ambiguity mechanism, cohort flow, primary results, robustness |
| Interpretation boundary | Canonical Exp2 paper run; non-paper development runs are excluded |
| Canonical source | yes |

Key files: `figures/figure_exp2_attribution_sensitivity_source.csv` (main figure
source data), `figures/figure_exp2_attribution_sensitivity.{pdf,png,svg}`,
`tables/table_exp2_primary_results.csv`, `derived/primary_comparisons.csv`,
`audit/scientific_validation.json`, `run_manifest.json`.

### Uncertainty semantics

- Exp2 resampling sensitivity range is an **empirical 2.5%–97.5% UID-cluster
  resampling range, not a confidence interval**. See `docs/PAPER_RESULTS.md`.

---

## Exp3 — sequential recommendation, delayed feedback

### Canonical paper run

| Field | Value |
| --- | --- |
| Repository path | `exp3_sequential_recommendation_delayed_feedback/outputs/exp3-full-20260807T072340Z/` |
| Evidence tier | `canonical` |
| Paper-result status | `false` (the promoted paper-facing copy lives under `publication/CR-EXP-OUTPUT-V1/exp3_*`) |
| Promoted | no (run is canonical; promotion copy is the publication tree) |
| Kind | primary |
| Formats | csv, json, md, pdf, png |
| Key claim supported | Score-gap-ranking main result, paired ranking contrast, calibration, resampling sensitivity |
| Interpretation boundary | Canonical run outputs; paper-facing copies under `publication/` remain authoritative for the manuscript |
| Canonical source | yes |

Key files:
- main figure data: `figures/data/exp3_main_score_gap_ranking_data.csv`
- score/gap/ranking: `tables/exp3_primary_route_results.csv`,
  `tables/exp3_paired_ranking_contrast.csv`, `tables/exp3_decile_calibration.csv`,
  `tables/exp3_gap_error_distribution.csv`
- resampling sensitivity: `checks/exp3_resampling_sensitivity_audit.csv`,
  `checks/exp3_bootstrap_interval_audit.csv`
- calibration/selection: `tables/exp3_ridge_coefficients.csv`,
  `tables/exp3_ridge_history_cv.csv`, `tables/exp3_support_coverage.csv`
- validation: `checks/exp3_self_check.json`, `reports/EXP3_RUN_REPORT.md`
- provenance: `manifest/run_manifest.json`, `metadata/run_config_snapshot.json`,
  `design/exp3_design_freeze.json`, `diagnostics/exp3_resampling_structure_diagnostics.json`

### Uncertainty semantics

- Exp3 resampling sensitivity range is an **empirical 2.5%–97.5% user-cluster
  resampling range, not a confidence interval**.

---

## Exp4 — controlled route audit

### Canonical full run

| Field | Value |
| --- | --- |
| Repository path | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` |
| Evidence tier | `canonical` |
| Paper-result status | `true` |
| Promoted | yes |
| Kind | primary |
| Formats | csv, json, tex, md, pdf, png |
| Key claim supported | Route alignment (Module A), audit reliability (Module B), calibration/recoverability (Module C) |
| Interpretation boundary | Canonical curated full run; raw/parquet/simulation intermediates excluded |
| Canonical source | yes |

Key files:
- Module A: `derived/module_a/exp4_module_a_paired_contrasts.csv`,
  `derived/module_a/exp4_module_a_population_summary.csv`,
  `derived/module_a/exp4_module_a_seed_direction_summary.csv`
- Module B: `derived/module_b/exp4_module_b_audit_performance.csv`,
  `derived/module_b/exp4_module_b_selection_diagnostics.csv`,
  `derived/module_b/exp4_module_b_weight_diagnostics.csv`
- Module C: `derived/module_c/exp4_module_c_control_summary.csv`,
  `derived/module_c/exp4_module_c_correspondence_checks.csv`,
  `derived/module_c/exp4_module_c_parameter_recovery.csv`
- main figure: `figures/pdf/fig_exp4_route_alignment_and_audit_reliability.pdf`,
  `figures/png/fig_exp4_route_alignment_and_audit_reliability.png` with source
  data at `figures/data/fig_exp4_route_alignment_and_audit_reliability_data.csv`
  and metadata at `figures/metadata/fig_exp4_route_alignment_and_audit_reliability_metadata.json`
- checks/tables/reports: `checks/exp4_scientific_checks.json`,
  `checks/exp4_v3_full_output_audit.json`, `tables/*.csv|tex`,
  `reports/exp4_run_summary.md`
- provenance: `logs/exp4_run_lineage.json`, `logs/exp4_stage_provenance.json`,
  `logs/output_manifest.json`

---

## Review / handoff

### Figure review package (non-authoritative)

| Field | Value |
| --- | --- |
| Repository path | `cloud_outputs/figure_review_20260910/` |
| Evidence tier | `presentation` / `audit` |
| Paper-result status | `false` |
| Promoted | no |
| Kind | presentation / handoff |
| Formats | md, json, png, pdf, svg |
| Key claim supported | Figure round audit and manuscript handoff visibility |
| Interpretation boundary | Review snapshot, explicitly NOT the scientific source of truth |
| Canonical source | no (copy of external review package) |

Key files: `FIGURE_ROUND_AUDIT.md`, `figure_round_audit.json`,
`figure_review_sheet_old_vs_new.png`, `EXP1_EXP4_MANUSCRIPT_HANDOFF_20260910.md`,
`candidate_main_figures/{pdf,png,svg}/*`, `audit/source_hashes_baseline.json`,
`audit/source_hashes_after.json`, `audit/validation_preview_after.json`.

### Paper-facing publication copy

| Field | Value |
| --- | --- |
| Repository path | `publication/CR-EXP-OUTPUT-V1/` |
| Evidence tier | `canonical` (paper-facing copy) |
| Paper-result status | `true` |
| Promoted | yes |
| Kind | primary (copy) |
| Formats | csv, json, tex, pdf, png, svg |
| Key claim supported | Manuscript-facing figures/tables/manifests for Exp1–Exp4 |
| Interpretation boundary | Copy of promoted results; per-experiment paths above remain the scientific source of truth |
| Canonical source | no (copy) |

---

## Index documents themselves

| Document | Role |
| --- | --- |
| `docs/CLOUD_OUTPUT_INDEX.md` | This human-readable index |
| `docs/CLOUD_OUTPUT_INDEX.json` | Machine-readable group index |
| `cloud_outputs/CLOUD_MANIFEST.json` | Per-artifact manifest (path, sha256, bytes, tier) |
| `docs/CLOUD_OUTPUT_EXCLUSIONS.md` | What was intentionally NOT published and why |
