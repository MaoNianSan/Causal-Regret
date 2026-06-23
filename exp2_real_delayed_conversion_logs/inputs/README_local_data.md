# Local protected input

Place the Criteo-format raw input at:

```text
inputs/pcb_dataset_final.tsv
```

The file must not be committed or included in a shareable experiment archive. It is parsed as a tab-separated file according to `config_exp2.yaml`.

This refactor changes action construction to `campaign_source_day_cell`. Do not reuse processed files or route assignments from earlier campaign-only/replay versions.
