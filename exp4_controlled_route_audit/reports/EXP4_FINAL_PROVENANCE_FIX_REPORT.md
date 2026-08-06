# Exp4 Final Provenance Fix Report

Status date: 2026-08-06
Scope: `exp4_controlled_route_audit` only (Exp1/Exp2/Exp3 untouched)

---

## 1. 修改内容

### 1.1 修改的文件

| 文件 | 修改内容 |
| --- | --- |
| `exp4/outputs/writers.py` | `RunContext` 新增 `exp4_worktree_clean_at_start` / `stage_source_hashes`;新增 `git_commit_available`、`exp4_dirty_files`、`exp4_worktree_clean`;stage-level source-hash 计算移入本模块作为唯一权威实现;`write_run_config` 增加 `formal_full_clean_worktree_required`、`exp4_worktree_clean_at_start` 与四个 stage hash 字段 |
| `exp4/validation/run_provenance.py` | 全面重构:`exp4_stage_provenance.json` 升级为 `exp4_stage_provenance_v2` 显式 schema;审计区分 reuse eligibility 与 execution mode;输出 per-stage `stored_hash/current_hash/hash_match/record_present/execution_mode`;新增 `simulation_provenance_verified`、`downstream_provenance_verified`、`run_lineage_valid`、`source_unchanged_during_run` 等总体状态;`full_simulation_reuse_decision` 保留为兼容字段并映射 `ELIGIBLE/NOT_ELIGIBLE/UNKNOWN`;新增 `record_downstream_rebuild`、`raw_simulation_artifacts_complete`、`recompute_calibration_hash` |
| `exp4/pipeline.py` | 运行前冻结 stage hash;simulation 完成后校验 simulation stage hash 未变;结束后校验 complete source hash / commit 未变,变化则写 `exp4_source_changed_marker.json` 并令 engineering FAIL;写入 FRESH lineage 与 v2 stage record(含 calibration hash 与 `source_unchanged_during_run`) |
| `main.py` | Formal Full 启动前 clean-worktree + resolvable-commit gate(`FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE` / `FORMAL_FULL_REFUSED_UNRESOLVABLE_GIT_COMMIT`);`aggregate/tables/plot/validate/report` 下游重建后调用 `record_downstream_rebuild` 刷新 lineage 与 stage record;`provenance` 命令做独立 calibration 重算 |
| `promote_results.py` | 删除弱检查 `downstream_stage_provenance_complete = all(stage_source_hashes.values())`;替换为 lineage/stage-record/hash-match/source-unchanged 等 15+ 显式 gates;FRESH 额外要求 null source run、recorded commit 匹配、complete/config/calibration hash 匹配;REUSED 要求 source run id + reconciliation artifact;旧 run 无 lineage → `run_lineage_valid=false` → promotion FAIL |
| `exp4/reporting/implementation_status.py` | 删除 `FULL_SIMULATION_REUSED` / `DOWNSTREAM_ARTIFACTS_REBUILT`;新增 `FULL_SIMULATION_REUSE_ELIGIBLE`、`FULL_SIMULATION_EXECUTION_MODE`、`FULL_SIMULATION_SOURCE_RUN_ID`、`DOWNSTREAM_ARTIFACTS_EXECUTION_MODE`、`DOWNSTREAM_SOURCE_RUN_ID`;`FULL_SIMULATION_RERUN_REQUIRED` 仅当 provenance 全部验证通过才为 NO |
| `exp4/outputs/manifests.py` | `output_manifest.json` 增加 `run_lineage` 与 `run_provenance` 段(lineage schema、execution modes、source/stage hashes、algorithm version) |
| `exp4/reporting/run_summary.py` | run summary 增加 Run lineage 段(execution modes、source run、clean start、source unchanged)与明确四问 |

### 1.2 新增的文件

| 文件 | 内容 |
| --- | --- |
| `exp4/outputs/run_lineage.py` | 不可变 `RunLineage` dataclass 与 `exp4_run_lineage_v1` schema;`fresh_lineage`、`write_run_lineage`、`load_run_lineage`、`lineage_valid`、`mark_downstream_rebuilt`;允许值 `FRESH/REUSED/UNKNOWN` 与 `INLINE_FRESH/REBUILT_FROM_OWN_SIMULATION/REBUILT_FROM_REUSED_SIMULATION/UNKNOWN` |
| `tests/unit/test_run_lineage.py` | 8 个 lineage 契约测试 |
| `tests/unit/test_full_clean_worktree_gate.py` | 8 个 clean-worktree / full gate 测试(临时 git fixture) |
| `tests/unit/test_promotion_lineage.py` | 8 个 promotion lineage 测试(含有效 fresh full fixture) |

### 1.3 变更声明

```text
SCIENTIFIC_LOGIC_UNCHANGED=YES
FROZEN_PARAMETERS_UNCHANGED=YES
```

- Module A/B/C 科学定义、estimands、attribution route、audit estimator、calibration 数值逻辑均未修改。
- 仅修改 provenance / lineage / status / promotion / manifest / reporting 语义。
- Schema 变更:`exp4_stage_provenance.json` 从平铺 hash 升级为 `exp4_stage_provenance_v2`(stages 嵌套);`exp4_run_lineage.json` 新增(`exp4_run_lineage_v1`);run config 新增 `formal_full_clean_worktree_required`、`exp4_worktree_clean_at_start` 与四个 stage hash。

---

## 2. 状态语义:eligibility ≠ actual reuse

两个 fixture 拥有相同的当前 source hash / stage hash(均与当前源码一致),但 execution mode 完全由 lineage 决定:

**Fresh fixture**(`simulation_execution_mode=FRESH`):

```json
{
  "full_simulation_reuse_eligibility": "ELIGIBLE",
  "simulation_execution_mode": "FRESH",
  "simulation_source_run_id": null,
  "downstream_execution_mode": "INLINE_FRESH",
  "simulation_provenance_verified": true,
  "source_unchanged_during_run": true
}
```

**Reused fixture**(`simulation_execution_mode=REUSED`,source run 存在但无 reconciliation artifact):

```json
{
  "full_simulation_reuse_eligibility": "NOT_ELIGIBLE",
  "simulation_execution_mode": "REUSED",
  "simulation_source_run_id": "full_source_1",
  "downstream_execution_mode": "REBUILT_FROM_REUSED_SIMULATION",
  "simulation_provenance_verified": false,
  "reconciliation_artifact_present": false
}
```

结论:hash 匹配只决定 `reuse_eligibility`;是否 "实际复用" 只由 lineage 的 `simulation_execution_mode` / `simulation_source_run_id` 表达。二者不再混淆。

### 2.1 旧 Full 的当前状态

`full_20260806T021401Z_5627f17b`(无 lineage):

```text
FULL_RUN_EXECUTED=YES
FULL_SIMULATION_REUSE_ELIGIBLE=UNKNOWN
FULL_SIMULATION_EXECUTION_MODE=UNKNOWN
FULL_SIMULATION_SOURCE_RUN_ID=UNKNOWN
FULL_SIMULATION_RERUN_REQUIRED=YES
DOWNSTREAM_ARTIFACTS_EXECUTION_MODE=UNKNOWN
PAPER_PROMOTION_EXECUTED=NO
```

旧 provenance 不明的 Full 不会被重新启用或自动猜测为 FRESH/REUSED。

---

## 3. Provenance

### 3.1 Stored/current hash comparison(v2 stage record)

`audit_run_provenance` 对每个 stage 输出 `stored_hash / current_hash / hash_match / record_present / execution_mode`。Promotion 要求四个 stage 的 `record_present=true` 且 `hash_match=true`。仅有非空 current stage hashes 但缺少 v2 stage record 的 legacy run 不通过(`record_present=false`)。

### 3.2 Stage record checks

- Fresh run:simulation 完成后校验 simulation stage hash 未变;结束后写 v2 stage record(含 complete source hash、config hash、calibration hash、`source_unchanged_during_run`)。
- 同一次运行期间源码变化 → 写 `logs/exp4_source_changed_marker.json` 且 engineering status=FAIL,不能 promotion。
- 下游重建(`aggregate/tables/plot/validate/report`)→ 保留原 simulation stage record,更新 downstream stages,lineage downstream mode 改为 `REBUILT_FROM_OWN_SIMULATION`/`REBUILT_FROM_REUSED_SIMULATION`,写清 rebuild timestamp。

### 3.3 Clean-worktree gate

```text
FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE=PASS (CLI 实测拒绝并列出 dirty 文件)
FORMAL_FULL_REFUSED_UNRESOLVABLE_GIT_COMMIT=PASS (测试覆盖)
Fast/Middle 允许 dirty worktree 并记录 exp4_worktree_clean_at_start=false (实测 fast 记录 false)
```

### 3.4 Promotion fixture results

| 场景 | 结果 |
| --- | --- |
| 有效 fresh full fixture | PASS(全部 gates 通过,`formal_full_started_clean=true`、`source_unchanged_during_run=true`) |
| 无 lineage 的 legacy full | FAIL(`run_lineage_present=false`) |
| fresh full 但 reporting stage hash 被篡改 | FAIL(`reporting_stage_hash_match=false`) |
| fresh full 但 simulation stage hash 被篡改 | FAIL(`simulation_stage_hash_match=false`、`simulation_provenance_verified=false`) |
| 伪造 REUSED lineage 无 source run | FAIL(`run_lineage_valid=false`) |
| REUSED lineage 有 source run 但无 reconciliation | FAIL(`simulation_provenance_verified=false`) |
| `source_unchanged_during_run=false` | FAIL |
| 缺少 v2 stage record | FAIL(`simulation_stage_record_present=false` 等) |

---

## 4. 测试

```text
COMPILE=PASS
PYTEST=PASS (78 passed)
FAST=PASS
LINEAGE_CONTRACT=PASS
STAGE_PROVENANCE=PASS
FULL_CLEAN_WORKTREE_GATE=PASS
TABLE_SEMANTICS=PASS
MONTE_CARLO_GATE=PASS
EXP1_EXP4_BOUNDARY=PASS
FORMAL_FULL_READY=YES
```

Fast 运行:`fast_20260806T080932Z_ae25ef5b`

- Fast engineering status:`PASS`
- Fast scientific status:`PASS`
- `main_table_complete=PASS`(两行主表)、`primary_monte_carlo_precision_pass=PASS`(non-full 规则)、`EXP1_EXP4_BOUNDARY=PASS`
- Fast promotion dry-run 被拒绝(tier 非 Full)
- 新 lineage artifact 存在:`exp4_run_lineage_v1`,`simulation_execution_mode=FRESH`,`exp4_worktree_clean_at_start=false`(dirty worktree 被正确记录)
- 下游重建验证:lineage 更新为 `REBUILT_FROM_OWN_SIMULATION`,simulation stage record 保留

---

## 5. 重跑范围

```text
EXP4_NEW_FULL_REQUIRED=YES
EXP1_RERUN_REQUIRED=NO
EXP2_RERUN_REQUIRED=NO
EXP3_RERUN_REQUIRED=NO
MIDDLE_RERUN_REQUIRED=NO
```

- 本轮只修改 provenance/lineage/status/promotion/manifest/reporting,未修改 execution/resume 逻辑或 simulation task scheduling,因此不重跑 Middle。
- 旧 provenance 不明的 Full(`full_20260806T021401Z_5627f17b`)不会被重新启用;Exp4 唯一需要重跑的正式计算是新的、来源完整的 Full。

---

## 6. 操作边界

```text
FULL_RUN_EXECUTED_BY_THIS_TASK=NO
PAPER_PROMOTION_EXECUTED=NO
GIT_COMMIT_EXECUTED=NO
GIT_PUSH_EXECUTED=NO
```

- 未自动执行 Full、未 commit/push、未创建 branch、未自动 promotion。
- 未修改旧 Full 的 `run_config.json` 来伪造 provenance(旧 run 的 lineage 缺失 → 保持 `UNKNOWN`)。
- 未将 hash compatibility 解释为 actual reuse。

---

## 7. 唯一下一步

**情况 A 适用:工作区仍有未提交修改(本轮所有改动未 commit)。**

下一步只能是:

```text
人工审查并提交本轮修改(commit exp4_controlled_route_audit 的全部变更)
```

在提交且 worktree 干净之前,不得运行 Formal Full(Full gate 会以 `FORMAL_FULL_REFUSED_DIRTY_EXP4_WORKTREE` 拒绝)。提交干净后,下一步命令:

```powershell
python main.py full --n-jobs 8
python main.py status
python promote_results.py --run-dir outputs/runs/<new_full_run_id> --approve-claims --dry-run
```

(不得自动正式 promotion。)

---

## 8. 最终验收标准

```text
SCIENTIFIC_LOGIC_UNCHANGED=YES
FROZEN_PARAMETERS_UNCHANGED=YES
EXP1_EXP4_BOUNDARY=PASS
REUSE_ELIGIBILITY_SEPARATED_FROM_EXECUTION_MODE=PASS
RUN_LINEAGE_CONTRACT=PASS
FORMAL_FULL_DIRTY_WORKTREE_REFUSAL=PASS
STAGE_HASHES_COMPARED_TO_STORED_RECORDS=PASS
LEGACY_FULL_PROMOTION_REFUSED=PASS
FRESH_FULL_FIXTURE_PROMOTION=PASS
FAST=PASS
FORMAL_FULL_READY=YES
```
