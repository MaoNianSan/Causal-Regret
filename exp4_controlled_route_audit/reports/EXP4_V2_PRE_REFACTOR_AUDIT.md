# Exp4 v2 Pre-Refactor Audit

Audit date: 2026-08-06  
Repository: `D:\research\causalregret\experiment\github`  
Scope: `exp4_controlled_route_audit` only  
Baseline commit: `889bc77120cd52de73c2d0659d1575aaa395196e`

## 1. Audit Boundary

- Existing outputs are read-only regression and provenance evidence.
- Exp1, Exp2, and Exp3 scientific logic is outside this change.
- The v1 full run is not a v2 paper result and cannot be migrated numerically where the attribution proxy semantics change.
- No full execution, promotion, commit, push, branch creation, or output deletion is authorized by this plan.

## 2. Current File Inventory

| File | Lines | Top-level classes/functions | Imports | Primary responsibility | Long or mixed responsibility |
|---|---:|---|---|---|---|
| `aggregate_results.py` | 302 | 5 functions | NumPy, pandas, config | Module A, audit, support, and calibration aggregation | Mixed across all modules |
| `audit_engine.py` | 701 | 2 dataclasses, 13 functions | NumPy, pandas, config, route maps, simulator | Inclusion, IPW, audit estimation, temporal calibration, controls, unit records | Overlong and highly mixed |
| `clean.py` | 35 | 1 function | shutil, pathlib, config | Interactive output cleanup | Focused |
| `code_check.py` | 64 | 1 function | json, pathlib, config, I/O | Static source-contract checks | Focused but v1-specific |
| `config.py` | 298 | 1 dataclass, 7 functions | dataclasses, hashlib, json, os, pathlib | Schema, registries, parameters, run modes, hashes | Mixed configuration and registry ownership |
| `engine.py` | 449 | 6 functions | NumPy, config, audit, policies, routes, simulator | Module A, learner appendix, Module B orchestration, storage | Overlong and mixed |
| `io_utils.py` | 239 | 2 classes, 9 functions | pandas, pathlib, subprocess, hashing/json | Run directories, metadata, Parquet, manifests | Cohesive infrastructure |
| `main.py` | 62 | 1 function | argparse plus all pipeline stages | `fast`/`full` end-to-end CLI | Focused, lacks middle and stage commands |
| `make_tables.py` | 181 | 2 functions | NumPy, pandas, config | Main and appendix tables | Mixed table families, includes learner result |
| `plot_results.py` | 673 | 7 functions | matplotlib, NumPy, pandas, config | Main figure, all appendix figures, style, bundles | Overlong and mixed |
| `policies.py` | 218 | 4 learner classes | NumPy, config | Scalar-feedback learner appendix | Exp1-like learner scope remains in Exp4 |
| `promote_results.py` | 94 | 4 functions | pandas, config, plotting, tables, I/O | Separate paper promotion | Focused but accepts v1 schema |
| `reproduce_all.py` | 6 | none | main | CLI alias | Compatibility wrapper |
| `route_maps.py` | 353 | 2 dataclasses, 11 functions | NumPy, config, simulator | Route construction, attribution, metrics, appendix regret | Mixed route and metric logic |
| `run_experiment4.py` | 315 | 3 functions | pandas, tqdm, config, engine, aggregation, I/O | Whole pipeline and all module artifact writing | Overlong orchestration |
| `self_check.py` | 399 | 4 functions | NumPy, pandas, config, route metrics, I/O | Engineering and scientific checks, reconstruction | Mixed validation categories |
| `simulator.py` | 329 | 1 dataclass, 9 functions | NumPy, config, hashing/json | DGP, delays, RNG streams, trajectory serialization | Mixed but internally coherent |
| `write_run_summary.py` | 105 | 1 function | NumPy, pandas, config | Chinese run summary | v1 names and artifact set |

There is no Exp4 test directory in the baseline repository. Validation is performed by runtime self-checks and static string checks only.

## 3. Current Schema and Registries

### Result schema

- Active: `exp4_controlled_route_audit_v1`
- Blocked legacy: `legacy_exp4_v1`

### Route IDs

- Primary order: `arrival_time`, `history_surrogate`, `proxy_label`, `source_bound`
- Dormant appendix registry entries: `noisy_state_oracle`, `latent_state_oracle`
- `proxy_label` display name is `Proxy-label`, not the v2 paper-facing `Partial-label proxy attribution`.
- `source_bound` display name is `Source-labelled`, not the v2 `Source-bound reference`.

### Audit design IDs

- `mcar_unweighted`
- `ambiguity_biased_unweighted`
- `ambiguity_biased_ipw`
- `full_population`

The two `ambiguity_biased_*` IDs and display names require a schema migration to `ambiguity_selective_*`.

### Calibration control IDs

- `affine_positive`
- `shuffled_negative`
- `nonlinear_monotone`

The first two require migration to `affine_linked` and `blocked_correspondence_destroyed`.

### Required derived files

The v1 contract requires 12 files: route-boundary seed and pair outputs, learner appendix, audit units, raw/calibrated estimates, fold parameters, audit/support/control summaries, and population targets. It uses a flat `derived/` directory and mixes Module A, B, and C contracts.

### Figure and table IDs

- Main figure: `fig_exp4_route_alignment_and_audit`
- Appendix figures: route heatmap, alignment-regret association, four-route comparison, effective support, calibration distributions
- Main table: `tbl_exp4_audit_reliability`

The current main figure includes calibration controls rather than effective support. Appendix figures and tables still include learner regret and the removed labelled-support coefficient.

### Promotion requirements

`promote_results.py` requires full tier, engineering/scientific PASS, all v1 derived files, main figure/table, explicit claim approval, and the current schema. It mutates derived metadata and regenerates figures/tables. Fast is blocked only through the full-tier check; there is no middle mode. The promotion code must be upgraded to reject v1 and all non-full v2 runs.

## 4. Theory-Code-Paper Mapping

### Action-gap defect

`route_maps.compute_action_gap_defect` constructs all upper-triangular action pairs, computes structural and route gaps, and returns

\[
\delta_t^r = \max_{a<b}|G_t^r(a,b)-G_t^c(a,b)|.
\]

`evaluate_route_map`, `audit_route`, `construct_audit_unit_records`, and `construct_population_target_records` all call this implementation. The code therefore matches Definition 4.3 and the proposed Appendix C.4 definition. The implementation should move to the v2 metric layer and return a typed result, but its scientific formula should not change.

### Ranking metric

`route_maps.evaluate_route_map` defines `ranking_reversal_rate` as whether any route-optimal action is not structurally optimal. This is an optimal-set conflict, not a pairwise sign-disagreement rate. The field is consumed by `aggregate_results.py`, `plot_results.py`, and `make_tables.py`. The v2 schema must rename it and add a separate 45-pair sign-disagreement metric.

### Module horizons

- Module A: `(T_A, W_A) = (5000, 250)` in both fast and full v1.
- Module B: formal `(T_B, W_B) = (2000, 100)`; v1 fast silently reduces `T_B` to 1000.
- v2 fast/middle/full should keep the scientific horizons explicit and vary only seeds/replications/bootstrap unless an explicitly named reduced integration fixture is used.

### Learner appendix

Learner logic is implemented in `policies.py` and `engine.run_scalar_feedback_learner`. It produces `exp4_learner_consequence_appendix.csv`, the alignment-regret appendix figure, the four-route comparison regret panel, and the learner-consequence appendix table. `self_check.py` also requires equality of the full-label proxy learner and source-bound learner traces. These artifacts are in `REQUIRED_DERIVED_FILES` and therefore currently affect promotion. V2 must remove learner outputs from primary artifacts, figures, tables, promotion, and Exp4 scientific gates; any retained regression helper must be appendix/validation-only and must not duplicate Exp1's evidence role.

## 5. Attribution, Audit, and Calibration Findings

- The v1 proxy calls `trajectory.attribution_proxy(sigma)` for every clock position and compares candidate source proxies with the proxy at the arrival clock. It does not create an arrival-side signature generated from the true source state.
- V1 uses a fixed kernel bandwidth `0.55` and exponential recency decay `0.035`; there is no independent calibration artifact or delay PMF.
- Candidate weights are numerically stabilized and normalized, but the pure weighting function is private and reads global configuration.
- Route-label masks are nested by construction because all rates threshold one uniform stream.
- The label-blind ambiguity score uses received assignment entropy and does not read true defect, but its contract is not isolated from route construction.
- Selective unweighted and IPW conditions share the same inclusion mask and probabilities in memory, but no stored shared-mask hash check exists.
- Empty/invalid weighted means return `NaN` silently and ESS returns zero; v2 requires explicit `NOT_ESTIMABLE` or an error.
- Cross-fitting uses contiguous folds and no identity/global fallback, but pair-specific estimability/status is compressed into a fold-wide boolean and detailed variance/status fields are absent.
- Calibration controls are embedded in the audit engine. The blocked shuffle saves neither permutation hashes nor correspondence/marginal-preservation checks.

## 6. Latest Full v1 Output Audit

Run: `outputs/runs/full_20260726T140240Z_1be8996e`

- Schema: `exp4_controlled_route_audit_v1`
- Recorded code commit: `6e09fa90a1fcdeccc861cf2960bd31c4b60e2df4`
- Config hash: `5ff1d086c5407968fc8fb9383f85df546b6191b793400618341f52da99f96b81`
- Module A seeds: 30
- Module B replications: 200
- Bootstrap replications: 2000
- Raw files: 430
- Derived files: 13
- Manifest rows: 484
- Engineering and scientific checks: PASS in stored checks
- Promotion/status files: `paper_result=true`, promotion PASS
- Run summary: still says `Paper promotion: NOT RUN` and `paper_result=false`

The report/status disagreement is preserved as a provenance warning. The run is complete enough for v1 regression auditing, but its attribution semantics, schema, sample sizes, controls, figures, and tables do not satisfy v2 and it must not be relabelled or promoted as v2.

## 7. Refactor Decision

The v2 implementation will use `exp4/` packages for configuration, simulation, routes, metrics, audit, calibration, modules, outputs, reporting, and validation. Top-level CLI files remain compatibility wrappers. Scientific logic will exist only in package modules; wrappers may re-export APIs during migration. Module A, B, and C outputs will be stored in separate derived subdirectories, and plotting/table code will read only frozen derived artifacts.

AUDIT_COMPLETE=YES  
CODE_MODIFICATION_STARTED=NO  
FULL_RUN_EXECUTED=NO  
PAPER_PROMOTION_EXECUTED=NO
