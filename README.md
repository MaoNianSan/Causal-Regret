# Causal Regret Minimization under Delayed Feedback

This repository accompanies a study of regret minimization in sequential
decision problems under **delayed feedback**. In online advertising and
recommendation systems, the outcome of a decision (a conversion, a reward)
arrives after a random delay and is conventionally **attributed to an earlier
decision** (source-time attribution). This repository studies how delayed,
attributed feedback changes what an offline benchmark measures and whether
regret-relevant structure can be recovered from logged data.

Each experiment is a self-contained package with a frozen design, a canonical
CLI, self-check gates, and explicit promotion rules. The four packages share a
scientific theme but have independent scientific contracts.

## Overview

- **Delayed feedback.** Outcomes are observed only after a random delay;
  evaluation must be conducted before all feedback has arrived.
- **Source-time attribution.** Each outcome is attributed to the decision that
  generated it, and the attribution convention determines what a benchmark
  actually ranks.
- **Benchmark-validity problem.** Attribution rules, delay structure, and
  logged support interact so that a benchmark can disagree with the true
  structural objective. The experiments localize where and why that happens.

## Experiments

| Experiment | Directory | Scientific question |
|---|---|---|
| Experiment 1: Controlled Alignment and Regret Transfer | [`exp1_alignment_transfer/`](exp1_alignment_transfer/README.md) | Does action-gap alignment, rather than delay magnitude alone, govern whether route-level optimization can control structural regret? |
| Experiment 2: Attribution Sensitivity in Delayed Conversion Logs | [`exp2_real_delayed_conversion_logs/`](exp2_real_delayed_conversion_logs/README.md) | How sensitive are allocation and ranking diagnostics to the attribution convention on a fixed delayed-conversion log? |
| Experiment 3: Logged-Supported Ranking Recovery | [`exp3_sequential_recommendation_delayed_feedback/`](exp3_sequential_recommendation_delayed_feedback/README.md) | Can logged support recover the reference ranking through the score -> reference-pair gap -> ranking recovery chain? |
| Experiment 4: Recoverability Boundary Diagnostic | [`exp4_controlled_route_audit/`](exp4_controlled_route_audit/README.md) | Where is the recoverability boundary of route alignment and audit reliability under controlled simulation? |

Each experiment README documents the scientific objective, boundary, frozen
data and split, estimands, implementation contract, output artifacts,
validation/self-check, and the commands used to produce the reported results.

## Repository structure

```text
Causal-Regret/
├── README.md               # this landing page
├── REPRODUCE.md            # step-by-step reproduction guide
├── DATA.md                 # data provenance for all four experiments
├── CITATION.cff            # citation metadata
├── environment.yml         # frozen environment used for the reported results
├── reproduce.py            # thin smoke / full forwarding wrapper
├── docs/
│   └── PAPER_RESULTS.md    # manuscript item -> repository artifact map
├── notebooks/
│   └── overview.ipynb      # rendered overview with figure previews (read-only)
├── exp1_alignment_transfer/                      # Experiment 1
├── exp2_real_delayed_conversion_logs/            # Experiment 2
├── exp3_sequential_recommendation_delayed_feedback/  # Experiment 3
└── exp4_controlled_route_audit/                  # Experiment 4
```

## Quick start

```bash
# 1. Create the environment (see REPRODUCE.md for alternatives)
conda env create -f environment.yml
conda activate causal-regret

# 2. Smoke test (lightweight fast-tier runs / self-checks)
python reproduce.py smoke --dry-run   # preview the commands
python reproduce.py smoke             # run them

# 3. Per-experiment full runs and paper artifacts
python reproduce.py full --exp 1      # forwards to the Experiment 1 full CLI
```

The commands behind the wrapper are documented in full in
[`REPRODUCE.md`](REPRODUCE.md), so the wrapper can be bypassed at any time.

## Reproducing paper results

[`REPRODUCE.md`](REPRODUCE.md) gives the environment, data preparation, smoke
test, per-experiment run commands, and the commands that regenerate every
paper figure and table. [`docs/PAPER_RESULTS.md`](docs/PAPER_RESULTS.md) maps
each manuscript item to its experiment, canonical run, source-data artifact,
and final figure/table artifact.

The current authoritative result of each experiment is the promoted
paper-facing canonical artifact:

| Experiment | Canonical result | Schema | Paper status |
|---|---|---|---|
| Exp1 | `exp1_alignment_transfer/outputs/paper_candidate/` | current v1.2 | `paper_result=true` |
| Exp2 | `exp2_real_delayed_conversion_logs/outputs/paper/` (`exp2-full-20260807T111616+0800`) | — | `paper_result=true` |
| Exp3 | `exp3_sequential_recommendation_delayed_feedback/paper_candidate/` (`exp3-full-20260807T072340Z`) | — | `paper_result=true` |
| Exp4 | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` | `exp4_controlled_route_audit_v3` | `paper_result=true` |

The canonical publication presentation bundle (CR-EXP-OUTPUT-V1) lives in
`publication/CR-EXP-OUTPUT-V1/`; see
[`docs/PAPER_RESULTS.md`](docs/PAPER_RESULTS.md) for per-item provenance and
artifact pointers. Historical migration details and superseded runs are
documented in the per-experiment READMEs and `docs/PAPER_RESULTS.md`, not here.

## Data

Raw external datasets are **not redistributed** by this repository. Experiment
2 uses the Criteo delayed-conversion attribution dataset and Experiment 3 uses
the KuaiRand-1K logged recommendation dataset; both are downloaded from their
official sources under their respective licenses. See
[`DATA.md`](DATA.md) for sources, citations, expected file names, placement,
and the fields used. Local input directories are kept intact; only the README
describing them is tracked.

## Compute

All experiments run on a single workstation. The full tiers use CPU-parallel
jobs (`--n-jobs`), and the heaviest step is the Exp3 bootstrap over 1000
replications. See [`REPRODUCE.md`](REPRODUCE.md#10-compute-requirements) for
per-experiment runtime and memory expectations.

## Citation

If you use this repository in your work, please cite it using the metadata in
[`CITATION.cff`](CITATION.cff). The final paper DOI and journal metadata will
be added when they become available.

## License

The license for this repository is pending author decision; no license has
been silently chosen. See [`LICENSE_SELECTION_REQUIRED.md`](LICENSE_SELECTION_REQUIRED.md)
for the decision that is required before public release.
