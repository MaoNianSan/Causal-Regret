# Experiment I/O Contract — Causal-Regret Submission Companion

This document is the single machine-and-reviewer readable contract for the four experiments in this repository.
It states, per experiment: the scientific purpose, the input contract, the exact execution commands (taken from the real CLI parsers), the output contract, the paper-facing metrics and their uncertainty semantics, the unique canonical paper result, and the interpretation boundary.

The repository also provides a machine-checkable validator: `scripts/validate_submission_repository.py` (see `REPRODUCE.md`, section "Validate published results"). This document and that validator agree by construction; the validator is read-only and never runs experiments.

Reference hashes:
- Exp1 frozen scientific-generation config hash: `483df70d6daceef6ffbb42b5c59d98e50373a606a8d9d6e9da8f317eee8af914`
- Exp4 frozen scientific config hash: `9a0a87ecc64ead7528cbd43d299e26c64ea8499f9d54852e0cc45d7e061364a7`

General conventions
- `full-sample estimates` are the primary readouts.
- `scientific source lineage` (frozen scientific run that produced the numbers) and `presentation source lineage` (presentation-layer rebuild of paper-facing figures) are recorded separately in figure metadata and are never conflated.
- Rebuilding paper-facing figures from a promoted frozen source does **not** re-run any experiment.
- Exp2/Exp3 use external logged datasets that are **not redistributed** by this repository; see `DATA.md` for download instructions.

---

## Experiment 1 — Controlled Alignment and Regret Transfer

### Scientific purpose
Whether action-gap alignment between the operational feedback route and the structural benchmark, rather than delay magnitude alone, governs structural regret transfer.

### Input contract
- **Input type**: controlled simulator (no external data). Scientific configuration is frozen in `exp1_alignment_transfer/config.py` (CONFIG_VERSION `1.2`).
- **Observation / unit**: simulator round `t`, horizon `T = 5000`, `K = 10` actions, `30` shared evaluation seeds; `500`-round AR burn-in and `100` prehistory rounds; `20` disjoint calibration seeds.
- **Delay mechanisms** (code identifiers `mechanism_id`): `zero_delay`, `exact_valid_shift`, `geometric_delay`, `mixture_delay`, `state_coupled_delay`, `systematic_misbinding`.
- **Evaluation routes**: `source-round` is the structural-benchmark route (binds factual feedback to the generating source round); `arrival-assigned` is the operational comparison route (binds feedback to the arrival clock round). Panel (b) of the main figure uses a route-greedy diagnostic policy, so route regret `R_T^r = 0` by construction.
- **Preprocessing / calibration**: frozen calibration artifact (`calibrate.py --force` regenerates only the frozen calibration lineage); scientific reuse is gated by stage-aware provenance.
- **Targeted sweeps**: shared-prefix horizons `{1000, 5000, 10000}`; generated mean delays `{5, 15, 30}`; matched shared-vs-action-dependent cancellation grid (see *Targeted diagnostics*).
- **Config location / hash**: `exp1_alignment_transfer/config.py`; frozen scientific-generation config hash `483df70d…`.
- **Canonical input**: none external; all inputs are the frozen committed configuration and calibration artifacts.

### Execution contract (from real CLI parsers)
```bash
# Fast tier (smoke / engineering gate only, never paper results)
python exp1_alignment_transfer/main.py fast
python exp1_alignment_transfer/self_check.py --run fast
python exp1_alignment_transfer/targeted.py --run fast
python exp1_alignment_transfer/plot_main.py --run fast
python exp1_alignment_transfer/plot_appendix.py --run fast

# Formal full run and validation
python exp1_alignment_transfer/main.py full
python exp1_alignment_transfer/self_check.py --run full
python exp1_alignment_transfer/targeted.py --run full
python exp1_alignment_transfer/plot_main.py --run full
python exp1_alignment_transfer/plot_appendix.py --run full

# Reporting-only rebuild (reuses verified scientific source; no scientific rerun)
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild reporting

# Paper promotion (paper-facing; requires human authorization memo, see CHANGE_MEMO_EXP1_005.md)
python exp1_alignment_transfer/promote.py --run full --dry-run
python exp1_alignment_transfer/promote.py --run full --force
```
Commands are exactly the flags accepted by each parser (`main.py {fast,full} [--force]`, `self_check.py/targeted.py/plot_*.py {fast,full} | --run {fast,full}`, `reconcile.py --source-run --rebuild {validation,aggregation,reporting,downstream}`, `promote.py --run full [--dry-run] [--force]`).

### Output contract
- **Canonical output root**: `exp1_alignment_transfer/outputs/paper_candidate/` (paper-facing; `outputs/full/` is the scientific full run and is intentionally not tracked).
- **Promotion manifest**: `exp1_alignment_transfer/outputs/paper_candidate/exp1_promotion_manifest.json`; promotion status `exp1_alignment_transfer/status/paper_promotion_status.json`.
- **Primary derived CSV**: `outputs/paper_candidate/derived/exp1_primary_summary.csv`; mechanism table `outputs/paper_candidate/tables/tab_exp1_mechanism_summary.csv`.
- **Main figure ID**: `fig_exp1_alignment_transfer`; long-form CSV at `outputs/paper_candidate/figures/data/fig_exp1_alignment_transfer_data.csv`.
- **Appendix figure IDs**: `fig_exp1_delay_verification`, `fig_exp1_reversal_margin`, `fig_exp1_route_trajectory`, `fig_exp1_state_coupling` (paper-candidate set; publication composites in `publication/CR-EXP-OUTPUT-V1/exp1_alignment_transfer/figures/appendix/`).
- **Main table**: `tables/tab_exp1_mechanism_summary.tex`.
- **Provenance / validation JSON**: `metadata/exp1_run_lineage.json`, `metadata/exp1_stage_provenance.json`, `checks/exp1_validation_report.json`, `targeted/exp1_targeted_validation_report.json`.

### Paper-facing metrics
| metric_id | estimand | unit | aggregation | uncertainty semantics |
|---|---|---|---|---|
| `alignment_budget_rate` | `A_T^arr/T` | unitless rate | 30-seed mean | 95% seed-bootstrap interval |
| `structural_regret_rate` | `R_T^c/T` | unitless rate | 30-seed mean | 95% seed-bootstrap interval |
| `transfer_bound_rate` | `(R_T^r + A_T^r)/T` | unitless rate | 30-seed mean | 95% seed-bootstrap interval |
| `arrival_minus_source_regret_rate` | paired binding contrast | unitless rate | 30-seed paired mean | 95% seed-bootstrap interval |
| `generated_mean_delay` | mean delay | rounds | 30-seed mean | 95% seed-bootstrap interval |

Uncertainty: `95% seed-bootstrap interval` computed over the 30 shared seeds with 2000 bootstrap repetitions; structural rounds are not treated as independent bootstrap observations. Deterministic / structural endpoints (e.g., zero-delay and exact-valid zero rates) are reported without artificial intervals.

### Targeted diagnostics (route-map-only, non-promoted)
- **Targeted output root**: `exp1_alignment_transfer/outputs/<tier>/targeted/` with `<tier> ∈ {fast, full}`. Every targeted row carries `paper_result = false`; targeted outputs are never paper-promoted without separate human authorization.
- **Horizon route-map artifacts**: `targeted/exp1_targeted_horizon_route_seed_metrics.csv` (per seed × horizon × route) and `targeted/exp1_targeted_horizon_route_summary.csv`. Horizon levels stay frozen at `T = {1000, 5000, 10000}` and the route quantities are computed on the *same* generated bundle as the learner horizon check. In the summary, `manuscript_facing = true` only for `route_id = arrival_assigned`; source-bound rows are retained for consistency.
- **Cancellation artifacts**: `targeted/exp1_targeted_cancellation_sweep.csv`, `targeted/exp1_targeted_cancellation_summary.csv`, `targeted/exp1_targeted_cancellation_invariants.json`; the overall `cancellation_sweep` block (gates C1–C6 plus `max_numerical_deviation`) and the PASS/FAIL status live in `targeted/exp1_targeted_validation_report.json`.
- **Cancellation grid (frozen)**: `shared_profile ∈ {static_shared, state_varying_shared}`, `alpha_shared ∈ {0.00, 0.05, 0.10, 0.20}`, `alpha_dep ∈ {0.00, 0.50, 0.99, 1.00, 1.01, 1.50}` → 48 cells per seed. The matched invariance reference is `(shared_profile = static_shared, alpha_shared = 0.00)` at fixed `(seed, alpha_dep)`.
- **Shared profile definitions (frozen)**: on the frozen eligible-round support (exactly one structural optimum, finite positive margin), `static_shared` adds `c_t = 1` and `state_varying_shared` adds `c_t = 1 + S_t`, where `S_t` is the already generated `structural_state` (so `c_t ∈ [0, 2]`). The shared term is added identically to every action of a round and is never normalized by any statistic computed from evaluation outcomes.
- **Action-dependent residual**: `u_t(best) = +d/2`, `u_t(competitor) = -d/2` with `d = alpha_dep * mu_t`, where `mu_t` is the structural margin between the unique best action and the deterministic nearest competitor (the existing margin-sweep construction). No clipping is applied and no learner is called; `L_route[t, a] = L[t, a] + alpha_shared * c_t + u_t[a]` is a route-map diagnostic, not an EXP3 loss.
- **C4 numerical rule (native scale, frozen before the run)**: the hard gate is the native identity `delta_t = alpha_dep * mu_t` with tolerance `ratio_tol * mu_t + roundoff_floor`, where `ratio_tol = 1e-9` (unchanged margin-sweep value), `roundoff_floor = 32 * eps * max(1, max|L_row|, max|L_route_row|)`, `eps = 2.220446049250313e-16`, and the round-off safety factor `32` is a declared frozen constant. The normalized ratio `delta_t / mu_t` is gated only on ratio-conditioned rounds (`mu_t >= roundoff_floor / ratio_tol`) against `ratio_tol + roundoff_floor / mu_t`; elsewhere it is kept as a diagnostic with `ratio_gate_applicable = False` and never determines acceptance. `C4 PASS = native identity PASS AND conditioned ratio PASS`. The invariant JSON reports `c4_native_identity_pass`, `c4_native_max_abs_error`, `c4_native_max_tolerance_ratio`, `c4_ratio_conditioned_pass`, `c4_ratio_conditioned_rounds`, `c4_ratio_unconditioned_rounds`, `c4_ratio_condition_threshold_min/max`, `c4_ratio_max_error_conditioned`, `c4_ratio_max_error_all_diagnostic`, `ratio_tol`, `roundoff_safety_factor` and `machine_eps`; the sweep CSV keeps `max_delta_over_mu_deviation` as a per-cell ratio diagnostic only.
- **Realized stability utilization denominator rule**: `regret_stability_utilization = abs(R_c - R_r) / A` is defined only when `A > A_tol`, with `A_tol = stability_tolerance_rate * T` returned by the existing `regret_stability_slack(R_c, R_r, A, T)` helper. At or below the tolerance the row keeps `regret_stability_utilization = NaN` with `utilization_defined = False` (never a manufactured zero); defined rows satisfy `0 <= u <= 1 + A_tol / A`.
- **Utilization artifacts**: `outputs/paper_candidate/derived/exp1_regret_stability_utilization.csv` plus `exp1_regret_stability_utilization_summary.csv` (paper-candidate side; the same names appear under any run tier's `derived/`). Per-row columns: `seed`, `mechanism_id`, `route_id`, `n_rounds`, `structural_regret`, `route_regret`, `alignment_budget`, `regret_stability_slack_rate`, `regret_stability_tolerance`, `alignment_budget_tolerance`, `regret_stability_utilization`, `utilization_defined`, `paper_result`, plus the source run / provenance identifiers carried through from the frozen seed-level route maps.
- **Uncertainty semantics for the utilization summary**: the summary aggregates only rows with `utilization_defined = True`. The primary estimate is the **mean of seed-level ratios** — never `abs(mean(R_c) - mean(R_r)) / mean(A)` — reported with the repository's existing seed-bootstrap convention (95% level; 2000 repetitions full, 200 fast for the fast tier). Mechanisms or routes whose alignment budget is numerically zero keep their row with `n_defined = 0` and `estimate = CI = NaN`.
- **Metric registry**: `regret_stability_utilization` is intentionally not added to the primary seed-metric registry `METRICS` in `src/contracts.py`. That registry describes the primary scientific seed-level output schema; this is a targeted/derived reporting quantity, so the primary schema is not broadened.

### Canonical paper result
`exp1_alignment_transfer/outputs/paper_candidate/` — promoted from full run `exp1_alignment_transfer:full:2026-08-17T06:28:21.157011+00:00` (code commit `23199c48`), `paper_result = true`, `run_tier = paper`.

### Interpretation boundary
Separates complete-map route validity from learner-level update allocation. It does **not** prove the stability theorems (those are proven in the paper's theory sections); the alignment budget is a valid but conservative **diagnostic bound**, not an exact prediction of realized regret.

---

## Experiment 2 — Attribution Sensitivity in Delayed-Conversion Logs

### Scientific purpose
Whether a fixed delayed-conversion log uniquely determines source-time credit allocation, and how much the attribution rule changes aggregate credit and cell ordering.

### Input contract
- **Input type**: external Criteo delayed-conversion log (not redistributed; see `DATA.md`).
- **Observation / unit**: impression = potential source event; decision cell `c = (campaign, source calendar day)`; analysis unit for resampling is `user_id` (UID cluster).
- **Delay window**: 7-day candidate window before conversion (fully observed lookback only); robustness under a 30-day window.
- **Preprocessing / filter**: temporal filters; minimum impressions per eligible cell = 50; retained complete-lookback journeys.
- **Attribution routes** (paper term ↔ code identifier from canonical CSV `condition_id`):
  | paper term | canonical code identifier |
  |---|---|
  | First-touch | `First-click-or-touch attribution` |
  | Last-touch | `Last-click-or-touch attribution` |
  | Linear credit | `Linear source-cell credit` |
  | Time-decay credit | `Time-decay source-cell credit` |
  | arrival accounting anchor | constructed arrival-time accounting anchor |
- **Metrics**: allocation TV `TV(Q_r,Q_r')`, Kendall's `τ_b`, top-k overlap (appendix).
- **Resampling**: UID-cluster bootstrap, 1000 repetitions, frozen full-sample support.
- **Data boundary**: `DOWNLOAD_REQUIRED` (not redistributed).

### Execution contract (from real CLI parsers)
```bash
# Fast tier (smoke)
python exp2_real_delayed_conversion_logs/main.py fast

# Formal full run (Criteo input under DATA.md path)
python exp2_real_delayed_conversion_logs/main.py full --n-bootstrap 1000 --n-jobs 4

# Cohort check
python exp2_real_delayed_conversion_logs/main.py cohort-check

# Paper promotion
python exp2_real_delayed_conversion_logs/promote.py --run-id exp2-full-20260807T111616+0800
```
Commands match `main.py {fast,full,cohort-check} [--config] [--input] [--n-bootstrap] [--n-jobs]` and `promote.py --run-id <id>`.

### Output contract
- **Canonical output root**: `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/`.
- **Main figure ID**: `figure_exp2_attribution_sensitivity` (source CSV `figures/figure_exp2_attribution_sensitivity_source.csv`, metadata `…_metadata.json`, PDF/SVG/PNG).
- **Main panel metrics**: route-vs-arrival Allocation TV; route-vs-arrival Kendall `τ_b`; pairwise-route Allocation TV; pairwise-route Kendall `τ_b`.
- **Appendix figure IDs**: `figure_exp2_ambiguity_mechanism`, `figure_exp2_delay_appendix`, `figure_exp2_pairwise_appendix`.
- **Tables**: `table_exp2_cohort_flow`, `table_exp2_primary_results`, `table_exp2_pairwise_appendix`, `table_exp2_robustness_summary`.
- **Provenance**: `run_manifest.json`; audit JSON under `audit/`.

### Paper-facing metrics
- `allocation_tv`, `kendall_tau_b` (metric_id in the long-form CSV).
- Uncertainty: **empirical 2.5%–97.5% UID-cluster resampling sensitivity range**; explicitly **NOT a confidence interval** (non-smooth function of high-dimensional allocations; active support held fixed across resamples).

### Canonical paper result
`exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` — `paper_result = true`.

### Interpretation boundary
Attribution sensitivity on a fixed logged cohort. It does **not** identify causal attribution, uplift, policy value, or structural regret.

---

## Experiment 3 — Delayed-Feedback Recommendation and Decision Recovery

### Scientific purpose
Whether held-out score recovery transfers to pairwise action-gap recovery and logged-supported ranking / decision recovery.

### Input contract
- **Input type**: external KuaiRand-1K logged recommendation data (not redistributed; see `DATA.md`).
- **Observation / unit**: user–video exposure at source time `t`; constructed six-hour target `Y_{u,t}^{(6h)}`; audit unit `i = (day, user-hash group)`, 85 audit units.
- **Temporal split**: history April 8–21, 2022; evaluation April 22–May 8, 2022; quarantine outside split boundaries (< 0.1% tolerance).
- **Action space**: frozen top-20 tag action space (85.0% of evaluation exposure mass); support rule ≥ 500 source events per fold–audit-unit–action cell.
- **Routes** (paper term ↔ code identifier):
  | paper term | code identifier | role |
  |---|---|---|
  | Arrival carrier | `arrival_carrier` | deliberate source-misbinding control |
  | Historical mean | `history_mean_control` | simple history control |
  | Ridge proxy | `ridge_proxy` | history-fitted proxy route (penalty α=30, selected by rolling temporal validation on history split) |
- **Cross-fitting**: two deterministic reference folds, actions selected on one fold, evaluated on the opposite fold.
- **Resampling**: user-cluster bootstrap, 1000 repetitions; supported action sets and cross-fitted selections recomputed within each resample.
- **Data boundary**: `DOWNLOAD_REQUIRED` (not redistributed).

### Execution contract (from real CLI parsers)
```bash
# Fast tier (smoke; falls back to synthetic fixture without inputs)
python exp3_sequential_recommendation_delayed_feedback/main.py fast

# Formal full run
python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12

# Self-check (validation only)
python exp3_sequential_recommendation_delayed_feedback/main.py self-check --mode full --run-id exp3-full-20260807T072340Z

# Paper promotion
python exp3_sequential_recommendation_delayed_feedback/promote.py --run-id exp3-full-20260807T072340Z
```
Commands match `main.py {fast,full} [--n-jobs] [--input-root] [--output-dir]`, `main.py self-check --mode {fast,full} [--run-id]`, `promote.py --run-id <id>`.

### Output contract
- **Canonical output root**: `exp3_sequential_recommendation_delayed_feedback/paper_candidate/` (from full run `exp3-full-20260807T072340Z`).
- **Main figure ID**: `exp3_main_score_gap_ranking` (2×3: score / gap / ranking).
- **Main metrics**: `pooled_supported_cell_spearman`, `pooled_supported_cell_mae`, `maximum_heldout_reference_pair_gap_error`, `heldout_reference_pair_sign_agreement`, `top_action_agreement_with_fold_reference`, `ridge_over_historical_paired_value_gain`.
- **Appendix composites** (publication): `exp3_appendix_support_and_dependence`, `exp3_appendix_carrier_and_gap_diagnostics`, `exp3_appendix_calibration_and_selection`.
- **Tables**: `exp3_primary_route_results`, `exp3_paired_ranking_contrast`, `exp3_support_coverage`, `exp3_action_space_coverage`, `exp3_resampling_structure_diagnostics`, `exp3_ridge_coefficients`, `exp3_ridge_history_cv`.
- **Provenance**: `manifest.json`.

### Paper-facing metrics and uncertainty
- Uncertainty: **empirical 2.5%–97.5% user-cluster resampling sensitivity range**; explicitly **NOT a confidence interval** (`formal_ci_validated = false` in the paired-contrast table).
- The Ridge-minus-Historical paired value gain (−0.0149 full sample; range [−0.0347, 0.0075]) **crosses zero**: the results do **not** support a Ridge superiority claim.

### Canonical paper result
`exp3_sequential_recommendation_delayed_feedback/paper_candidate/` — `paper_result = true`.

### Interpretation boundary
Characterizes recovery on observed logged support. It is not off-policy evaluation, deployment-value estimation, or structural causal validity.

---

## Experiment 4 — Route Alignment, Audit Reliability, and Recoverability

### Scientific purpose
To separate three empirical properties under a controlled simulator: population route alignment, reliability of finite audit evidence, and discrepancy reduction within a prespecified calibration family.

### Input contract
- **Input type**: controlled simulator (no external data). Frozen scientific configuration hash `9a0a87ecc64ead7528cbd43d299e26c64ea8499f9d54852e0cc45d7e061364a7`.
- **Frozen parameters** (from `tables/tbl_app_exp4_parameters`): `K = 10` actions, state dimension `3`, horizon `T = 5000`, warmup `W = 250`, `100` shared structural seeds, delay–state coupling `β = 2.0` (primary), target mean delay 2, max candidate delay 20, feedback noise SD 0.009, root seed `2026080604`.
- **Module A (population alignment)**: `q_route ∈ {0, 0.3, 0.7, 1.0}`; `proxy_noise_sd ∈ {0.0, 0.10, 0.25, 1.00}`; **primary proxy noise = 0.25**.
- **Module B (audit)**: horizon 2000, warmup 100, 1000 replications, audit evidence rates `{0.1, 0.3, 0.5, 1.0}` (1.0 = full-information endpoint), fixed `q_route = 0.3`, `proxy_noise_sd = 0.25`.
- **Audit mechanisms** (code identifiers): `mcar_unweighted`, `ambiguity_selective_unweighted`, `ambiguity_selective_ipw`, and `full_population` (deterministic endpoint).
- **Module C (calibration)**: affine-linked positive control, temporally blocked correspondence-destroyed control, nonlinear-monotone control; OOF affine calibration (5 temporal folds), calibration seeds `50000..50019`, `proxy_calibration_noise_sd = 0.25`.

### Execution contract (from real CLI parsers)
```bash
# Fast / middle / formal full tiers
python exp4_controlled_route_audit/main.py fast --n-jobs 4
python exp4_controlled_route_audit/main.py middle --n-jobs 8
python exp4_controlled_route_audit/main.py full --n-jobs 8   # refuses dirty Exp4 worktree / unresolvable commit

# Downstream stages for a completed run
python exp4_controlled_route_audit/main.py validate --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py aggregate --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py plot --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py tables --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py report --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py provenance --run-dir outputs/runs/<run_id>

# Stage-aware selective rebuild (no scientific rerun)
python exp4_controlled_route_audit/main.py reconcile --run-dir outputs/runs/<run_id> --rebuild reporting

# Implementation status report
python exp4_controlled_route_audit/main.py status

# Paper promotion (claims gate is explicit)
python exp4_controlled_route_audit/promote_results.py --run-dir outputs/runs/<run_id> --approve-claims --dry-run
python exp4_controlled_route_audit/promote_results.py --run-dir outputs/runs/<run_id> --approve-claims
```

### Output contract
- **Canonical output root**: `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` (result schema `exp4_controlled_route_audit_v3`).
- **Main figure ID**: `fig_exp4_route_alignment_and_audit_reliability` (2×2).
  - Panel (a): **primary metric `D_pair`** = `mean_pairwise_gap_discrepancy_mean` (mean pairwise gap discrepancy). Legacy `population_action_gap_defect` / `mean_round_max_gap_defect` are **excluded** from panel (a) and remain secondary diagnostics only.
  - Panel (b): audit `bias` (estimate ± 1.96 MCSE).
  - Panel (c): audit `rmse` (estimate ± 1.96 MCSE).
  - Panel (d): `raw_pairwise_discrepancy` vs `oof_calibrated_pairwise_discrepancy`, with `recoverability`.
- **Appendix composites** (publication): `exp4_appendix_route_alignment_detail`, `exp4_appendix_audit_support`, `exp4_appendix_calibration_diagnostics`.
- **Tables**: `tbl_exp4_calibration_controls`, `tbl_app_exp4_paired_contrasts`, `tbl_app_exp4_audit_performance`, `tbl_app_exp4_parameters`.
- **Provenance**: `logs/run_config.json`, `logs/exp4_result_status.json`, `logs/output_manifest.json`, `logs/exp4_run_lineage.json`, `logs/exp4_stage_provenance.json`, `checks/exp4_promotion_check.json`.

### Paper-facing metrics and uncertainty
- Panel (a): **paired-seed frozen interval** over the shared structural seeds; `q_route = 1` and the full-population audit endpoint are deterministic controlled endpoints reported **without intervals**.
- Panels (b)–(c): estimate ± 1.96 Monte Carlo standard errors (1000 independent audit replications).
- **Calibration recoverability ≠ route validity certificate**: positive recovery within the prespecified affine family does not establish structural route validity.

### Canonical paper result
`exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` — `paper_result = true`, `paper_promotion = PASS`, schema v3.

### Interpretation boundary
Population alignment, audit reliability, and calibratability are distinct diagnostics. Known simulated inclusion probabilities and positive affine recoverability are controlled diagnostics; neither establishes structural validity under an unknown real-world evidence mechanism.

---

## Cross-cutting answers the reviewer needs

- **What is the unit?** Exp1: simulator round (seed-level). Exp2: impression/journey with UID-cluster resampling. Exp3: user–video exposure with user-cluster resampling. Exp4: simulator round over 100 structural seeds (module A), audit replication (module B).
- **Which rules are frozen?** Frozen scientific configs (hashes above), calibration artifacts, seeds, support thresholds, cross-fitting folds, and audit rates; all recorded in `logs/run_config.json` / `metadata/exp1_stage_provenance.json`.
- **Which outputs are paper-facing canonical?** The four canonical roots listed above plus `publication/CR-EXP-OUTPUT-V1/` (paper-facing figures with `paper_result = true`).
- **What do the error bars mean?** Exp1: 95% seed-bootstrap interval. Exp2: empirical 2.5–97.5% UID-cluster resampling sensitivity range (not CI). Exp3: empirical 2.5–97.5% user-cluster resampling sensitivity range (not CI). Exp4: paired-seed frozen interval (panel a), ±1.96 MCSE (panels b/c), no interval at deterministic endpoints.
- **Scientific generation vs reporting/presentation?** Scientific runs are produced by the `main.py full`-type commands; reporting-only rebuilds (`reconcile.py … --rebuild reporting`, Exp4 `plot/tables/report`) and the publication presentation rebuild (`render_presentation.py render/validate --mode publication --exp all`) never touch scientific outputs. Lineage is separated into `scientific_source_lineage` and `presentation_source_lineage` in every figure metadata file.
- **How to verify repository = paper?** Run `scripts/validate_submission_repository.py` (read-only) and `pytest -q tests/test_submission_repository_contract.py`, then `render_presentation.py validate --mode publication --exp all`.
