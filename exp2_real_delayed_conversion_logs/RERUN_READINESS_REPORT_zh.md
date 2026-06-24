# Exp2 重新运行前复核与修复报告

## 结论

该版本可以开始真实数据的 fast 重跑。此前会阻断 clean rerun 或造成输出语义不一致的四项问题均已修复；同时移除了 candidate-window 附录诊断中的重复嵌套 bootstrap，以避免不必要的长时间统计步骤。

真实 full 尚未在本次修复环境中执行。必须先运行真实 fast，并在 fast 的 self-check 与 code-check 均通过后再运行 full。

## 已修复的问题

| 问题 | 原因 | 当前处理 | 结果影响 |
|---|---|---|---|
| clean rerun hash guard | clean runner 会删除 outputs，但 self-check 曾要求旧的 before-hash 文件 | clean run 允许 hash regression 为 not applicable；只有显式 display-only replot audit 才启用 before/after hash 对照 | 不改变任何统计结果 |
| delay profile 统计单位错误 | 原实现按 conversion 去重，但一个 conversion 可有多个 source events | 改为按 eligible source-event rows 统计，并改为 `n_eligible_source_events`、`source_event_share_percent` | 改正 Panel A 语义；会改变该图/表的计数与比例 |
| UID=-1 sentinel | `-1`/`-1.0` 可能被当成同一真实 UID cluster | 与缺失 UID 一样过滤，并写入 integrity audit | 修正 bootstrap cluster 定义；可能轻微改变真实数据样本量和 CI |
| fixture 契约陈旧 | fixture 使用旧 route/gate 名称 | 同步为 arrival-bin anchor 与当前 scientific gates | 只影响测试有效性 |
| candidate-window nested bootstrap | 每个 window 重复运行 UID bootstrap，成本高但没有输出 CI | 改为 common-cohort point-estimate appendix diagnostic，并显式写入 `window_bootstrap_replicates=0` | 不改变主图/主统计的 bootstrap CI；候选窗口表不再声称 CI |
| failed self-check 破坏 figure bundle | 人工在运行中调用 self-check 可能将图 metadata 改写为失败状态 | self-check 现在只报告失败；full finalizer 仍负责 paper_result promotion | 防止检查动作污染结果 |

## 已验证的内容

运行：

```powershell
python tests\run_synthetic_integration.py
```

验证内容：

1. 使用 synthetic fixture 完整执行两次 fast pipeline：
   `precheck -> timeline -> route_assignment -> statistics -> figures -> tables -> self_check`。
2. 分别使用 `--n-jobs=1` 和 `--n-jobs=4`。
3. 两次 UID bootstrap 输出文件 SHA256 完全一致。
4. 最终 69 项 semantic self-check 全部通过。
5. static code-check 全部通过。
6. 真实数据输出未写入该修复包；包内没有伪造的 fast/full 结果。

## 真实数据运行顺序

将真实输入放入：

```text
inputs/pcb_dataset_final.tsv
```

先执行：

```powershell
python tests\run_synthetic_integration.py
python main.py --mode fast --n-jobs auto
python self_check.py --mode fast
python code_check.py --mode fast
```

必须检查：

```text
outputs/fast/metadata/run_status.json            status=success
outputs/fast/checks/exp2_self_check_report.md    failures=0
outputs/fast/processed/exp2_conversion_uid_integrity_summary.csv
outputs/fast/summaries/exp2_source_event_delay_profile.csv
outputs/fast/summaries/exp2_route_sensitivity_summary.csv
outputs/fast/summaries/exp2_candidate_window_sensitivity.csv
```

特别确认：

- UID integrity audit 中没有 `missing_reference` 或 `uid_mismatch`；
- 主 route sensitivity 的 bootstrap replicate 数为 fast 的 200；
- candidate-window 表显示 `window_bootstrap_replicates=0`，这是设计规定的 appendix point-estimate diagnostic，不是运行遗漏；
- source-event delay profile 使用 `n_eligible_source_events`，而不是 unique conversion count；
- scientific gates 全部通过。

随后执行：

```powershell
python main.py --mode full --n-jobs auto
python self_check.py --mode full
python code_check.py --mode full
```

Full 仅在最终 semantic self-check 通过后将 `paper_result` 提升为 true。

## 输出结构

```text
outputs/<mode>/metadata/  run_status、config snapshot、manifest、input identity
outputs/<mode>/precheck/  输入预检查和窗口摘要
outputs/<mode>/processed/ source-time cell、UID integrity、candidate、arrival、route assignment
outputs/<mode>/raw/       主 UID bootstrap replicates
outputs/<mode>/summaries/ 主 route sensitivity、delay profile、route divergence、window diagnostic、EM audit
outputs/<mode>/figures/   PDF、PNG、data CSV、metadata JSON
outputs/<mode>/tables/    CSV、Markdown、TeX
outputs/<mode>/checks/    semantic self-check、code-check、audit records
```

## 解释边界

Exp2 的主 estimand 仍是 observational logged credit-allocation 和 source-time decision-cell ranking sensitivity。它不估计 causal regret、线上 policy value、ROI、部署表现或新的因果效应。
