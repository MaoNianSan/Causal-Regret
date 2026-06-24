# Development Guide

This guide records the repository-level normalization rules for code and
supporting documentation.

## Python Formatting

Python files are formatted with Black using the root `pyproject.toml`.

```bash
python -m pip install -r requirements-dev.txt
python -m black --check .
python -m black .
```

The formatter intentionally excludes input-data holders and generated output
trees. Do not format or rewrite protected raw data, generated CSV outputs,
figures, notebooks, or run artifacts unless a task explicitly requires it.

## README Structure

Experiment README files should keep this order where applicable:

1. experiment scope and interpretation boundary;
2. required inputs and data-license notes;
3. fast and full run commands;
4. self-check or validation commands;
5. output contract and paper-facing artifacts;
6. GitHub packaging notes.

Keep commands copyable from the repository root or clearly state when they must
be run from an experiment directory.

## Documentation Conventions

Use relative paths wrapped in backticks, for example
`exp2_real_delayed_conversion_logs/inputs/`. Use fenced code blocks for command
sequences and output-tree sketches. Prefer concise scientific claims that match
the experiment's actual information protocol; avoid presenting smoke-test
outputs as paper-eligible full results.

## Version-Control Hygiene

Commit source code, README files, notebooks for inspection, lightweight figures,
tables, summaries, checks, metadata, reports, and manifests. Keep raw external
data, archives, caches, virtual environments, large regenerated intermediates,
and temporary runtime files local.
