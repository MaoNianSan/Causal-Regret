# Exp2 本轮修正：原因分类、设计取舍与结论边界

## 1. 当前问题的完整分类

本轮 fast 之后，Exp2 的问题不能归为单一代码 bug。它由四类因素共同构成。

| 类别 | 具体表现 | 是否能通过代码修复 | 本轮处理 |
|---|---|---:|---|
| 数据与识别边界 | Criteo 是观察性 conversion log，没有新策略随机化、完整 propensity 或线上反事实回报 | 否 | Exp2 不称 causal regret、policy value、ROI 或随机化因果效果 |
| action/estimand 错配 | campaign-only action 使同一 conversion journey 的多触点在 action 层面塌缩，导致多条归因路线完全相同 | 不能靠更多 bootstrap 修复 | 改为 `campaign × source calendar day` decision cell |
| 工程与统计契约 | 缺 UID、跨 UID conversion、window sensitivity 错用主 cohort UID reference、旧 replay 的 label-rate RNG 泄漏 | 是 | 统一 UID integrity filter、window-specific audit、hard fail、自检 |
| 指标与图表语义 | 把 route-specific credited mass 画成近似 policy endpoint；把 arrival anchor 误读为真实 policy；将低信息量 audit 画成性能图 | 是 | 改主横轴、降级 appendix 诊断、修正 route display 名称 |

因此，原 campaign-only fast 不能支撑“多路线 campaign attribution comparison”，主要原因是 **数据结构与 action 定义不匹配**，不是 seed 不够、bootstrap 不够或图画得不够好。

## 2. 不能支持的结论

即使代码全部正确，Exp2 仍不能支持：

- causal regret；
- 新线上 policy 的 value；
- attribution route 的因果优劣；
- 真实经济收益或 ROI；
- Criteo attribution label 是完整 source ground truth。

这些限制来自数据识别条件，而不是实现不足。

## 3. 可以支持的结论

在同一 observed conversion journey cohort 中，不同 attribution routes 将 arriving conversion 分配到不同 **recorded source-time decision cells**，可以改变：

1. conversion credit 的 action-cell allocation；
2. 与 constructed arrival-bin anchor 的 allocation total-variation distance；
3. route-specific top-10 decision-cell ranking support；
4. source routes 之间的 pairwise top-k overlap。

这就是 Exp2 在证据链中的 `logged attribution sensitivity` 角色。

## 4. 为什么不强行加入 UID 的所有历史曝光

不采用“把同一 UID 的所有历史 campaign exposure 作为同一 conversion 的候选触点”。这样的做法会把 conversion ID 未记录为同一 journey 的曝光强行写入 attribution set，制造不可验证的跨 campaign 竞争。

新的 decision cell 只使用同一 `conversion_id` 的记录候选 impression，并按

\[
a_i=(\mathrm{campaign}_i,\;\mathrm{source\ calendar\ day}_i)
\]

聚合。这是 source-time 的透明粗化，不是扩展或伪造 conversion path。

## 5. 本轮主指标修正

此前的主 scatter 使用 route-specific top-k credited mass difference。这一数值同时受 credit concentration、top-k selection 和 action support 影响，容易被误读为 route utility 或 policy performance。

新的正文 Panel B 使用：

\[
x=\operatorname{TV}\!\left(
\text{route credit allocation},
\text{arrival-bin anchor allocation}
\right),
\]

\[
y=\operatorname{Top10Overlap}\!\left(
\text{route decision-cell set},
\text{arrival-bin anchor decision-cell set}
\right).
\]

其中 arrival-bin anchor 是 constructed diagnostic reference，不是线上动作或 policy value estimator。

`top_k_credited_mass_per_1000_events` 仍保留在主表中，作为 route-specific logged credit summary；不得在正文写成 utility、effect、return 或 positive performance claim。

## 6. 图表取舍

### 保留在正文

- `fig_exp2_attribution_sensitivity`
  - (a) eligible source-event delay composition；
  - (b) allocation TV distance vs arrival anchor 与 top-10 overlap。

### 保留为 appendix figure

- `fig_app_exp2_source_route_pairwise_overlap`
  - `k=10,20,50` 的 pairwise decision-cell overlap heatmaps；
  - 用来展示 source routes 的相互差异，而不是重复展示它们与 arrival anchor 的 0/1 曲线。

### 改为 appendix tables

- `tbl_app_exp2_source_linked_audit`：unique-labelled subset 的 bookkeeping audit；该 subset 可无 attribution discrimination，因此不再画成“验证性能图”。
- `tbl_app_exp2_candidate_window_sensitivity`：统一 common conversion-ID intersection，避免把 window 变化和 cohort coverage 变化混在折线中。
- `tbl_app_exp2_em_assignment_diagnostic`：EM nontriviality/entropy gate 的审计结果，不作为性能 endpoint。
- `tbl_app_exp2_cost_adjusted_credit_score`：transformed cost 的 robustness，仅附录。

## 7. 新的 hard gates

```text
[ ] main ambiguous_decision_cell_rate >= 0.01
[ ] 至少一对 core source routes（first / last / linear / time decay）TV > 0
[ ] EM nontrivial entropy share >= 0.001
[ ] action-cell universe > max(top-k)
[ ] UID integrity 与每个 candidate window 均无 missing_reference / uid_mismatch
[ ] main cost_lambda = 0
[ ] Arrival-bin anchor 标记 diagnostic_only=true、deployable=false
[ ] source-linked reference 不出现在 main cohort
```

若任一失败，不运行或不解释 full；而是将 Exp2 明确收缩为有限的 logged audit。

## 8. 与 experiment/appendix memo 的对应

本轮仍遵守 memo 的核心规定：

- Exp2 是 `logged attribution sensitivity`，不是 causal regret；
- 主 cohort 是 `all_conversion_candidates`；
- unique-labelled subset 只用于 source-linked audit；
- UID bootstrap：fast=200，full=1000；
- fast 不能标为 paper result；
- 所有 Figure 都需要 PDF/PNG/data/metadata bundle。

需要在论文和 Exp2 appendix 中更新的唯一 substantive expression 是：

```text
campaign ranking displacement
-> source-time decision-cell credit-allocation and ranking displacement
```
