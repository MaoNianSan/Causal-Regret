# EXP1 output contract

The source of truth is `output_manifest.md`; this file provides the concise
paper-facing interpretation.

## Standard production outputs

Fast and full runs write complete seed-level results, summaries, tables,
figure bundles, manifests, and self-check reports. Standard production runs
use `summary_only` trace mode. They do not create empty detailed trace files.

## Figure requirements

Every registered figure must have:

```text
figures/pdf/<figure_id>.pdf
figures/png/<figure_id>.png
figures/data/<figure_id>_data.csv
figures/metadata/<figure_id>_metadata.json
```

Figure data uses a stable manuscript interface including method, information
interface, reference role, deployability, metric, uncertainty, run mode, and
paper-result fields.

## Paper-result gate

All new results begin with `paper_result=false`. A completed, non-smoke full
run must pass `self_check.py --mode full` before
`finalize_paper_outputs.py --mode full` can mark its bundle as paper eligible.
