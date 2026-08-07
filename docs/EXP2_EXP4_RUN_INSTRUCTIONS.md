# Exp2–Exp4 Full Run Instructions

Date: 2026-08-07
Scope: Run Full tiers for Exp2, Exp3, Exp4 under the current (cleaned) code.

## Prerequisites (before any run)

1. Commit or stash the current documentation/cleanup changes so the Exp4 formal Full worktree gate passes.
   ```powershell
   cd D:\research\causalregret\experiment\github
   git status --short
   # Review the M/D files (README rewrites, audit deletions) and commit them:
   git add -A
   git commit -m "exp2-4 doc normalization and audit-code cleanup"
   ```
   Exp4 `main.py full` refuses a dirty Exp4 worktree
   (`FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE`) and requires a resolvable commit.

2. Verify each experiment's tests before running Full.
   ```powershell
   python -m compileall exp2_real_delayed_conversion_logs exp3_sequential_recommendation_delayed_feedback exp4_controlled_route_audit
   ```

---

## Exp2 — Attribution Sensitivity (delayed-conversion logs)

```powershell
cd D:\research\causalregret\experiment\github\exp2_real_delayed_conversion_logs

# 1. Engineering gate (fast, real inputs present)
python main.py fast

# 2. Cohort check on the real log (full mode)
python main.py cohort-check --mode full

# 3. Formal full run (explicit authorization required)
python main.py full
```

- Fast runs are always `INELIGIBLE_FAST`; only the formal full run is a paper
  promotion candidate.
- Inputs must be present under `inputs/` (criteo/pcb datasets; they are present
  on disk and not stored in Git).

---

## Exp3 — Logged-Supported Ranking Recovery

```powershell
cd D:\research\causalregret\experiment\github\exp3_sequential_recommendation_delayed_feedback

# 1. Tests (unit + contract)
python -m pytest -q

# 2. Software fixture fast run (no real inputs needed)
python main.py fast --synthetic-fixture --n-jobs 4
python main.py self-check --mode fast --output-dir outputs/<fixture_run_id>

# 3. Real-data fast engineering gate
python main.py fast --n-jobs 4
python main.py self-check --mode fast --run-id <real_fast_run_id>

# 4. Formal full run (explicit human approval required)
python main.py full --n-jobs <N>
python main.py self-check --mode full --run-id <new_full_run_id>
python promote.py --run-id <new_full_run_id>
```

- Fast is never a paper result.
- The `outputs/` and `deliverables/` directories are recreated automatically at
  run time (they were cleaned locally; they are Git-ignored).
- Frozen inputs are under `inputs/KuaiRand-1K/` and `inputs/_fast_fixture/`.

---

## Exp4 — Recoverability Boundary Diagnostic

```powershell
cd D:\research\causalregret\experiment\github\exp4_controlled_route_audit

# 1. Tests
python -m pytest -q

# 2. Fast tier (engineering gate)
python main.py fast --n-jobs 4

# 3. Middle tier (optional intermediate)
python main.py middle --n-jobs 8

# 4. Formal full run (requires clean Exp4 worktree + resolvable commit)
python main.py full --n-jobs 8

# 5. Post-run stages on the new run dir
python main.py validate --run-dir outputs/runs/<new_full_run_id>
python main.py aggregate --run-dir outputs/runs/<new_full_run_id>
python main.py plot --run-dir outputs/runs/<new_full_run_id>
python main.py tables --run-dir outputs/runs/<new_full_run_id>
python main.py report --run-dir outputs/runs/<new_full_run_id>

# 6. Promotion (separate manual approval; only a passed full v2 run)
python promote_results.py --run-dir outputs/runs/<new_full_run_id> --approve-claims
```

- The previous promoted run `full_20260806T090024Z_2d3c1b0d` was lost in a
  cleanup (untracked, not on GitHub, not in recycle bin). A new full run must
  be produced; the old tracked run `full_20260806T021401Z_5627f17b` lacks
  lineage and cannot be promoted.
- Keep `outputs/runs/<new_full_run_id>` tracked if it should be published to
  GitHub: update `.gitignore` whitelist to include it.

---

## Summary table

| Exp | Tests | Fast gate | Full run | Post-run | Promote |
|---|---|---|---|---|---|
| Exp2 | pytest | `main.py fast` | `main.py full` | cohort-check | `promote.py` |
| Exp3 | pytest | `main.py fast` | `main.py full` | self-check full | `promote.py` |
| Exp4 | pytest | `main.py fast` | `main.py full` | validate/aggregate/plot/tables/report | `promote_results.py` |
