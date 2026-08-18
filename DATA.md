# Data

This page documents the data provenance of the four experiments. Raw external
datasets are **not redistributed** by this repository. Local input
directories are kept intact on the researcher's machine; only the README
describing each input directory is tracked by git.

## Availability summary

| Experiment | Status | Note |
|---|---|---|
| Exp1 | `AVAILABLE_IN_REPO` | controlled simulator; no external data |
| Exp2 | `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` | Criteo delayed-conversion log |
| Exp3 | `DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED` | KuaiRand-1K logged recommendation data |
| Exp4 | `AVAILABLE_IN_REPO` | controlled simulator; no external data |

## Experiment 1
*(`AVAILABLE_IN_REPO`)*

- **Type**: synthetic / controlled simulator.
- **No external raw dataset.**
- The frozen simulation settings and calibration artifacts are part of the
  package:
  - `exp1_alignment_transfer/config.py`
  - `exp1_alignment_transfer/calibration/` (delay, misbinding, structural,
    and context calibration JSON files + manifest)
- Expected local data: none to download.

## Experiment 2
*(`DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED`)*

- **Dataset**: Criteo delayed-conversion attribution dataset
  ("Attribution Modeling for Bidding").
- **Official source**: released with the AdKDD 2017 paper
  (Criteo Research). See
  `exp2_real_delayed_conversion_logs/inputs/README.md` for the full dataset
  description and citation.
- **Citation**:

  > Diemert, E., Meynet, J., Lefortier, D., Galland, P. "Attribution Modeling
  > Increases Efficiency of Bidding in Display Advertising." AdKDD & TargetAd
  > Workshop, KDD 2017.

- **License/access**: released by Criteo for research use; the upstream README
  (in `exp2_real_delayed_conversion_logs/inputs/README.md`) states the terms.
  This repository does not redistribute the raw file.
- **Expected local path**:
  `exp2_real_delayed_conversion_logs/inputs/criteo_attribution_dataset.tsv.gz`
  and the processed input
  `exp2_real_delayed_conversion_logs/inputs/pcb_dataset_final.tsv`.
- **Fields used**: `timestamp`, `uid`, `campaign`, `conversion`,
  `conversion_timestamp`, `conversion_id`, `attribution`, `click`, `cost`,
  `cpo`; the contextual `cat[1-9]` features are not required by the frozen
  analysis.
- **Train/evaluation period**: 30 days of live traffic; the primary
  attribution window is frozen at 7 days with 30 days retained as a
  robustness window.
- **Redistribution policy**: raw Criteo data is downloaded by the researcher
  and is excluded from git tracking (see
  `exp2_real_delayed_conversion_logs/.gitignore`).

## Experiment 3
*(`DOWNLOAD_REQUIRED` / `NOT_REDISTRIBUTED`)*

- **Dataset**: KuaiRand-1K (logged sequential recommendation feedback).
- **Official source**: released by Kuaishou; see
  `exp3_sequential_recommendation_delayed_feedback/inputs/README.md`.
- **Citation**: KuaiRand-1K is described in the KuaiRand dataset paper; the
  canonical citation is recorded in the inputs README.
- **License/access**: research license as specified by the dataset release;
  not redistributed by this repository.
- **Expected local files** (under
  `exp3_sequential_recommendation_delayed_feedback/inputs/KuaiRand-1K/data/`):
  - `log_standard_4_08_to_4_21_1k.csv`
  - `log_standard_4_22_to_5_08_1k.csv`
  - `video_features_basic_1k.csv`
- **Evaluation split**: deterministic two-fold user split (history vs.
  evaluation) with a strict temporal boundary; see
  `exp3_sequential_recommendation_delayed_feedback/config.py` and the design
  contract. The constructed target uses a six-hour post-exposure window.
- **Redistribution policy**: raw KuaiRand data is downloaded by the
  researcher and is excluded from git tracking (see
  `exp3_sequential_recommendation_delayed_feedback/.gitignore`). Fast mode
  can run on a deterministic synthetic fixture that is never paper eligible.

*(`AVAILABLE_IN_REPO`)*
## Experiment 4

- **Type**: synthetic / controlled simulator.
- **No external raw dataset.**
- The controlled simulation (state process, delay process, observation
  proxy, calibration) is part of the package under
  `exp4_controlled_route_audit/exp4/simulation/`.
- Expected local data: none to download.

## Summary

| Experiment | Data | External download required | Raw data tracked by git |
|---|---|---|---|
| Exp1 | controlled simulator | no | n/a |
| Exp2 | Criteo delayed-conversion log | yes (official source) | no |
| Exp3 | KuaiRand-1K | yes (official source) | no |
| Exp4 | controlled simulator | no | n/a |

Raw external datasets are not redistributed by this repository. If you need
the raw data, download it from the official sources listed above under their
respective licenses.
