# Causal Regret Minimization under Delayed Feedback — Submission Companion Repository

This repository accompanies the paper on regret minimization in sequential decision problems under **delayed feedback**. In online advertising and recommendation systems, the outcome of a decision arrives after a random delay and is conventionally attributed to an earlier decision (source-time attribution). This repository studies how delayed, attributed feedback changes what an offline benchmark measures and whether regret-relevant structure can be recovered from logged data.

The repository is organized as **code + data instructions + experiment contracts + canonical paper results + publication figures + reproduction/validation entry points**. It is not a development-history log.

## Repository structure

```text
Causal-Regret/
├── README.md                          # this landing page
├── REPRODUCE.md                       # reviewer-facing reproduction guide
├── DATA.md                            # data provenance and availability
├── CITATION.cff                       # citation metadata
├── environment.yml                    # frozen environment
├── reproduce.py                       # thin smoke/full forwarding wrapper
├── render_presentation.py             # presentation CLI (render/validate; preview/publication)
├── presentation_sources.py            # presentation registry (figure/table sources)
├── scripts/
│   └── validate_submission_repository.py   # read-only submission validator
├── tests/
│   ├── test_presentation_output.py
│   └── test_submission_repository_contract.py
├── docs/
│   ├── EXPERIMENT_IO_CONTRACT.md      # per-experiment input/output contracts (authoritative)
│   ├── PAPER_RESULTS.md               # canonical result registry
│   └── DEVELOPMENT_HISTORY.md         # dev-noise classification of non-submission files
├── publication/
│   └── CR-EXP-OUTPUT-V1/              # paper-facing publication bundle (README inside)
├── exp1_alignment_transfer/           # Experiment 1
├── exp2_real_delayed_conversion_logs/ # Experiment 2
├── exp3_sequential_recommendation_delayed_feedback/  # Experiment 3
└── exp4_controlled_route_audit/       # Experiment 4
```

## Quick start

```bash
# 1. Environment (see REPRODUCE.md)
conda env create -f environment.yml
conda activate causal-regret

# 2. Validate the published results (lightest possible; read-only)
python scripts/validate_submission_repository.py
pytest -q tests/test_submission_repository_contract.py

# 3. Rebuild the publication figures (no scientific re-run)
python render_presentation.py render --mode publication --exp all
python render_presentation.py validate --mode publication --exp all

# 4. Smoke test (fast-tier runs / self-checks)
python reproduce.py smoke --dry-run
python reproduce.py smoke
```

Full per-experiment commands are in `REPRODUCE.md` and `docs/EXPERIMENT_IO_CONTRACT.md`.

## Experiments and canonical results

| Experiment | Role in evidence chain | Input | Canonical output | Main artifact |
|---|---|---|---|---|
| Exp1 | Controlled alignment and regret transfer | controlled simulator (no external data) | `exp1_alignment_transfer/outputs/paper_candidate/` | `fig_exp1_alignment_transfer` |
| Exp2 | Attribution sensitivity in delayed-conversion logs | Criteo log (download required) | `exp2_real_delayed_conversion_logs/outputs/paper/exp2-full-20260807T111616+0800/` | `figure_exp2_attribution_sensitivity` |
| Exp3 | Delayed-feedback recommendation and decision recovery | KuaiRand-1K logs (download required) | `exp3_sequential_recommendation_delayed_feedback/paper_candidate/` (run `exp3-full-20260807T072340Z`) | `exp3_main_score_gap_ranking` |
| Exp4 | Route alignment, audit reliability, recoverability | controlled simulator (no external data) | `exp4_controlled_route_audit/outputs/runs/full_20260817T071019Z_7d7146b7/` | `fig_exp4_route_alignment_and_audit_reliability` |

All four canonical outputs carry `paper_result = true`. Exp4 uses result schema `exp4_controlled_route_audit_v3`. The authoritative per-experiment input/output contracts (commands, metrics, uncertainty semantics, interpretation boundaries) are in [`docs/EXPERIMENT_IO_CONTRACT.md`](docs/EXPERIMENT_IO_CONTRACT.md). The paper-facing presentation bundle with all figures, tables, and per-figure metadata is in [`publication/CR-EXP-OUTPUT-V1/`](publication/CR-EXP-OUTPUT-V1/README.md).

## Reproduce / validate

- **[`REPRODUCE.md`](REPRODUCE.md)** — environment setup, validation of published results, publication figure rebuild (no scientific re-run), per-experiment reproduction, data limitations, and full scientific rerun.
- **[`scripts/validate_submission_repository.py`](scripts/validate_submission_repository.py)** — read-only check that the repository matches the paper-facing canonical state.
- **[`tests/test_submission_repository_contract.py`](tests/test_submission_repository_contract.py)** — the same contract as executable tests.
- **[`docs/PAPER_RESULTS.md`](docs/PAPER_RESULTS.md)** — canonical result registry (experiment, canonical id/path, schema, paper status, main figure/table).

## Data availability

- Exp1, Exp4: controlled simulators — **`AVAILABLE_IN_REPO`** (no external data).
- Exp2: Criteo delayed-conversion log — **`DOWNLOAD_REQUIRED`**, not redistributed.
- Exp3: KuaiRand-1K logs — **`DOWNLOAD_REQUIRED`**, not redistributed.

See [`DATA.md`](DATA.md) for sources, expected paths, required fields, and license/terms.

## Uncertainty semantics (summary)

- Exp1: 95% seed-bootstrap interval.
- Exp2: empirical 2.5%–97.5% UID-cluster resampling sensitivity range (**not** a confidence interval).
- Exp3: empirical 2.5%–97.5% user-cluster resampling sensitivity range (**not** a confidence interval).
- Exp4: paired-seed frozen interval (panel a), estimate ±1.96 MCSE (panels b/c), no interval at deterministic endpoints.

## Citation

If you use this repository or its results, cite it via the metadata in [`CITATION.cff`](CITATION.cff). The final paper DOI and journal metadata will be added when available.

## License

The license for this repository is pending author decision; no license has been formally selected yet (see [`LICENSE_SELECTION_REQUIRED.md`](LICENSE_SELECTION_REQUIRED.md)). Until a license is chosen, treat the repository as all-rights-reserved by the authors.
