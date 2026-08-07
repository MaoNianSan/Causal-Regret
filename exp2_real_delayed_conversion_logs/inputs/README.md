# Experiment 2 Inputs — Criteo Delayed-Conversion Log

## Dataset

The **Criteo Attribution Modeling for Bidding** dataset: a sample of 30 days
of Criteo live display-advertising traffic, with one row per impression. It
includes click, conversion, conversion-timestamp, attribution, and cost
information, plus anonymized contextual features. Key figures: ~16.5M
impressions, ~45K conversions, 700 campaigns, ~2.4 GB uncompressed
(623 MB compressed).

## Official source

Released by Criteo Research together with the AdKDD 2017 paper
*Attribution Modeling Increases Efficiency of Bidding in Display Advertising*
(Diemert, Meynet, Lefortier, Galland). The tarball contains
`criteo_attribution_dataset.tsv.gz` and `Experiments.ipynb`.

## Citation

> Diemert, E., Meynet, J., Lefortier, D., Galland, P. "Attribution Modeling
> Increases Efficiency of Bidding in Display Advertising." AdKDD & TargetAd
> Workshop, KDD 2017.

```bibtex
@inproceedings{DiemertMeynet2017,
  author = {{Diemert Eustache, Meynet Julien} and Galland, Pierre and Lefortier, Damien},
  title = {Attribution Modeling Increases Efficiency of Bidding in Display Advertising},
  booktitle = {Proceedings of the AdKDD and TargetAd Workshop, KDD, Halifax, NS, Canada, August 14, 2017},
  year = {2017}
}
```

## Access / license

Research use as granted by Criteo's release of the dataset. This repository
does **not** redistribute the raw file; it must be downloaded by the
researcher from the official source.

## Expected file

```
exp2_real_delayed_conversion_logs/inputs/criteo_attribution_dataset.tsv.gz
```

The frozen analysis consumes the processed input at:

```
exp2_real_delayed_conversion_logs/inputs/pcb_dataset_final.tsv
```

## Expected directory

```
exp2_real_delayed_conversion_logs/inputs/
```

Raw data files (`.tsv`, `.tsv.gz`, `.csv`, `.parquet`, `.ipynb`) in this
directory are excluded from git tracking by
`exp2_real_delayed_conversion_logs/.gitignore`; the directory is kept on the
local machine.

## Fields used

The frozen analysis uses the tab-separated fields: `timestamp`, `uid`,
`campaign`, `conversion`, `conversion_timestamp`, `conversion_id`,
`attribution`, `click`, `cost`, and `cpo`. The contextual `cat[1-9]` columns
are not required by the frozen route definitions.

## Primary 7-day window

The primary attribution window is **frozen at 7 days**. Changing the frozen
primary window requires a complete Experiment 2 scientific rerun.

## 30-day robustness window

The 30-day window is retained as a **robustness** analysis only. It does not
change the primary estimands or the paper-facing primary results.

## Raw data redistribution policy

Raw Criteo data is **local only**: it is never committed, never included in a
shareable experiment archive, and never redistributed by this repository.
   