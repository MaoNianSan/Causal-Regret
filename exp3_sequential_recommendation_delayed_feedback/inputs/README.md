# Experiment 3 Inputs — KuaiRand-1K

## Dataset

**KuaiRand-1K**: a logged sequential-recommendation feedback dataset released
by Kuaishou, subsampled to 1000 users. It records user interaction sequences
over video recommendations and is used here for the frozen
logged-supported ranking recovery design.

## Official source

Kuaishou's official KuaiRand release (KuaiRand / KuaiRand-1K). See the
dataset release page for the download location and the exact file versions.

## Citation

Cite the KuaiRand dataset paper as specified in the official release
(recorded at download time). The canonical reference is the KuaiRand dataset
paper by the Kuaishou team.

## Access / license

Research license as specified by the dataset release. This repository does
**not** redistribute the raw data; it must be downloaded by the researcher
from the official source.

## Expected files

Place the three frozen files under `inputs/KuaiRand-1K/data/`:

- `log_standard_4_08_to_4_21_1k.csv`
- `log_standard_4_22_to_5_08_1k.csv`
- `video_features_basic_1k.csv`

## Expected directory

```
exp3_sequential_recommendation_delayed_feedback/inputs/KuaiRand-1K/data/
```

Raw data under `inputs/` is excluded from git tracking by
`exp3_sequential_recommendation_delayed_feedback/.gitignore`; the directory
is kept on the local machine. Fast mode can run on a deterministic synthetic
fixture (`inputs/_fast_fixture/`) that is never paper eligible.

## Evaluation split

The frozen design uses a deterministic two-fold user split (history vs.
evaluation) with a strict temporal boundary; the constructed target uses a
six-hour post-exposure window. The split and target construction are part of
the frozen design contract (see `config.py` and `design_contract.py`). The
random-exposure stream is not part of the primary Experiment 3 target.

## Local data policy

Keep the KuaiRand-1K checkout local for private execution. Do not commit
KuaiRand inputs, upstream README/LICENSE files, loader code, processed
tables, user sequences, feature tables, or caches. Raw data is never
redistributed by this repository.
