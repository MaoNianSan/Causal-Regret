# Causal Regret Minimization under Delayed Feedback

A repository of controlled simulation and real-log experiments studying regret
minimization under delayed feedback. Each experiment is a self-contained
package with a frozen design, canonical CLI, self-check gates, and explicit
promotion rules.

## Experiments

| Experiment | Directory | Goal | Status |
|---|---|---|---|
| Exp1 | [exp1_alignment_transfer](exp1_alignment_transfer/README.md) | Controlled alignment and regret transfer | IMPLEMENTED |
| Exp2 | [exp2_real_delayed_conversion_logs](exp2_real_delayed_conversion_logs/README.md) | Attribution sensitivity diagnostics | IMPLEMENTED |
| Exp3 | [exp3_sequential_recommendation_delayed_feedback](exp3_sequential_recommendation_delayed_feedback/README.md) | Logged-supported ranking recovery | IMPLEMENTED |
| Exp4 | [exp4_controlled_route_audit](exp4_controlled_route_audit/README.md) | Recoverability boundary diagnostic | IMPLEMENTED |

Each experiment README documents the scientific objective, boundary, frozen
data and split, estimands, implementation contract, output artifacts,
validation/self-check, and running commands.

## Delivery Overview

- [ipy/github_overview.ipynb](ipy/github_overview.ipynb) — rendered overview
  with embedded figure previews and per-project output manifests. Reads
  existing files only; performs no recomputation.

## Documentation

- [docs/EXP2_EXP4_RUN_INSTRUCTIONS.md](docs/EXP2_EXP4_RUN_INSTRUCTIONS.md) —
  full run instructions for Exp2–Exp4.
- [docs/REPOSITORY_ARTIFACT_AND_CLEANUP_POLICY.md](docs/REPOSITORY_ARTIFACT_AND_CLEANUP_POLICY.md) —
  artifact and cleanup policy.
- [docs/REPOSITORY_CLEANUP_HISTORY.md](docs/REPOSITORY_CLEANUP_HISTORY.md) —
  repository cleanup history.
- [docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv](docs/EXPERIMENT_DOCUMENTATION_INVENTORY.csv) —
  experiment documentation inventory.
