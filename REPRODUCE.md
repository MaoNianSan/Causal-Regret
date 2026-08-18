# Reproducing and Validating the Reported Results

This guide is written **reviewer-first**: the fastest way to confirm that the
published results are what the repository actually contains is section B,
then C. Reproducing an experiment from scratch (section F) is the last and
heaviest step and is only needed when you want to re-derive the scientific
numbers yourself.

All commands run **from the repository root** with relative paths, unless a
command explicitly navigates into an experiment directory. The frozen
environment used for the reported paper results is `environment.yml`.

---

## A. Environment setup

```bash
# Option A: conda (frozen root environment, used for the reported results)
conda env create -f environment.yml
conda activate causal-regret

# Option B: pip with per-experiment requirements
python -m pip install -r exp1_alignment_transfer/requirements.txt
python -m pip install -r exp2_real_delayed_conversion_logs/requirements.txt
python -m pip install -r exp3_sequential_recommendation_delayed_feedback/requirements.txt
python -m pip install -r exp4_controlled_route_audit/requirements.txt
```

Python 3.11 was used. All four experiments require `numpy`, `pandas`,
`scipy`, `matplotlib`, and `pyarrow`; Exp2 additionally requires `PyYAML`,
`tqdm`, and `joblib`; Exp4 additionally requires `Jinja2`; `pytest` is used
by the test suites.

---

## B. Validate the published results (no scientific rerun)

Three independent, read-only checks confirm that the repository matches the
paper-facing canonical state. These are the quickest way to verify the
submission companion.

```bash
# 1. Read-only submission validator (checks A–L; exit 0 = PASS)
python scripts/validate_submission_repository.py

# 2. The same contract as an executable test suite
python -m pytest -q tests/test_submission_repository_contract.py

# 3. Validate the publication presentation bundle
python render_presentation.py validate --mode publication --exp all
```

What these check: canonical result roots exist with `paper_result=true`;
main long-form result CSVs carry the required columns
(`metric_id`, `estimand_id`, `condition_id`, `series_id`, `point_estimate`,
`interval_lower`, `interval_upper`); main publication figures exist in
PDF/SVG/PNG + CSV data + JSON metadata; appendix figures and manifests are
complete; publication validation records are present; the Exp2/Exp3 intervals
are correctly described as resampling **sensitivity ranges** (not confidence
intervals); Exp4 uses the v3 schema with the `panel_a` D_pair diagnostic and
the v2 legacy run is excluded from the canonical registry; scientific lineage
and presentation lineage are separated; and every referenced artifact is
tracked by git.

---

## C. Rebuild the publication figures (no scientific rerun)

The CR-EXP-OUTPUT-V1 publication bundle is rebuilt from the promoted frozen
derived data. This path **does not rerun any experiment**; it re-renders the
same frozen point estimates and uncertainty:

```bash
python render_presentation.py render --mode publication --exp all
python render_presentation.py validate --mode publication --exp all
```

Output: `publication/CR-EXP-OUTPUT-V1/<experiment_id>/` (figures, tables,
manifests, validation). Publication metadata records `paper_result=true` and
`promotion_status=CANONICAL_PUBLICATION`, and keeps
`scientific_source_lineage` separate from `presentation_source_lineage`. Use
`--mode preview --preview-root <dir>` for an out-of-repo preview instead.

Per-experiment figure/table regeneration without a scientific rerun is
documented in each experiment README and in
`docs/EXPERIMENT_IO_CONTRACT.md`.

---

## D. Reproduce each experiment

Raw external datasets are **not redistributed** (see section E and
[`DATA.md`](DATA.md)). A lightweight smoke tier exists for every experiment
and never requires the full external data:

```bash
python reproduce.py smoke --dry-run   # preview every command
python reproduce.py smoke             # run the fast-tier smoke checks
```

Smoke (fast-tier) runs are engineering gates only and are never paper
results.

### D.1 Experiment 1 — controlled alignment and regret transfer

No external data; the frozen simulation design and calibration artifacts are
part of the package.

```bash
# Fast tier (engineering gate)
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
(figures, tables, source data, checks, metadata).

**Selective rebuild without scientific rerun.** When the verified
scientific-generation source, effective configuration, frozen calibration
identity, and raw/seed artifacts still pass the explicit provenance audit,
rebuild only the stale downstream stage (this never launches the simulator):

```bash
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --audit
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild validation
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild aggregation
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild reporting
python exp1_alignment_transfer/reconcile.py --source-run exp1_alignment_transfer/outputs/full --rebuild downstream
```

A generation/configuration/calibration mismatch refuses reuse and requires a
separately approved scientific full rerun (section F).

### D.2 Experiment 2 — attribution sensitivity in delayed-conversion logs

Requires the Criteo-format input placed per section E.

```bash
python -m pytest -q exp2_real_delayed_conversion_logs/tests
python exp2_real_delayed_conversion_logs/main.py fast
python exp2_real_delayed_conversion_logs/main.py cohort-check --mode full
python exp2_real_delayed_conversion_logs/main.py full
```

The full run writes to
`exp2_real_delayed_conversion_logs/outputs/exp2-full-<UTC timestamp>/`;
promotion copies the curated paper artifact set to
`exp2_real_delayed_conversion_logs/outputs/paper/`:

```bash
python exp2_real_delayed_conversion_logs/promote.py --run-id <full_run_id>
```

### D.3 Experiment 3 — logged-supported ranking recovery on KuaiRand-1K

Requires the KuaiRand-1K inputs placed per section E.

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

Paper artifacts:
`exp3_sequential_recommendation_delayed_feedback/paper_candidate/` (figures,
tables, source data, `manifest.json`). See
`exp3_sequential_recommendation_delayed_feedback/RUN_THIS_FIRST.txt` for the
full operational checklist.

### D.4 Experiment 4 — recoverability boundary diagnostic

No external data; the controlled simulator is part of the package.

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
```

`main.py full` refuses to start from a dirty Exp4 worktree or an unresolvable
git commit. The canonical published run is
`exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/`
(result schema `exp4_controlled_route_audit_v3`, `paper_result=true`). The
previous v2 run `full_20260807T045219Z_7eeb2a31` is kept as a superseded
legacy run and is no longer canonical. A changed source tree or Git commit
alone does not force a new simulation; only the simulation-stage source,
frozen configuration, calibration identity, or required raw artifacts can do
that.

---

## E. Data-dependent limitations

Raw external datasets are **not redistributed**. This repository ships only
the code, contracts, and frozen derived results; Exp2 and Exp3 full runs
cannot be reproduced without the upstream downloads.

| Experiment | Status | What is required |
|---|---|---|
| Exp1 | `AVAILABLE_IN_REPO` | none — controlled simulator + frozen calibration |
| Exp2 | `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` | Criteo delayed-conversion log → `exp2_real_delayed_conversion_logs/inputs/pcb_dataset_final.tsv` (derived from `criteo_attribution_dataset.tsv.gz`; see `inputs/README.md`) |
| Exp3 | `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` | KuaiRand-1K files under `exp3_sequential_recommendation_delayed_feedback/inputs/KuaiRand-1K/data/` (see `inputs/README.md`) |
| Exp4 | `AVAILABLE_IN_REPO` | none — controlled simulator |

Sources, licenses, citations, expected file names, and the exact fields used
are in [`DATA.md`](DATA.md). Note that the smoke tier of Exp3 runs on a
deterministic synthetic fixture when the original inputs are absent; that
fixture is an engineering gate only and is never paper eligible.

---

## F. Full scientific rerun (heaviest path, last)

Only the sections above confirm the published results or rebuild presentation
artifacts. A full scientific rerun re-derives every number from scratch and is
only needed if you want to independently regenerate the scientific content.

```bash
# Per-experiment full runs + promotion (from section D)
python exp1_alignment_transfer/main.py full && python exp1_alignment_transfer/promote.py --run full
python exp2_real_delayed_conversion_logs/main.py full && python exp2_real_delayed_conversion_logs/promote.py --run-id <run_id>
python exp3_sequential_recommendation_delayed_feedback/main.py full --n-jobs 12 && python exp3_sequential_recommendation_delayed_feedback/promote.py --run-id <run_id>
python exp4_controlled_route_audit/main.py full --n-jobs 8
```

After all promotions, re-run section B and section C so the validator,
contract tests, and the publication bundle are regenerated against the new
canonical runs. Promotion gates must report `PASS` before a run is treated as
a paper result; non-deterministic stages (Exp2/Exp3 resampling) are expected
to produce runs that agree within the reported sensitivity ranges, not bitwise
identical artifacts.

**Compute (reference runs, single CPU workstation, Python 3.11):**

| Experiment | Full-tier cost | Notes |
|---|---|---|
| Exp1 | minutes | small controlled simulator; calibration frozen |
| Exp2 | ~1 h (30-day Criteo log) | UID-resampling over ~16.5M impressions |
| Exp3 | ~1–2 h | 1000 bootstrap replications; the heaviest step |
| Exp4 | ~1 h | three modules over the controlled route grid |

Memory is modest (a few GB) for every experiment. Use `--n-jobs` to scale
with the available cores.

---

## Expected outputs (any run)

Each formal run writes a self-contained run directory containing, at minimum:

- `checks/` — engineering, scientific, and self-check reports (JSON/CSV);
- `derived/` — the frozen scientific summary tables;
- `figures/` — PDF and PNG figures with `data/` and `metadata/` subfolders;
- `tables/` — paper tables in CSV and LaTeX form;
- `manifest/` or `metadata/` — run manifest, config snapshot, and artifact
  hashes.

`docs/PAPER_RESULTS.md` maps every manuscript item to its experiment, source
data, command, canonical run, and final artifact. The authoritative
input/output contracts (including uncertainty semantics) are in
`docs/EXPERIMENT_IO_CONTRACT.md`.
