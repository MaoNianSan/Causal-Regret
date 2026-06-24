# Repair notes

This package was repaired because its previous entry points delegated to an external `common.dual_mode` wrapper that was not included in the archive. The wrapper could write generic metadata with `backend_status: "skipped"` while recording an overall pass, without executing the Toy simulator or creating any substantive output.

## Changes applied

- Restored a self-contained native `main.py` that invokes the Toy simulator (`ToyCausalEnv`, `run_one_seed`, delay schedules, summaries, and figures).
- Removed the dependency on the absent external `common.dual_mode` package from runnable entry points and compatibility modules.
- Replaced `self_check.py` with a strict semantic validator. It requires executed/successful metadata, actual summary and figure artifacts, valid numeric tables, exact design coverage, zero oracle regret, zero-delay agreement, and fast-mode raw-log/delay consistency.
- Ensured each rerun clears only its target `outputs/<mode>/` directory to prevent stale artifacts from being reused.
- Regenerated and validated a genuine `outputs/fast/` run using seeds 0, 1, and 2.
- Updated reproduction scripts, README, output manifest, and the previously broken cleanup compatibility wrapper.

## Validation performed

```bash
python main.py --mode fast
python self_check.py --mode fast
python summarize.py --mode fast
python code_check.py
```

A negative test was also run: after changing `outputs/fast/logs/run_metadata.json` to `backend_status: "skipped"`, `self_check.py --mode fast` failed with the expected message. The valid metadata was then restored and the fast check passed.

`outputs/full/` is intentionally not precomputed in this repaired archive. Generate and validate it with `python reproduce_full.py` before using full-mode paper results.

## Follow-up integrity repair (2026-06)

A subsequent audit fixed three semantic issues that could otherwise survive a superficial fast check:

- The latent process is now a configurable clipped AR(1) state (`state_rho`, `state_sigma`, `state_clip`) rather than an unbounded random walk. This preserves time variation while keeping state and action-anchor scales compatible.
- `raw/delay_schedule.csv` now records the true `arrival_t` even for censored observations. Censoring governs learner access, not whether the source-to-arrival map is auditable.
- Source-state-distance and ranking-reversal diagnostics are retained in `toy_seed_summary.csv`, so `analyze_results.py --mode full` analyses the matching full output rather than silently reusing a possibly stale fast raw log.

The strict checker now cross-validates source, step, arrival, diagnostic, and summary tables in fast mode; verifies shared latent-state and delay paths; verifies censoring semantics; and checks zero-delay equality at the individual seed/timestep level.

## Final validation before delivery

The repaired package was checked with:

```bash
python reproduce_fast.py
python self_check.py --mode fast
python code_check.py
python analyze_results.py --mode fast
```

A disposable 3-seed full-mode smoke configuration also completed through
`main.py --mode full`, `self_check.py --mode full`, and
`analyze_results.py --mode full`. A negative test that changed
`backend_status` to `skipped` failed the strict checker as required.

The generated `outputs/` directories are intentionally removed before delivery
so a user rerun cannot accidentally be interpreted as packaged evidence.
