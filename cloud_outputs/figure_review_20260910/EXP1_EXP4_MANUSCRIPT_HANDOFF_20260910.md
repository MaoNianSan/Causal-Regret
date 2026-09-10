# Exp1–Exp4 Manuscript Handoff — 2026-09-10

**Report only.** No LaTeX manuscript file was read for editing and none was
modified in this session. Every number below is read from a frozen repository
source; the source path is given next to it. Where a quantity is undefined in
the source, it is reported as undefined rather than as zero.

- Repository HEAD: `b1a7775b506c6c290b3d2368e657a8518d06c558` (`origin/main` identical)
- Spec: `CR-EXP-OUTPUT-V1`
- Candidate figures: `figure_review_20260910\candidate_main_figures\` (preview, not promoted)
- Nothing was promoted, published, or pushed in this session.

---

## Exp1 — Controlled alignment and regret transfer

### Paths

| Role | Path |
|---|---|
| Canonical primary figure (published) | `publication/CR-EXP-OUTPUT-V1/exp1_alignment_transfer/figures/main/pdf/fig_exp1_alignment_transfer.pdf` (also `.svg`, `.png`) |
| Primary figure source data | `exp1_alignment_transfer/outputs/paper_candidate/figures/data/fig_exp1_alignment_transfer_data.csv` |
| Published appendix — delay / state coupling | `.../figures/appendix/pdf/exp1_appendix_delay_coupling_diagnostics.pdf` from `figures/data/fig_exp1_delay_survival_data.csv`, `fig_exp1_state_coupling_data.csv` |
| Published appendix — reversal / trajectory | `.../figures/appendix/pdf/exp1_appendix_reversal_trajectory_diagnostics.pdf` from `fig_exp1_reversal_margin_data.csv`, `fig_exp1_route_trajectory_data.csv` |
| Published appendix — targeted validation | `.../figures/appendix/pdf/exp1_appendix_targeted_validation.pdf` from `targeted/fig_exp1_targeted_validation_data.csv` |
| **New** targeted appendix candidate (preview only) | `exp1_appendix_targeted_cancellation_and_utilization` from `exp1_alignment_transfer/outputs/full/targeted/exp1_targeted_cancellation_summary.csv` and `exp1_alignment_transfer/outputs/full/derived/exp1_regret_stability_utilization_summary.csv` |
| Main table | `.../tables/tex/tab_exp1_mechanism_summary.tex`, `tab_exp1_mechanism_protocol.tex` |

### Exact PASS status

`exp1_alignment_transfer/outputs/full/targeted/exp1_targeted_validation_report.json`:

- `status = PASS`, `analysis_tier = targeted`, `run_tier = full`, **`paper_result = false`**
- Cancellation gates: `C1_pure_shared = true`, `C2_shared_amplitude_invariance = true`,
  `C3_profile_invariance = true`, `C4_delta_margin_ratio = true`,
  `C5_choice_threshold = true`, `C6_no_clipping_no_learner = true`
- `max_numerical_deviation = 2.220446049250313e-16`, `tolerance = 1e-10`, `n_cells = 1440`, `n_seeds = 30`
- `C4`: native identity `delta_t = alpha_dep * mu_t` with `ratio_tol = 1e-9`,
  `roundoff_safety_factor = 32`, native pass `true`, conditioned pass `true`
- `horizon_route_map.stability_inequality_pass = true`, `utilization_defined_rows = 90`

### Cancellation finding

Mean action-gap defect χ (`metric_id = mean_chi`) on the frozen targeted grid
(`shared_profile ∈ {static_shared, state_varying_shared}` ×
`alpha_shared ∈ {0, 0.05, 0.10, 0.20}` × `alpha_dep ∈ {0, 0.5, 0.99, 1.0, 1.01, 1.5}`):

| `alpha_dep` | χ | distinct values across the 8 profile×amplitude cells |
|---|---|---|
| 0.00 | 0.0 | 1 |
| 0.50 | 0.0 | 1 |
| 0.99 | 0.0 | 1 |
| 1.00 | 0.5 | 1 |
| 1.01 | 1.0 | 1 |
| 1.50 | 1.0 | 1 |

The shared term cancels exactly: for every `alpha_dep` the eight
profile × amplitude cells carry **one** distinct χ value. The absolute
action-wise level error, by contrast, tracks the shared amplitude
(≈ 0.05 / 0.10 / 0.20 for `alpha_shared` = 0.05 / 0.10 / 0.20) and is
essentially flat in `alpha_dep`. Levels move; action comparisons do not.

### Realized stability utilization

- **Definition:** `regret_stability_utilization = abs(R_c - R_r) / A`, where `A` is the alignment budget.
- **Defined / undefined rule:** defined only when the alignment budget is numerically above the existing stability tolerance. Otherwise the value is `NaN` with `utilization_defined = False`. Undefined rows are **never** reported as a manufactured zero.
- **Summary values** — `derived/exp1_regret_stability_utilization_summary.csv`, `route_id = arrival_assigned`, `n_defined = 30` of `n_total_seeds = 30`, 95% seed-bootstrap interval, 2000 repetitions:

| Mechanism | estimate | ci_lower | ci_upper |
|---|---|---|---|
| zero_delay | undefined | — | — |
| exact_valid_shift | undefined | — | — |
| geometric_delay | 0.1256766378398699 | 0.1238676267585824 | 0.1274656003083025 |
| mixture_delay | 0.1249224390050025 | 0.1229843589287260 | 0.1268268356740098 |
| state_coupled_delay | 0.1218197990899347 | 0.1201454588680522 | 0.1235510839016651 |
| systematic_misbinding | 0.2777777777777778 | 0.2777777777777778 | 0.2777777777777778 |

On `route_id = source_bound` all six mechanisms have `n_defined = 0`: the
quantity is undefined there, not zero.

### Systematic-misbinding horizon values

`targeted/exp1_targeted_horizon_summary.csv`, `metric_id = structural_regret_rate`:

| Horizon T | arrival_clock | source_round |
|---|---|---|
| 1000 | 0.179898 [0.177094, 0.182642] | 0.155453 [0.153055, 0.157800] |
| 5000 | 0.178471 [0.177272, 0.179631] | 0.107082 [0.106546, 0.107632] |
| 10000 | 0.178337 [0.176707, 0.180064] | 0.086073 [0.085693, 0.086469] |

Cumulative `structural_regret` in the same source: arrival_clock 179.897942 /
892.355144 / 1783.369136; source_round 155.453498 / 535.410288 / 860.725103.

### Interpretation boundary (strict)

The supported statement is exactly:

> A time/state-varying route-error component can change loss levels without
> changing action comparisons when it remains action-invariant within each
> round; action-dependent residual variation is what enters the action-gap
> defect. Realized stability utilization reports how much of the available
> alignment budget appears as same-sequence structural-vs-route regret
> discrepancy on a realized controlled path.

It does **not** establish that arbitrary state variation, arbitrary delayed
routing, arbitrary history dependence, or arbitrary nonlinear aggregation is
harmless.

### Prohibited

The old additive decomposition

```
delay component + validity component = total
```

**must not be used.** It is not supported by the frozen sources and the targeted
round did not re-derive it.

### Proposed placement

- **Main text:** the existing 1×3 main figure and `tab_exp1_mechanism_summary`, unchanged in claim scope.
- **Appendix:** the targeted cancellation + utilization figure, **and only there**. It must remain `paper_result = false` until an explicit promotion decision.
- **Do not claim:** any general "state variation is harmless" statement; any identification of route error with delay magnitude; any use of utilization where the alignment budget is zero.

### Publication-mode prerequisite (action required before any promotion)

`exp1_alignment_transfer/outputs/paper_candidate/targeted/` does **not** contain
`exp1_targeted_cancellation_summary.csv` (nor the cancellation invariants JSON);
those exist only in `outputs/full/targeted/`. The utilization summary is present
in `paper_candidate` and is byte-identical to the `full` copy. Consequently a
`render --mode publication` run would fail with `FileNotFoundError` on the
cancellation source. Promoting the cancellation artifacts into the
paper-candidate bundle is a scientific-artifact change and was **not** performed.

---

## Exp2 — Attribution sensitivity in delayed conversion logs

### Paths

| Role | Path |
|---|---|
| Canonical main figure | `publication/CR-EXP-OUTPUT-V1/exp2_real_delayed_conversion_logs/figures/main/pdf/figure_exp2_attribution_sensitivity.pdf` |
| Figure source data | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/figures/figure_exp2_attribution_sensitivity_source.csv` |
| Appendix figure | `.../figures/appendix/pdf/exp2_appendix_ambiguity_heatmap.pdf`, `exp2_appendix_delay_distribution.pdf`, `exp2_appendix_pairwise_topk.pdf` |
| Tables | `.../tables/tex/tab_exp2_cohort_flow.tex`, `tab_exp2_robustness.tex`, `tab_exp2_pairwise_appendix.tex`, `tab_exp2_attribution_route_definitions.tex` |

### Headline supported finding

Ambiguity between the arrival timeline and a source attribution is **localized
and route-dependent**. Comparing the arrival anchor against each source
attribution (`allocation_tv`): first-click 0.138310, last-click 0.102917,
linear source-cell 0.118943, time-decay source-cell 0.109161. Comparing two
source attributions against each other, the same statistic is much smaller:
First–Last 0.061768, First–Linear 0.032168, First–Decay 0.049638,
Last–Linear 0.032788. Kendall tau-b moves the same way (arrival anchor
0.482419–0.589145 versus within-source 0.717426–0.854508).

Present this as a **sensitivity analysis**, not as causal policy-value
identification.

### Uncertainty semantics

The intervals are `*_resampling_q025` / `q500` / `q975` from UID resampling
(`resampling_range_method`, `formal_ci_validated` fields in the source table).
They are **resampling sensitivity ranges, not confidence intervals**, and must
not be labelled as CIs.

### Interpretation boundary

Attribution choice changes the ranking diagnostic in a way that is specific to
the compared routes. The analysis does not identify a true attribution and does
not estimate a causal effect of attribution on deployment value.

---

## Exp3 — Sequential recommendation under delayed feedback

### Paths

| Role | Path |
|---|---|
| Canonical main figure | `publication/CR-EXP-OUTPUT-V1/exp3_sequential_recommendation_delayed_feedback/figures/main/pdf/exp3_main_score_gap_ranking.pdf` |
| Figure source data | `exp3_sequential_recommendation_delayed_feedback/paper_candidate/figures/data/exp3_main_score_gap_ranking_data.csv` |
| Appendix figures | `.../figures/appendix/pdf/exp3_appendix_support_and_dependence.pdf`, `exp3_appendix_carrier_and_gap_diagnostics.pdf`, `exp3_appendix_calibration_and_selection.pdf` |
| Tables | `.../tables/tex/exp3_primary_route_results.tex`, `exp3_paired_ranking_contrast.tex`, `exp3_support_coverage.tex`, `exp3_action_space_coverage.tex`, `exp3_ridge_history_cv.tex`, `exp3_resampling_structure_diagnostics.tex` |

### Exact source values behind the predictive-vs-decision contrast

`tables/exp3_primary_route_results.csv`:

| route | pooled Spearman | pooled MAE | max held-out gap error | sign agreement | top-action agreement |
|---|---|---|---|---|---|
| arrival_carrier | 0.610160 | 0.128489 | 0.641791 | 0.764632 | 0.335294 |
| history_mean_control | 0.714376 | 0.106061 | 0.385917 | 0.867371 | 0.517647 |
| ridge_proxy | 0.695784 | 0.105065 | 0.399623 | 0.856586 | 0.447059 |

The contrast that matters: `ridge_proxy` has the **lowest** predictive error
(MAE 0.105065, max held-out gap error 0.399623) yet a **lower** top-action
agreement (0.447059) than `history_mean_control`, whose predictive error is
higher (MAE 0.106061, max gap error 0.385917) but whose top-action agreement is
higher (0.517647). Lower predictive error therefore does not imply better
decision recovery. These are the only values that may be annotated on the
figure; no new decision metric was added.

### Uncertainty semantics

The ranges are `*_sensitivity_lower` / `*_sensitivity_upper` produced by
resampling (`uncertainty_role`, `formal_ci_validated`). They are **sensitivity
ranges, not formal confidence intervals**; the main-figure contract records
`uncertainty_role = "sensitivity range, not confidence interval"`.

### Interpretation boundary

The experiment compares sequential routes on supported cells. It does not
establish deployment value, does not validate the ridge proxy as a causal
estimator, and the arrival carrier is a misbinding control rather than a
recommended policy.

---

## Exp4 — Recoverability boundary diagnostic

### Paths

| Role | Path |
|---|---|
| Canonical main figure | `publication/CR-EXP-OUTPUT-V1/exp4_controlled_route_audit/figures/main/pdf/fig_exp4_route_alignment_and_audit_reliability.pdf` |
| Route / population alignment source | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/derived/module_a/exp4_module_a_population_summary.csv` |
| Audit reliability source | `.../derived/module_b/exp4_module_b_audit_performance.csv`, `exp4_module_b_weight_diagnostics.csv` |
| Calibration source | `.../derived/module_c/exp4_module_c_control_summary.csv`, `exp4_module_c_correspondence_checks.csv`, `exp4_module_c_parameter_recovery.csv` |
| Appendix figures | `.../figures/appendix/pdf/exp4_appendix_route_alignment_detail.pdf`, `exp4_appendix_audit_support.pdf`, `exp4_appendix_calibration_diagnostics.pdf` |
| Tables | `.../tables/tex/tbl_exp4_calibration_controls.tex`, `tbl_app_exp4_audit_performance.tex`, `tbl_app_exp4_paired_contrasts.tex`, `tbl_app_exp4_parameters.tex` |

### Route / audit / calibration separation

Three distinct layers must stay distinct:

1. **Route information / population alignment** (Module A) — how much route-label
   structure survives as a function of `q_route` and the noise scale σ.
2. **Audit evidence / estimator reliability** (Module B) — bias and RMSE of each
   audit design against the full-population reference.
3. **Calibration / recoverability** (Module C) — raw versus out-of-fold
   calibrated pairwise discrepancy, and how much of the parameter is recovered.

`recoverability != identification` must remain readable. Calibration is a
recoverability control, not an identification claim.

### Calibration-control finding

`derived/module_c/exp4_module_c_control_summary.csv`:

| Control | raw pairwise discrepancy | OOF-calibrated | recoverability |
|---|---|---|---|
| affine_linked | 0.240765 | 0.045827 | 0.809446 |
| blocked_correspondence_destroyed | 0.396094 | 0.293073 | 0.259830 |
| nonlinear_monotone (appendix only) | 0.046036 | 0.031784 | 0.309092 |

A large calibrated reduction coexists with low recoverability (the
correspondence-destroyed control drops from 0.396094 to 0.293073 while
recoverability stays at 0.259830). Lower calibrated discrepancy is therefore not
evidence that the route is valid.

Audit reliability (`derived/module_b/exp4_module_b_audit_performance.csv`, bias /
RMSE ranges across evidence rates): full-population audit exactly 0 / 0;
`ambiguity_selective_unweighted` up to 0.031627 / 0.031934;
`ambiguity_selective_ipw` up to 0.000177 / 0.002623;
`mcar_unweighted` up to 0.000026 / 0.002829.

### Interpretation boundary

Module A/B/C outputs are diagnostics of information, estimator reliability, and
recoverability. Nothing here identifies the true route error on real data, and
calibration recoverability must not be presented as identification.

---

## Cross-experiment notes

- Exp2's main PNG is byte-identical to the published bundle after this session's
  preview render: no presentation change was made to Exp2.
- The Exp1 targeted appendix candidate is preview-only and requires the
  promotion decision described above before it can enter the publication bundle.
- Uncertainty wording: Exp1 uses 95% seed-bootstrap intervals; Exp2 and Exp3 use
  resampling sensitivity ranges that are **not** confidence intervals; Exp4
  Module B uses estimate ± 1.96 MCSE. These must not be described uniformly.
