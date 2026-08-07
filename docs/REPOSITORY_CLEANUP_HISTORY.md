# Repository Cleanup History

## Purpose

This record documents the documentation normalization and audit-code cleanup
applied to the final Exp1–Exp4 frozen repository. It describes what was cleaned
and why, and the principles that govern which artifacts are retained.

## Motivation

- Unify each experiment README around a single structure (objective, boundary,
  data, estimand, contract, outputs, validation, commands, limitations).
- Reduce the root README to a concise experiment overview.
- Remove obsolete audit history, deprecated v1 compatibility wrappers,
  redundant legacy entry points, and temporary audit dumps.
- Keep the repository focused on canonical source, tests, active status
  reports, and published or promoted artifacts.

## Documentation changes

| file | change_type | reason |
|---|---|---|
| README.md | rewrite | Reduced to experiment overview and removed process-oriented narrative |
| exp1_alignment_transfer/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp2_real_delayed_conversion_logs/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp3_sequential_recommendation_delayed_feedback/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| exp4_controlled_route_audit/README.md | rewrite | Unified structure around objective, boundary, data, estimand, contract, outputs, validation, commands, limitations |
| docs/DOCUMENTATION_CLEANUP_PRE_AUDIT.md | create | Captured pre-cleanup repository state and sync policy |
| docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv | create | Recorded inventory and keep/delete/rewrite decisions |
| docs/CLEANUP_REFERENCE_CHECK.md | create | Documented reference checks for files slated for deletion |
| docs/REPOSITORY_CLEANUP_HISTORY.md | create | This permanent cleanup record |

## Categories of removed files

- Historical status and implementation reports (Exp1).
- Historical refactor baselines, status notes, and one-off comparison utilities
  (Exp2).
- Historical change memos, pre-modification audits, superseded implementation
  reports, and redundant implementation maps (Exp3).
- Deprecated v1 compatibility wrappers and legacy CLI entry points (Exp4).
- Temporary file-change and provenance audit dumps (Exp2/Exp4 reports).
- Untracked local audit dumps under experiment directories.

The full per-file list with reasons is recorded in
`docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv` and
`docs/CLEANUP_REFERENCE_CHECK.md`.

## Categories of retained scientific artifacts

- Canonical source packages and tests.
- Frozen design contracts, configuration, and calibration manifests.
- Self-check and validation infrastructure (engineering, scientific,
  provenance, schema, and figure/table consistency checks).
- Promoted and full-run results: figures, tables, checks, derived outputs, and
  run summaries.
- Manuscript-relevant figure source data and table source files.

## Reproducibility principles

- Generated artifacts are removed only when they are deterministically
  rebuildable from tracked source and configuration.
- Promoted paper candidates are preserved by ordinary cleanup until replacement
  artifacts are available.
- Calibration artifacts are preserved unless an approved cleanup explicitly
  removes them.
- Cleanup never deletes raw inputs or licensed external data.
- Experiment logic, simulation parameters, random seeds, outputs, scientific
  metrics, figures, tables, and manuscript numerical values are outside the
  scope of documentation cleanup.
