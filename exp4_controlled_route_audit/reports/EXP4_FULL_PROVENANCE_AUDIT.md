# Exp4 Full Provenance Audit

Status date: 2026-08-06
Scope: `exp4_controlled_route_audit` only (read-only audit; no run outputs were modified)

## 1. Run identity

| Field | Value |
| --- | --- |
| Full run ID | `full_20260806T021401Z_5627f17b` |
| Recorded `code_commit` | `889bc77120cd52de73c2d0659d1575aaa395196e` |
| Recorded `source_code_hash` | `52e2ca0be113392807336020532d3996823a4d02465ecae60b1fa37dcbffdd9c` |
| Recorded `config_hash` | `0f87d5b27c36a5e6857bd889a8ee48a0b2b2e6abb10d8d08a7980998c1458db9` |
| Recorded `calibration_hash` | `c418ceaf99072b87f00aac0070d20925fe3c9f0eefd10dde8e2736e2c993ddf0` |
| Run tier | `full` |
| Result schema | `exp4_controlled_route_audit_v2` |

## 2. Source verification

| Field | Value |
| --- | --- |
| Current git HEAD | `339a5d71930a05939f8a98fda3cdda11bbcbd5be` |
| Current pre-fix `source_code_hash` | `0cce5bf348c98699cc5e47defd9637a2f6643df0a3cfcd24794d6073b2c3e62e` |
| **Source hash match** | **NO** |
| Current `config_hash` | `0f87d5b27c36a5e6857bd889a8ee48a0b2b2e6abb10d8d08a7980998c1458db9` |
| Config hash match | YES |
| Calibration hash match | YES (reproduced by the current implementation) |
| exp4 git worktree | clean (`git diff --check`-clean; diff hash `e3b0c442…` empty) |
| Repo worktree dirty | yes, 36 entries, all confined to `exp3_sequential_recommendation_delayed_feedback` (out of scope, untouched) |

### 2.1 How the hashes were computed

- `source_code_hash` uses the project's own implementation: SHA-256 over the sorted set of `exp4/**/*.py` relative paths plus file bytes (`exp4/outputs/writers.py::source_code_hash`).
- `config_hash` uses `exp4/outputs/writers.py::config_hash` over the frozen configuration payload.
- `calibration_hash` was recomputed with the current `calibrate_proxy_route` payload serialization and matches the stored value exactly.

### 2.2 Why the source hash does not match

The full-run outputs were published in commit `b565141` ("Publish exp4 full v2 results and exp2 paper outputs"); the `exp4/` v2 package did not exist in git until commit `339a5d7` ("Add exp2/exp4 v2 refactor code, docs and tests"), which is the current HEAD. The run's recorded `code_commit` (`889bc77`) predates both.

The stored `source_code_hash` cannot be reproduced from any current file set (attempted variants: current implementation, plus top-level `.py`, plus `tests/**`, all experiment `.py` excluding/including outputs, and absolute-path hashing). The run was therefore created from a pre-commit local state of the v2 package whose `exp4/**/*.py` contents cannot be shown identical to the current source.

## 3. Artifact completeness

| Field | Value |
| --- | --- |
| Module A raw trajectories | 100 / 100 (seeds 0..99) |
| Module B/C raw trajectories | 1000 / 1000 (replications 0..999) |
| Route maps | 1000 / 1000 |
| Manifest-referenced raw files | all exist, relative paths |
| Raw simulation size | 804.8 MB |
| Simulation artifacts complete | YES |
| Raw seed/replication outputs complete | YES |

## 4. Decision

Per the post-full-fix instruction §2.2, reuse of the existing Full simulation requires:

```text
stored_source_code_hash == current_pre_fix_source_code_hash   -> NO
config_hash_match == true                                     -> YES
calibration_hash_match == true                                -> YES
simulation_artifacts_complete == true                         -> YES
raw_seed_replication_outputs_complete == true                 -> YES
```

Because the source hash condition is not met, simulation provenance is **unverified**:

```text
FULL_SIMULATION_RERUN_REQUIRED=YES
FULL_SIMULATION_REUSED=NO
```

No original values in `outputs/runs/full_20260806T021401Z_5627f17b/logs/run_config.json` were modified during this audit.
