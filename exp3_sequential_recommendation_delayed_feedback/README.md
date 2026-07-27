# Experiment 3: Proxy Score, Gap, and Ranking Recovery

## Scientific scope

Experiment 3 is a logged-support recoverability diagnostic using KuaiRand-1K
standard recommendation logs. Its fixed evidence chain is:

\[
\text{score recovery}
\rightarrow
\text{held-out action-gap recovery}
\rightarrow
\text{offline ranking recovery}.
\]

It does **not** estimate online policy value, off-policy value, causal action
gaps, source-label sufficiency, or structural causal regret.

## Frozen design

- History: `log_standard_4_08_to_4_21_1k.csv`
- Evaluation: `log_standard_4_22_to_5_08_1k.csv`
- Time bins: Asia/Shanghai epoch days, with frozen split intervals
  `[2022-04-08, 2022-04-22)` and `[2022-04-22, 2022-05-09)`
- Primary target: constructed same-user 6-hour future-engagement score on the exact interval `[t, t+6h)`
- Candidate actions: history-defined top 20 named tags
- Residual bucket: accounting only; never a primary candidate
- Audit unit: calendar day × deterministic user hash group
- Reference: deterministic two-fold user split
- Full support threshold: 500 source events per fold, audit unit, and action
- Primary routes: Arrival carrier, Historical mean, Ridge proxy
- Uncertainty interface: full-sample point estimates are primary; user-cluster resampling (100 fast; 1,000 full) supplies empirical 95% sensitivity ranges only. No formal confidence interval is claimed
- Ranking metric: signed `cross_fitted_ranking_shortfall`; negative values are
  permitted and are never truncated

The group count, action vocabulary, support threshold, near-tie threshold, and
Ridge model are frozen from the history split before evaluation.

## Commands

```bash
# Real-data fast run. This is the default fast contract.
python main.py fast --n-jobs 4
python main.py self-check --mode fast --run-id <real_fast_run_id>

# After independent PASS, create and verify a slim archive. The local full run
# and its processed event files remain untouched.
python main.py archive --mode fast --run-id <real_fast_run_id>
python main.py archive-verify --package-dir deliverables/<real_fast_run_id>-archival --run-id <real_fast_run_id>

# Explicit software-only fixture. The printed fixture run ID must be passed to
# self-check because fixture outputs are intentionally not resolved as real fast runs.
python main.py fast --synthetic-fixture --n-jobs 4
python main.py self-check --mode fast --output-dir outputs/<fixture_run_id>

python main.py audit-inputs
python main.py full --n-jobs 12
python main.py self-check --mode full

# Resume only the bootstrap/render/finalize stages of an interrupted run.
python main.py full --resume-bootstrap --output-dir outputs/<full_run_id> --n-jobs 12

# Promotion is explicit and run-ID based.
python promote.py --run-id <full_run_id>

# Remove one run interactively, either by exact run ID or by latest tier run.
python clean.py --run-id <run_id>
python clean.py --mode fast
python clean.py --mode full
```

Each fresh run is immutable and is written to
`outputs/exp3-<tier>-<UTC timestamp>/`. With no explicit selector, self-check
uses the latest pipeline-completed run, including a run whose earlier
self-check failed. Formal result references use the separate latest audited
PASS resolver. Bootstrap resume requires arrays, checkpoint, config, and a
compatible source-tree hash. `--run-id` and `--output-dir` always take
precedence over automatic resolution.

Fast and full both hard-fail when the three required original inputs are
missing. A deterministic software fixture is available only through the
explicit `--synthetic-fixture` flag and always has `paper_result=false`.

## Cleaning outputs

`clean.py` removes one immutable run directory at a time. By default it prints
the resolved target and requires typing `CLEAN` before deletion:

```bash
# Delete a specific real or fixture run.
python clean.py --run-id exp3-fixture-20260727T040311Z

# Delete the latest real run of a tier. Fixture runs are not selected by --mode.
python clean.py --mode fast
python clean.py --mode full

# Skip the interactive confirmation, for example in automation.
python clean.py --run-id <run_id> --yes
```

Promoted paper results are protected. `clean.py` refuses to remove one unless
`--force-paper` is supplied explicitly; archive the result before using that
override.

## Main output

The active paper figure is:

```text
figures/main/exp3_main_score_gap_ranking.pdf
figures/main/exp3_main_score_gap_ranking.png
figures/data/exp3_main_score_gap_ranking_data.csv
figures/metadata/exp3_main_score_gap_ranking_metadata.json
```

The layout directly encodes the evidence chain:

1. score calibration for Historical mean and Ridge proxy;
2. held-out action-gap defect and sign agreement;
3. signed cross-fitted ranking shortfall and top-action match.

Primary numerical and audit tables:

```text
tables/exp3_primary_route_results.csv
tables/exp3_paired_ranking_contrast.csv
tables/exp3_support_coverage.csv
tables/exp3_decile_calibration.csv
checks/exp3_resampling_sensitivity_audit.csv
tables/exp3_data_dependence_structure.csv
tables/exp3_resampling_structure_diagnostics.csv
derived/exp3_outcome_reuse_quantiles.csv
diagnostics/exp3_route_selection_diagnostics.csv
diagnostics/exp3_ridge_history_selection_overlap.json
tables/exp3_action_space_coverage.csv
tables/exp3_full_design_support_preflight.csv
```

Appendix figures:

```text
figures/appendix/exp3_appendix_full_design_support_preflight.pdf
figures/appendix/exp3_appendix_arrival_carrier_diagnostic.pdf
figures/appendix/exp3_appendix_dependence_and_selection_structure.pdf
```

The full-design support preflight evaluates the formal top-20, G in {10,5}, and 500-events-per-fold specification during fast without changing the active top-6 fast estimand.

Support coverage is scoped to the selected action vocabulary. The main figure,
source CSV, metadata, and report separately disclose the fraction of total
evaluation exposure mass represented by that vocabulary.

All plots read frozen tables only. They do not fit models, choose actions,
change support, or run bootstrap procedures.

## Status gates

- `Engineering PASS`: executable pipeline, valid schemas, schedule-independent
  bootstrap seeds, resumable persisted draws, and synchronized figure data.
- `Scientific PASS`: honest time split and two-fold design, adequate support,
  no evaluation-based design tuning, no legacy partial-label routes.
- `Paper PASS`: explicit promotion after a non-synthetic full run with both
  engineering and scientific PASS.

`PASS_WITH_LIMITED_SUPPORT` is reportable as a diagnostic but cannot be
promoted to a paper result without a new approved design decision.


## Run-tier input contract

- `python main.py fast` uses the frozen real KuaiRand inputs. Fast changes only the prespecified computational scale—top-6 actions, fast support threshold, and 100 bootstrap repetitions—and is never paper eligible.
- `python main.py fast --synthetic-fixture` runs the deterministic software fixture explicitly. Its run ID begins with `exp3-fixture-`; it cannot be mistaken for or resolved as a real fast run.
- `python main.py full` uses the frozen real KuaiRand inputs and hard-fails on missing inputs or boundary contamination above the frozen limits.
- `python main.py audit-inputs` performs a low-memory audit of the real history/evaluation files before a full run.
- `python main.py self-check --mode ...` is only valid after the corresponding pipeline completes; otherwise it returns `SELF_CHECK_BLOCKED` rather than a missing-file traceback.
- Full local self-check requires the event-level `processed` artifacts and
  independently reconstructs every check. A slim archive deliberately omits
  those large files and must use `archive-verify`; that command verifies frozen
  hashes and the source-tree version and never claims independent reconstruction.

The official files contain small epoch-time tails outside their named local
date ranges. The audit reports the raw ranges, then the pipeline quarantines
only history events before April 8 and evaluation events before April 22.
Each exclusion is independently capped at 0.1%; larger contamination hard-fails.
Both raw and normalized exclusion counts are persisted in the audit and run
preflight artifacts.

## Implementation safeguards added in the final repair

- The target interval is explicitly left-closed and right-open: `[t,t+6h)`.
- Calendar bins and split-end right-censoring use frozen Asia/Shanghai day
  boundaries rather than the execution machine timezone or UTC midnight.
- Outcome-reuse diagnostics are aligned after the final event sort.
- Main-figure filled markers are full-sample estimates. Open markers and horizontal lines
  are resampling medians and empirical sensitivity ranges. They are sensitivity
  diagnostics rather than confidence intervals and need not contain the
  full-sample estimate.
- Bootstrap replication seeds depend only on `(bootstrap_seed, replication_id)`,
  so results do not depend on thread scheduling.
- Complete bootstrap chunks are persisted and can be resumed by run ID.
- A full pipeline ends at `PENDING_SELF_CHECK`; scientific PASS is assigned
  only by the independent self-check.
- Self-check reconstructs the target-window contract and verifies that figure
  source data reproduce the frozen numerical tables exactly.


## 2026-07-27 boundary-preserving repair

The scientific task boundary is unchanged: the same three routes, history-frozen design, honest two-fold held-out reference, support-qualified score/gap/ranking estimands, and user-cluster bootstrap remain active.

Implementation repairs:

- Ridge uses only action indicators, the most recent completed-bin proxy mean/count, and a missingness indicator. Unfrozen EWMA features were removed; no new model family was introduced.
- Full-sample point estimates are primary. The displayed 2.5--97.5% user-cluster resampling ranges are sensitivity diagnostics and are not interpreted as formal confidence intervals.
- Legacy basic-bootstrap reflections remain only in `checks/exp3_resampling_sensitivity_audit.csv` so earlier anomalies can be reconstructed. Centering warnings remain disclosed but do not invalidate the accepted sensitivity-only interface.
- `tables/exp3_data_dependence_structure.csv`, `derived/exp3_outcome_reuse_quantiles.csv`, and `tables/exp3_resampling_structure_diagnostics.csv` disclose overlapping-target reuse and support/reference/selection switching under user resampling.
- The old support-margin map was removed. The replacement reports formal full-design cell support and selected-action exposure-mass coverage separately.
- Route-selection diagnostics disclose action collapse and Ridge–Historical-mean selection equivalence rather than tuning the model to avoid a null result.
- Boundary quarantine, action-space scope, and target-reuse diagnostics are explicit report artifacts.
- Run resolution ignores incomplete failed runs when choosing the latest run for self-check.
- Every run freezes `code_version_type=source_tree_sha256` and the deterministic
  source hash in its run manifest, artifact manifest, design freeze, report,
  and figure metadata.
- Core responsibilities were split into `input_normalization.py`, `evaluation_arrays.py`, `evaluation_artifacts.py`, `bootstrap_intervals.py`, `bootstrap_summary.py`, `run_registry.py`, and `self_check_helpers.py`; all Python files remain below 400 lines.
