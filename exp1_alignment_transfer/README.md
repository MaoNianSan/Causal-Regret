# Experiment 1: Controlled Alignment and Regret Transfer

This directory is the active implementation of Experiment 1 for the manuscript **Causal Regret Minimization under Delayed Feedback**.

The experiment has one scientific purpose:

> Test whether action-gap alignment, rather than delay magnitude alone, determines whether route-level optimization can control structural regret.

The implementation separates two components that must not be interpreted as the same object:

1. `route_map_diagnostic`: simulator-only full-map analysis of route validity and regret transfer;
2. `learner_consequence`: the same contextual Delayed EXP3 learner under arrival-clock and source-round scalar-feedback binding.

## Main commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the frozen sequence:

```bash
python calibrate.py
python main.py fast
python self_check.py --run fast
python targeted.py --run fast
python plot_main.py --run fast
python plot_appendix.py --run fast
```

After fast validation passes:

```bash
python main.py full
python self_check.py --run full
python targeted.py --run full
python plot_main.py --run full
python plot_appendix.py --run full
python promote.py --run full
```

`promote.py` is intentionally independent. It does not rerun estimands and cannot promote a development CSV fallback.

## Presentation-only rebuild

After a presentation-only patch (figures, captions, terminology, repository hygiene), no scientific rerun is needed. Rebuild presentation artifacts from the existing frozen full outputs only:

```bash
python plot_main.py --run full
python plot_appendix.py --run full
python promote.py --run full --force
```

This never touches seed metrics, derived summaries, checks, targeted outputs, figure data, or manuscript numerical values. The distinction is:

- **Scientific rerun** (`calibrate.py --force`, `main.py fast/full`, `targeted.py --run ...`) changes the frozen scientific artifacts and is forbidden for this patch.
- **Presentation rebuild** (the three commands above) regenerates PDF/PNG figures, figure metadata, and the paper candidate from frozen figure data only.

`outputs/full/` and `outputs/fast/` are kept locally for reproducibility but are not tracked by Git; `outputs/paper_candidate/` is the small, authoritative candidate and **is** tracked. See `.gitignore`.

## Figure metadata lineage

Figure metadata records two distinct lineages:

- `scientific_source_lineage`: the package-local `code_lineage` recorded in `calibration/exp1_calibration_manifest.json` at freeze time.
- `presentation_source_lineage`: a fingerprint of the presentation-only figure source (`plot_main.py`, `plot_appendix.py`).

A presentation patch updates `presentation_source_lineage` while `scientific_source_lineage` and all scientific artifact hashes remain unchanged.

## Parquet requirement

Formal runs require `pyarrow`. The code hard-fails if no parquet engine is installed.

For code development in an isolated environment only, the explicit flag below writes `.dev.csv` files and marks the run non-paper:

```bash
EXP1_DEV_CSV_FALLBACK=1 python main.py fast
```

This is not a silent fallback and cannot pass paper promotion.

## Frozen primary design

```text
K=10
T=5000
d_max=100
prehistory=100
state_burn_in=500
evaluation_seeds=0,...,29
calibration_seeds=10000,...,10019
bootstrap_repetitions=2000
```

Primary mechanisms, in fixed display order:

```text
zero_delay
exact_valid_shift
geometric_delay
mixture_delay
state_coupled_delay
systematic_misbinding
```

The structural loss is intrinsically bounded:

```text
L_t^c(a) = ((S_t - mu_a) / 2)^2 in [0,1]
```

The previous `/12.25` normalization and silent clipping are removed.

## Module responsibilities

| File | Responsibility |
|---|---|
| `config.py` | frozen configuration objects and IDs |
| `calibrate.py` | structural, delay, misbinding, and context calibration using calibration seeds only |
| `src/structural_process.py` | bounded structural paths and potential-loss matrices |
| `src/delay_mechanisms.py` | policy-independent delay paths |
| `src/path_generator.py` | shared path bundles and learner random tape |
| `src/route_maps.py` | simulator-only arrival and source-bound action-level maps |
| `src/delayed_exp3.py` | scalar-feedback-only contextual Delayed EXP3 |
| `src/runner.py` | route diagnostic and paired learner execution |
| `src/metrics.py` | frozen scientific estimands and invariants |
| `src/derived.py` | seed bootstrap, figure data, tables, and manuscript macros |
| `self_check.py` | engineering and scientific hard gates |
| `targeted.py` | non-Cartesian mean-delay and horizon validation |
| `plot_main.py` | main three-panel figure from frozen figure data only |
| `plot_appendix.py` | appendix figures from frozen derived data only |
| `promote.py` | independent paper promotion |

## Output structure

```text
outputs/<run_tier>/
├─ raw/
├─ seed_metrics/
├─ derived/
├─ figures/
│  ├─ data/
│  ├─ png/
│  ├─ pdf/
│  └─ metadata/
├─ tables/
├─ manuscript/
├─ checks/
├─ metadata/
└─ targeted/
```

Main manuscript artifacts include:

```text
fig_exp1_alignment_transfer.pdf
fig_exp1_alignment_transfer_data.csv
tab_exp1_mechanism_summary.tex
exp1_manuscript_values.json
exp1_manuscript_macros.tex
```

## Calibration lineage

Calibration compatibility is checked against a path-independent fingerprint of this package's scientific Python source tree. The containing repository Git commit is stored only as supplementary provenance. Therefore, extracting this package inside a larger Git repository does not invalidate calibration.

Structural persistence is gated directly by lag-1 state autocorrelation and median optimal-action run length. The optimal-action switch rate is reported descriptively because it is sensitive to action-grid boundaries.

`python calibrate.py` is idempotent: when the bundled calibration already matches the current scientific source tree, it validates the artifacts and exits without overwriting them. Use `--force` only after an approved code/design change.

## AR(1) manuscript boundary

AR(1) is a simulation DGP for the smooth baseline mechanisms. It is not a theoretical assumption of the paper and must not be added to the Section 3 assumption hierarchy.

## Cleanup

Cleanup is independent and never removes calibration artifacts:

```bash
python cleanup.py fast
python cleanup.py full
python cleanup.py all_runs
```

Without `--yes`, the command requires typing `CLEAN`.

## Frozen prehistory semantics

Prehistory initializes the simulator-only arrival route map. The contextual Delayed EXP3 learner starts at evaluation round 0 with an empty queue; no prehistory factual event is learner-visible.

## Full-run memory behavior

Round-level parquet artifacts are written incrementally per seed-mechanism task. The runner does not retain learner round-level output in memory across the full matrix.
