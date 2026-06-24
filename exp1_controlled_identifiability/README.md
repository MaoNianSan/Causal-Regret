# EXP1: Controlled source-binding validity simulation

## Scope

EXP1 is a controlled contextual simulation for the source--intervention
binding validity claim. It is not an algorithm leaderboard and does not claim
that a source-labelled learner uniformly dominates every delayed-feedback
method. The experiment asks whether arrival-time evaluation remains
information-consistent after feedback is delayed.

Every learner receives the same decision-time context. The primary benchmark
is contextual structural causal regret relative to the action that minimises
conditional loss under that same context. Source-labelled, soft-attribution,
and proxy routes differ only in the information used to connect a delayed
outcome to its generating source event.

## Primary design

- `K=10` actions, `T=5000`, maximum delay `d_max=100`.
- Fast mode: `3` shared simulation seeds and `792` design combinations.
- Full mode: `30` shared simulation seeds and `7920` design combinations.
- The primary matched settings are `geometric_matched_15`,
  `mixture_matched_15`, and `state_structural_matched_15`.
- Matched settings share pre-generated state, context, and policy-independent
  delay paths within each seed and are calibrated to realised observed mean
  delay approximately `15`.
- `action_structural_stress` is policy-dependent and is a stress test only;
  it is excluded from matched-mean-delay claims.

## Information interfaces

- `arrival_time_naive`: updates from arrival-time feedback.
- `delayed_exp3`: unlabelled delayed-feedback baseline.
- `source_labelled`: updates the generating source-time pair when source labels
  are available.
- `soft_attribution_em`: soft source allocation under partial or unavailable
  labels.
- `proxy_state`: filtered-state recovery route.
- `oracle_reference`: non-deployable contextual reference.

All methods process one effective update per observed source outcome. No
arrival batch is collapsed into a single feedback observation. Gaussian-
integrated EM is an observable-information approximation for state-dependent
delay; `soft_attribution_em_stationary_ablation` is a deliberately simplified
stationary-geometric diagnostic control.

## Verification and rerun order

```powershell
# Compile all modules, execute the complete 264-combination smoke design,
# validate output contracts, and rebuild smoke outputs from raw results.
python code_check.py

# Development fast run: 3 seeds, T=5000, 792 combinations.
python reproduce_fast.py
python self_check.py --mode fast

# Formal numerical run: 30 seeds, T=5000, 7920 combinations.
python reproduce_full.py
python self_check.py --mode full

# Only after the full self-check passes: mark output bundles as paper eligible.
python finalize_paper_outputs.py --mode full
```

`fast` is a development and interface gate. It always writes
`paper_result=false`. A normal completed full run also begins with
`paper_result=false`; only `finalize_paper_outputs.py` can mark a verified full
output bundle as paper eligible.

## Output contract

Standard fast and full runs use `summary_only` trace mode. They write complete
seed-level records, summaries, tables, figure-data CSVs, figure metadata, and
a compact appendix trajectory audit. They intentionally do **not** create
empty `delay_schedule.csv`, `arrival_log.csv`, or `step_log.csv` placeholders.

The standard output tree is:

```text
outputs/<mode>/
  raw/seed_level_results.csv
  processed/selected_trajectory_points.csv
  summaries/
    seed_summary.csv
    method_summary.csv
    diagnostic_summary.csv
    paired_tests.csv
    bootstrap_ci.csv
    matched_mean_delay_summary.csv
  tables/
    table_exp1_results.csv
    table_exp1_diagnostics.csv
    table_exp1_matched_delay.csv
    tbl_app_exp1_all_method_results.tex
    tbl_app_exp1_simulation_settings.tex
    tbl_app_exp1_information_interfaces.tex
  figures/
    pdf/
    png/
    data/
    metadata/
  metadata/
  checks/
```

Confidence intervals use percentile bootstrap over shared simulation seeds with
`2000` resamples. Main figures use point ranges and keep methods in comparable
information regimes; cross-regime method bars are not used as fairness claims.

## Optional detailed trace audit

Detailed schedule, arrival, and step traces are intentionally disabled during
parallel production runs because multi-worker writers would otherwise create
empty or incomplete files. To generate a real compact trace audit, use one
worker and a small smoke run:

```powershell
$env:CRMD_WORKERS=1
$env:EXP1_TRACE_EVERY=20
python main.py --mode fast --smoke --raw-log-mode full --output-tag trace_smoke
python self_check.py --mode fast --output-tag trace_smoke
```

The command above is a trace audit, not a paper result.

## Rebuilding outputs from completed raw results

```powershell
python rebuild_outputs_from_raw.py --mode fast
python self_check.py --mode fast
```

The rebuild script consumes the current `raw/seed_level_results.csv` schema.
It does not use the retired `raw_setting_id` or `setting_id` fields from older
versions. Existing compact appendix trajectories are reused during an output-only
rebuild; a fresh simulation run regenerates them.

The compatibility command below rebuilds the same current-contract artifacts
from an existing output directory:

```powershell
python -m src.aggregate_results --output-root outputs/fast
```
