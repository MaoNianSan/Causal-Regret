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
