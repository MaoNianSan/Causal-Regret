# Reproducing the Experiments

This guide reproduces the four experiments and the paper-facing artifacts from
a clean clone. All commands are run **from the repository root** and use
relative paths. The environment described here is the one used for the
reported paper results (see `environment.yml`).

## 1. Environment

The root `environment.yml` is the frozen environment used for the reported
results. Per-experiment `requirements.txt` files specify compatible
dependencies and are kept for users who prefer `pip`.

```bash
# Option A: conda (root frozen environment)
conda env create -f environment.yml
conda activate causal-regret

# Option B: pip with the per-experiment requirements
python -m pip install -r exp1_alignment_transfer/requirements.txt
python -m pip install -r exp2_real_delayed_conversion_logs/requirements.txt
python -m pip install -r exp3_sequential_recommendation_delayed_feedback/requirements.txt
python -m pip install -r exp4_controlled_route_audit/requirements.txt
```

Python 3.11 was used. All four experiments require `numpy`, `pandas`,
`scipy`, `matplotlib`, and `pyarrow`; Exp2 additionally requires `PyYAML`,
`tqdm`, and `joblib`; Exp4 additionally requires `Jinja2`; `pytest` is used by
the test suites.

## 2. Data preparation

Raw external datasets are not redistributed. See [`DATA.md`](DATA.md) for
sources, licenses, citations, expected file names, and placement.

- **Experiment 1**: no external raw data. The controlled simulator and the
  frozen calibration artifacts are part of the package
  (`exp1_alignment_transfer/calibration/`).
- **Experiment 2**: place the Criteo-format delayed-conversion log at
  `exp2_real_delayed_conversion_logs/inputs/pcb_dataset_final.tsv`
  (expected to be derived from `criteo_attribution_dataset.tsv.gz`, see
  `exp2_real_delayed_conversion_logs/inputs/README.md`).
- **Experiment 3**: place the three frozen KuaiRand-1K files under
  `exp3_sequential_recommendation_delayed_feedback/inputs/KuaiRand-1K/data/`
  (see `exp3_sequential_recommendation_delayed_feedback/inputs/README.md`).
- **Experiment 4**: no external raw data. The controlled simulator is part of
  the package (`exp4_controlled_route_audit/exp4/simulation/`).

## 3. Smoke test

The lightweight tier of each experiment can be exercised without the full
datasets (Exp3 falls back to a deterministic synthetic fixture when the
original inputs are absent).

```bash
python reproduce.py smoke --dry-run   # preview every command
python reproduce.py smoke             # run the fast-tier smoke checks
```

Smoke (fast-tier) runs are engineering gates only and are never paper
results.

## 4. Experiment 1

Controlled alignment and regret transfer. Frozen simulation design and
calibration artifacts; no external data.

```bash
# Fast tier (smoke / engineering gate)
python exp1_alignment_transfer/main.py fast
python exp1_alignment_transfer/self_check.py fast
python exp1_alignment_transfer/targeted.py fast
python exp1_alignment_transfer/plot_main.py fast
python exp1_alignment_transfer/plot_appendix.py fast

# Formal full run and paper promotion
python exp1_alignment_transfer/main.py full
python exp1_alignment_transfer/self_check.py full
python exp1_alignment_transfer/targeted.py full
python exp1_alignment_transfer/plot_main.py full
python exp1_alignment_transfer/plot_appendix.py full
python exp1_alignment_transfer/promote.py --run full
```

Paper artifacts: `exp1_alignment_transfer/outputs/paper_candidate/`
(figures, tables, source data, checks, and metadata).

### Selective rebuild without scientific rerun

When the verified scientific-generation source, effective configuration,
frozen calibration identity, and raw/seed artifacts still pass the explicit
provenance audit, rebuild only the stale downstream stage. These commands do
not launch the simulator and do not promote a paper candidate:

```bash
# Inspect or bootstrap explicit provenance for the verified source run.
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --audit

# Reuse raw/seed artifacts for the requested stage set.
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild validation
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild aggregation
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild reporting
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild downstream
```

The reconciliation artifact records the reused scientific run, the stage
hashes, and the rebuilt stages. A generation/configuration/calibration mismatch
refuses reuse and requires a separately approved scientific full rerun.

## 5. Experiment 2

Attribution sensitivity in delayed-conversion logs. Requires the local input
placed in step 2.

```bash
# Unit tests and fast tier
python -m pytest -q exp2_real_delayed_conversion_logs/tests
python exp2_real_delayed_conversion_logs/main.py fast

# Cohort check and formal full run
python exp2_real_delayed_conversion_logs/main.py cohort-check --mode full
python exp2_real_delayed_conversion_logs/main.py full
```

The full run writes its outputs to
`exp2_real_delayed_conversion_logs/outputs/exp2-full-<UTC timestamp>/`, and
promotion copies the curated paper artifact set to
`exp2_real_delayed_conversion_logs/outputs/paper/`:

```bash
python exp2_real_delayed_conversion_logs/promote.py --run-id <full_run_id>
```

## 6. Experiment 3

Logged-supported ranking recovery on KuaiRand-1K. Requires the local input
placed in step 2.

```bash
# Audit the real split before any run
python exp3_sequential_recommendation_delayed_feedback/main.py audit-inputs

# Fast tier on the real split (engineering gate)
python exp3_sequential_recommendation_delayed_feedback/main.py fast --n-jobs 4

# Fast tier on the software fixture (no external data needed)
python exp3_sequential_recommendation_delayed_feedback/main.py fast --synthetic-fixture --n-jobs 4

# Formal full run, self-check, and promotion
python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12
python exp3_sequential_recommendation_delayed_feedback/main.py self-check --mode full --run-id <full_run_id>
python exp3_sequential_recommendation_delayed_feedback/promote.py --run-id <full_run_id>
```

Paper artifacts: `exp3_sequential_recommendation_delayed_feedback/paper_candidate/`
(figures, tables, source data, and `manifest.json`). See
`exp3_sequential_recommendation_delayed_feedback/RUN_THIS_FIRST.txt` for the
full operational checklist.

## 7. Experiment 4

Recoverability boundary diagnostic under controlled simulation. No external
data.

```bash
# Fast, middle, and formal full tiers
python exp4_controlled_route_audit/main.py fast --n-jobs 4
python exp4_controlled_route_audit/main.py middle --n-jobs 8
python exp4_controlled_route_audit/main.py full --n-jobs 8

# Downstream stages for a completed run
python exp4_controlled_route_audit/main.py validate --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py aggregate --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py plot --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py tables --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py report --run-dir outputs/runs/<run_id>
python exp4_controlled_route_audit/main.py provenance --run-dir outputs/runs/<run_id>

# Stage-aware selective rebuild; raw simulation artifacts are reused only
# after the simulation/configuration/calibration provenance audit passes.
python exp4_controlled_route_audit/main.py reconcile --run-dir outputs/runs/<run_id> --rebuild validation
python exp4_controlled_route_audit/main.py reconcile --run-dir outputs/runs/<run_id> --rebuild aggregation
python exp4_controlled_route_audit/main.py reconcile --run-dir outputs/runs/<run_id> --rebuild reporting
python exp4_controlled_route_audit/main.py reconcile --run-dir outputs/runs/<run_id> --rebuild downstream
```

`main.py full` refuses to start from a dirty Exp4 worktree or an unresolvable
git commit. The canonical published run is
`exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/`
(result schema `exp4_controlled_route_audit_v3`, `paper_result=true`). The
previous v2 run `full_20260807T045219Z_7eeb2a31` is kept as a superseded
legacy run and is no longer canonical.

Selective rebuilds write an explicit reconciliation artifact. A changed
complete source tree or Git commit alone does not force a new simulation;
only the simulation-stage source, frozen configuration, calibration identity,
or required raw artifacts can do that.

## 8. Paper figures and tables

`docs/PAPER_RESULTS.md` maps every manuscript item to its experiment, source
data, command, canonical run, and final artifact. Regenerating a figure or
table never requires a scientific rerun: each package has a presentation-only
rebuild path that reads the frozen derived data of the canonical run.

| Experiment | Paper-facing artifacts |
|---|---|
| Exp1 | `exp1_alignment_transfer/outputs/paper_candidate/figures/`, `.../tables/`, `.../source_data/` |
| Exp2 | `exp2_real_delayed_conversion_logs/outputs/paper/figures/`, `.../tables/`, `.../derived/` |
| Exp3 | `exp3_sequential_recommendation_delayed_feedback/paper_candidate/figures/`, `.../tables/`, `.../source_data/` |
| Exp4 | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/figures/`, `.../tables/`, `.../derived/` |

### Publication presentation rebuild (no scientific rerun)

The canonical CR-EXP-OUTPUT-V1 publication bundle is rebuilt from the promoted
frozen sources with the presentation CLI. This path **does not rerun any
experiment**; it re-renders the same frozen point estimates and uncertainty:

```bash
python render_presentation.py render --mode publication --exp all
python render_presentation.py validate --mode publication --exp all
```

Output: `publication/CR-EXP-OUTPUT-V1/<experiment_id>/` (figures, tables,
manifests, validation). Publication metadata records `paper_result=true` and
`promotion_status=CANONICAL_PUBLICATION`, and keeps `scientific_source_lineage`
separate from `presentation_source_lineage`. Use `--mode preview --preview-root
<dir>` for an out-of-repo preview instead.

## 9. Expected outputs

Each formal run writes a self-contained run directory that contains, at
minimum:

- `checks/` — engineering, scientific, and self-check reports (JSON/CSV);
- `derived/` — the frozen scientific summary tables;
- `figures/` — PDF and PNG figures with `data/` and `metadata/` subfolders;
- `tables/` — paper tables in CSV and LaTeX form;
- `manifest/` or `metadata/` — run manifest, config snapshot, and artifact
  hashes.

The self-check and promotion gates must report `PASS` before a run is treated
as a paper result.

## 10. Compute requirements

All experiments were run on a single CPU workstation (Python 3.11).

| Experiment | Full-tier cost (reference run) | Notes |
|---|---|---|
| Exp1 | minutes | small controlled simulator; calibration artifacts are frozen |
| Exp2 | ~1 h (30-day Criteo log) | UID-resampling over ~16.5M impressions |
| Exp3 | ~1–2 h | 1000 bootstrap replications; the heaviest step |
| Exp4 | ~1 h | three modules over the controlled route grid |

Memory is modest (a few GB) for every experiment. Use `--n-jobs` to scale
with the available cores.
