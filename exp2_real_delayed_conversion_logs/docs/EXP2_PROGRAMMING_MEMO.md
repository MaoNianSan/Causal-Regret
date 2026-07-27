# Experiment 2 编程实施备忘录
## Delayed-Conversion Attribution Sensitivity

**版本**：Exp2 Programming Memo v1.1  
**日期**：2026-07-26  
**适用目录**：`exp2_delayed_conversion_attribution`  
**上位文件**：`Causal Regret Experiments Programming Memo v3.1`

---

# 0. 文档定位与覆盖关系

本备忘录是 Experiment 2 后续重新编程、运行、验收和论文出图的直接控制文件。后续实现应能够仅依据当前论文稿、全局实验备忘录 v3.1、本文件和 Criteo 原始字段说明完成 Exp2。

若本文件与历史 Exp2 实现、旧参数表、旧图表或旧输出冲突：

1. 科学任务边界以论文当前主线为准；
2. 全局工程规则以 v3.1 为准；
3. Exp2 的具体实现、命名、统计量和图表以本文件为准；
4. 旧输出只用于 migration audit，不得进入新 plotting 或 paper bundle。

本文件对 v3.1 的图表要求作进一步明确更新：正文 Panel B 使用 **pairwise allocation-TV dot-and-whisker plot**，将六组 source-route pairs 作为离散比较，并直接标注共享 Top-10 decision cells；原 source-route combined matrix 保留为附录数值审计图。该调整不改变 estimand，只改善主结果直观性并避免把离散 route pairs 误读为连续变量关系。

---

# 1. Exp2 的唯一任务与证据边界

## 1.1 唯一主命题

> The same delayed-conversion journeys do not uniquely determine source-time credit allocation or decision-cell ranking.

固定证据链：

\[
\text{same conversion journeys}
\rightarrow
\text{different attribution routes}
\rightarrow
\text{different source-time credit allocations}
\rightarrow
\text{different high-ranked decision cells}.
\]

## 1.2 Exp2 识别什么

Exp2 只识别：

- 同一日志 cohort 下 attribution route sensitivity；
- arrival-side accounting 与 source-time accounting 的差异；
- source-time attribution rules 之间的 allocation 差异；
- attribution route 对 high-ranked campaign-day cells 的影响；
- UID sampling variability 下的结果不确定性。

## 1.3 Exp2 不识别什么

Exp2 不识别：

- causally correct attribution rule；
- structural causal regret；
- counterfactual conversion lift；
- deployment policy value 或 off-policy value；
- ROI、profit、bidding efficiency；
- 某条 route 的线上真实改进；
- Criteo `attribution` 字段对应的完整 causal source truth。

代码、字段、文件名、图题、表题和正文中禁止使用会暗示上述结论的术语。

## 1.4 与其他实验的边界

| 实验 | 核心任务 | Exp2 不得侵入的部分 |
|---|---|---|
| Exp1 | source binding、alignment、structural regret | Exp2 不计算 causal regret |
| Exp2 | delayed-conversion log attribution sensitivity | 本实验唯一任务 |
| Exp3 | score–gap–ranking proxy recovery | Exp2 不训练 long-term proxy |
| Exp4 | labels、proxy、audit evidence 的 recoverability | Exp2 不做 calibration audit |

---

# 2. 当前代码迁移判断

当前 GitHub 版本可保留的数据读取、journey 构造、route engine、UID bootstrap、fast/full/promotion 和 figure metadata 思路，不应逐行修补旧 pipeline。

必须重构的问题：

1. 删除 top-50 campaign 截断；
2. EM 从 main routes 降为 appendix；
3. Arrival anchor 取消 modal-campaign fallback；
4. 旧 pairwise TV 实际是 journey-level assignment TV，必须更名；
5. 新增 aggregate decision-cell allocation TV；
6. 新增 common-support Kendall \(\tau_b\)；
7. 主图不再以 delay composition 为核心；
8. 删除 cost-adjusted utility、policy replay 等越界对象；
9. 统一 action/utility/regret/oracle 等旧命名；
10. 合并重复入口、检查和绘图脚本。

重构原则：**保留可靠的数据语义，重建 cohort contract、metric layer、命名、输出和图表。**

---

# 3. 目录结构与模块职责

## 3.1 目录改名

```text
exp2_real_delayed_conversion_logs
    ->
exp2_delayed_conversion_attribution
```

使用 `git mv`，不得形成两个长期并存的正式目录。

## 3.2 最终目录

```text
exp2_delayed_conversion_attribution/
├── main.py
├── clean.py
├── promote.py
├── config.yaml
├── README.md
├── requirements.txt
├── contracts.py
├── data_io.py
├── cohort.py
├── routes.py
├── metrics.py
├── bootstrap.py
├── reporting.py
├── validation.py
├── inputs/
│   └── README.md
├── tests/
│   ├── test_cohort.py
│   ├── test_routes.py
│   ├── test_metrics.py
│   ├── test_bootstrap.py
│   └── test_pipeline.py
└── outputs/
```

不再长期保留功能重复的 `run_exp2.py`、`reproduce_fast.py`、`reproduce_full.py`、`reproduce_paper.py`、`finalize_exp2.py`、多个 self/code check、多个 plot 文件和 `sequential_replay.py`。

## 3.3 职责

- `main.py`：命令解析、阶段编排、进度与摘要；不得写统计公式。
- `clean.py`：只能独立调用，安全清理 Exp2 输出；不得由 `main.py` 隐式触发。
- `promote.py`：仅提升已通过 gate 的 full run；不得重算。
- `contracts.py`：canonical columns、route registry、metric IDs、schemas、tolerances。
- `data_io.py`：schema、分块读取、timestamp、input manifest、I/O。
- `cohort.py`：去重、journey、candidate window、UID/campaign integrity、cell universe、common cohort。
- `routes.py`：构造 attribution weights；不读取最终结果，不调参。
- `metrics.py`：credit、allocation、ranking、TV、Overlap、Kendall、ambiguity。
- `bootstrap.py`：UID sampling、replicate metrics、CI、并行一致性。
- `reporting.py`：只读取 derived files 出图和制表；不得重算 estimand。
- `validation.py`：engineering/scientific gates、figure/table reconstruction、paper gate。

---

# 4. 命名规范

## 4.1 规则

- 文件、函数、变量：`snake_case`
- 数据类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 布尔：`is_`、`has_`、`uses_`、`passes_`
- ID：`_id`
- 数量：`_count`
- 比例：`_rate` 或 `_share`
- CI：`_ci_lower`、`_ci_upper`
- timestamp：`_timestamp_utc`
- date：`_date_utc`
- route 权重：`credit_weight`
- bootstrap 抽样倍数：`bootstrap_multiplicity`

不得用同一个 `weight` 表示 route credit 和 bootstrap multiplicity。

## 4.2 实验元数据

```text
experiment_id = exp2
experiment_slug = delayed_conversion_attribution
experiment_title = Attribution Sensitivity in Delayed-Conversion Logs
```

## 4.3 禁用术语

正式新 pipeline 禁止：

```text
action
action_id
candidate_action_id
reward
regret
causal_regret
offline_policy_value
policy_utility
roi
profit
uplift
oracle
ground_truth
```

旧 `action_id` 统一迁移为 `decision_cell_id`。

## 4.4 核心字段

Source-event：

```text
source_event_id
raw_row_id
user_id
conversion_id
campaign_id
event_timestamp_utc
conversion_timestamp_utc
is_click
is_conversion
source_date_utc
source_lag_days
```

Journey：

```text
journey_id
user_id
conversion_id
conversion_timestamp_utc
candidate_event_count
candidate_cell_count
candidate_campaign_count
is_attribution_ambiguous
is_attribution_degenerate
is_primary_eligible
exclusion_reason
arrival_anchor_cell_id
```

Decision cell：

```text
decision_cell_id
campaign_id
source_date_utc
eligible_impression_count
eligible_journey_count
is_support_eligible
```

Route assignment：

```text
journey_id
route_id
decision_cell_id
credit_weight
source_lag_days
analysis_tier
route_role
```

## 4.5 Route IDs

```text
arrival_bin_anchor
first_touch
last_touch
linear_credit
time_decay_credit
em_soft_credit
logged_attribution_reference
```

显示与角色：

| ID | Display label | Role |
|---|---|---|
| `arrival_bin_anchor` | Arrival-time anchor | diagnostic anchor |
| `first_touch` | First click or touch | primary source route |
| `last_touch` | Last click or touch | primary source route |
| `linear_credit` | Linear attribution | primary source route |
| `time_decay_credit` | Time-decay attribution | primary source route |
| `em_soft_credit` | EM soft attribution | appendix diagnostic |
| `logged_attribution_reference` | Logged attribution reference | audit reference |

固定顺序不得按结果调整。

---

# 5. 时间、事件与 Journey

## 5.1 时间标准

```text
timestamp_timezone = UTC
source_date = floor event timestamp to UTC calendar day
arrival_date = floor conversion timestamp to UTC calendar day
daylight_saving_adjustment = false
```

不得使用运行机器本地时区。

## 5.2 Source-event ID 与去重

优先使用原始稳定事件 ID。若无，生成稳定 hash：

```text
stable_hash(user_id, conversion_id, campaign_id,
            event_timestamp_utc, is_click, raw_row_sequence)
```

规则：

1. 完全重复行保留一条；
2. 同 timestamp/campaign/conversion 但 click 不同，不自动合并；
3. 无法判定的 ambiguous duplicate 触发 `STOP_AND_REVIEW`；
4. 输出去重前后和异常数量。

## 5.3 Journey

每个 journey 对应一个 `conversion_id`：

\[
\mathcal E_j=\{e:\operatorname{conversion\_id}(e)=\operatorname{conversion\_id}(j)\}.
\]

禁止从同一 UID 的其他 conversion journey 借用曝光或人工拼接 path。

## 5.4 Candidate window

Primary：

\[
H_{\mathrm{candidate}}=30\text{ days}.
\]

候选事件满足：

\[
0\le t_j^{\mathrm{conv}}-t_{je}^{\mathrm{src}}\le30\text{ days}.
\]

Targeted：7 days。既有规范 1-day、14-day 结果可迁移，但不强制新跑。

## 5.5 Complete lookback

若：

\[
t_j^{\mathrm{conv}}-30\text{ days}<t_{\min}^{\mathrm{log}},
\]

主分析排除该 journey。不得把左截断 path 当作完整 path。

## 5.6 UID integrity

Retained journey 必须有且仅有一个有效 UID。`-1`、`-1.0`、空字符串和 NA 均为缺失。缺失 UID 不得合并为一个 bootstrap cluster。

---

# 6. Decision cell 与 campaign universe

## 6.1 Decision cell

\[
c=(\text{campaign ID},\text{source UTC calendar day}).
\]

不可退回 campaign-only。

## 6.2 Campaign universe

删除 top-50 campaign 逻辑。Primary 使用所有通过 route-independent 数据完整性和 cell-support 条件的 campaigns。

禁止：

- 按 conversion 数或 route 结果筛 campaign；
- 运行后改变 campaign universe；
- 低支持时自动回退到 top campaigns。

## 6.3 Cell support

Primary：

\[
N_{\mathrm{imp}}(c)\ge50.
\]

规则：

1. attribution 前计算并冻结；
2. 所有 routes 共用；
3. bootstrap 内不重筛；
4. 不用 credited conversion 作门槛；
5. 不自动降低；
6. denominator 固定为 eligible impressions。

Appendix sensitivity：25、100；不与 window/top-k 形成完整组合。

## 6.4 Multi-campaign journeys

Primary 要求：

\[
N_{\mathrm{candidate\ campaigns},j}=1.
\]

多 campaign journey 排除出 primary，进入 appendix exclusion audit。禁止 modal-campaign fallback。必须报告排除 journeys、UIDs、比例和 candidate-cell 分布。

---

# 7. Primary common cohort

Cohort ID：

```text
primary_common_journey_cohort
```

进入条件：

1. conversion ID 有效；
2. UID 唯一且非缺失；
3. 30-day lookback 完整；
4. 至少一个 candidate source event；
5. 至少一个 support-eligible cell；
6. candidate campaign 唯一；
7. Arrival anchor 可映射到 frozen cell universe；
8. 不依赖 route 结果；
9. 不依赖 bootstrap replicate。

所有 primary routes 的 `journey_set_hash`、`decision_cell_universe_hash`、`eligible_impression_denominator_hash` 必须一致。

---

# 8. Attribution routes

## 8.1 Arrival-time anchor

对 unique-campaign journey \(j\)，campaign 为 \(g_j\)：

\[
c_j^{\mathrm{arr}}=(g_j,\operatorname{date}_{UTC}(t_j^{\mathrm{conv}})).
\]

\[
w_{j,c}^{\mathrm{arr}}=\mathbf1\{c=c_j^{\mathrm{arr}}\}.
\]

元数据：

```text
route_role = diagnostic_anchor
source_bound = false
deployable = false
ground_truth = false
```

禁止 modal campaign、nearest source fallback、source-labelled fallback 或静默新建 cell。

## 8.2 First click or touch

有 click：最早 clicked candidate；无 click：最早 eligible touch。全部 credit 给对应 cell。

Tie-break：

```text
event_timestamp_utc ascending
campaign_id ascending
source_date_utc ascending
source_event_id ascending
```

## 8.3 Last click or touch

有 click：最后 clicked candidate；无 click：最后 eligible touch。Tie-break 固定，不依赖 DataFrame 行顺序。

## 8.4 Linear attribution

先对 journey 内 unique decision cells 去重：

\[
\mathcal C_j=\{c:\text{journey }j\text{ has a candidate event in }c\}.
\]

\[
w_{j,c}^{\mathrm{lin}}=\frac{\mathbf1\{c\in\mathcal C_j\}}{|\mathcal C_j|}.
\]

不是对 candidate rows 均分。

## 8.5 Time-decay attribution

对每个 journey-cell 取最后一次 candidate event：

\[
t_{j,c}^{\mathrm{last}}=\max_{e\in\mathcal E_{j,c}}t_e.
\]

\[
\Delta_{j,c}=\frac{t_j^{\mathrm{conv}}-t_{j,c}^{\mathrm{last}}}{1\text{ day}}.
\]

固定：

\[
\lambda=0.5\text{ day}^{-1}.
\]

\[
w_{j,c}^{\mathrm{decay}}=
\frac{\exp(-\lambda\Delta_{j,c})}
{\sum_{c'\in\mathcal C_j}\exp(-\lambda\Delta_{j,c'})}.
\]

不调参，不运行 lambda grid。

## 8.6 EM soft attribution

仅 appendix：

```text
analysis_tier = appendix
route_role = appendix_diagnostic
diagnostic_only = true
deployable = false
```

不进入正文主图和 primary pair map。

## 8.7 Logged attribution reference

仅用于 unique-labelled audit subset：

```text
route_role = audit_reference
analysis_tier = appendix
ground_truth = false
```

若 candidate count 几乎均为 1，标记 `attribution_nondiscriminative`。

## 8.8 Credit conservation

每个 journey、route：

\[
w_{j,c}^{(r)}\ge0,\qquad\sum_cw_{j,c}^{(r)}=1.
\]

容差 `1e-10`；违反即 hard fail。

---

# 9. 统计对象与指标

## 9.1 Route credit

\[
C_r(c)=\sum_{j=1}^{J}w_{j,c}^{(r)},
\qquad
\sum_cC_r(c)=J.
\]

## 9.2 Allocation distribution

\[
Q_r(c)=\frac{C_r(c)}{\sum_{c'}C_r(c')}=\frac{C_r(c)}{J},
\qquad\sum_cQ_r(c)=1.
\]

## 9.3 Decision-cell score

\[
S_r(c)=\frac{C_r(c)}{N_{\mathrm{imp}}(c)}.
\]

固定 denominator 为 `eligible_impression_count`。不使用 UID、journey、conversion、cost 或 route-specific denominator；不平滑，不加 pseudo-credit。

## 9.4 Arrival displacement

\[
TV_{\mathrm{arr}}(r)=\frac12\sum_{c\in\mathcal C}|Q_r(c)-Q_{\mathrm{arr}}(c)|.
\]

字段：`allocation_tv_vs_arrival`。

## 9.5 Source-route aggregate allocation TV

\[
TV(r,r')=\frac12\sum_{c\in\mathcal C}|Q_r(c)-Q_{r'}(c)|.
\]

字段：`allocation_tv`。这是正文 pairwise allocation 指标。

## 9.6 Journey-level assignment TV

\[
TV_j(r,r')=\frac12\sum_c|w_{j,c}^{(r)}-w_{j,c}^{(r')}|.
\]

\[
\overline{TV}_{\mathrm{journey}}(r,r')=\frac1J\sum_jTV_j(r,r').
\]

字段：`mean_journey_assignment_tv`；只放附录。旧 `pairwise_credit_allocation_tv_distance` 必须迁移为该名称。

## 9.7 Top-k overlap

\[
\operatorname{Overlap@}k(r,r')=
\frac{|\operatorname{Top}_k(r)\cap\operatorname{Top}_k(r')|}{k}.
\]

Primary \(k=10\)；targeted \(k=20,50\)。

\[
\operatorname{RankingDisplacement@}k=1-\operatorname{Overlap@}k.
\]

Stable tie-break：score descending、campaign ascending、date ascending、cell ID ascending。eligible cells 不大于最大 k 时 hard fail，不自动缩小 k。

## 9.8 Kendall \(\tau_b\)

使用 tie-aware Kendall \(\tau_b\)。Common active support：

\[
\mathcal C_{r,r'}^{\mathrm{active}}
=\{c:C_r(c)>0\text{ or }C_{r'}(c)>0\}.
\]

零 credit 是有效观测，不是 missing。同步报告 positive/common support counts。

---

# 10. Ambiguity diagnostics

使用 unique candidate decision-cell count：

\[
m_j=|\mathcal C_j|.
\]

```text
is_attribution_degenerate = candidate_cell_count == 1
is_attribution_ambiguous = candidate_cell_count >= 2
```

固定 strata：1、2、3+ candidate cells。每层报告 journeys、UIDs、share、cells、aggregate TV、journey TV、Overlap@10、ranking displacement、Kendall、entropy 和 maximum assignment weight。

Soft-route entropy：

\[
H_j^r=-\sum_cw_{j,c}^{(r)}\log w_{j,c}^{(r)},
\qquad
M_j^r=\max_cw_{j,c}^{(r)}.
\]

Ambiguity strata 进入 cohort summary 和附录，不增加正文 panel。

---

# 11. UID-cluster bootstrap

固定：

```text
bootstrap_unit = user_id
fast_repetitions = 200
full_repetitions = 1000
confidence_level = 0.95
interval_method = percentile
bootstrap_seed = 20260725
```

每次 replicate：对 unique UIDs 有放回抽样；某 UID 抽中 m 次，其全部 journeys multiplicity 为 m；重算 credit、allocation、score、Arrival TV、source-route TV、Overlap、ranking displacement 和 Kendall。

Bootstrap 中不重建 cohort、window、cell universe、support、route definitions、route order 或 top-k。因此区间表示 frozen specification 下的 UID sampling variability。

同一 seed 下 `n_jobs=1` 与并行运行必须产生相同 replicate IDs 和结果。

---

# 12. Targeted 与 appendix

Targeted 仅包括：

1. candidate window = 7 days；
2. top-k = 20、50；
3. cell support = 25、100。

不得形成完整组合。

Window sensitivity 必须先取比较窗口的 common journey cohort，只报告 point estimate：

```text
window_bootstrap_replicates = 0
window_uncertainty_status = not_computed
analysis_tier = targeted
```

Appendix 可包括 delay composition、ambiguity strata、三张 pairwise matrices、rank shift、EM、logged reference、journey TV、multi-campaign audit、window/top-k/support sensitivity。

正式删除：sequential replay、cost-adjusted policy utility、ROI、uplift、surrogate attribution regret、policy-value wording。

---

# 13. 配置文件冻结值

```yaml
experiment:
  experiment_id: exp2
  experiment_slug: delayed_conversion_attribution

input:
  raw_file: inputs/pcb_dataset_final.tsv
  separator: "\t"
  timestamp_unit: seconds
  timezone: UTC
  chunk_size: 500000

cohort:
  primary_cohort_id: primary_common_journey_cohort
  candidate_window_days: 30
  require_complete_lookback: true
  require_unique_uid_per_journey: true
  require_unique_candidate_campaign: true
  prohibit_modal_campaign_fallback: true

decision_cell:
  definition: campaign_id_x_source_date_utc
  minimum_impressions: 50
  support_sensitivity: [25, 100]

routes:
  primary:
    - arrival_bin_anchor
    - first_touch
    - last_touch
    - linear_credit
    - time_decay_credit
  appendix:
    - em_soft_credit
  audit_reference:
    - logged_attribution_reference
  time_decay_rate_per_day: 0.5
  time_decay_cell_timestamp: latest_event_in_cell

ranking:
  score: credited_conversion_mass_per_eligible_impression
  primary_top_k: 10
  targeted_top_k: [20, 50]
  kendall_variant: tau_b
  kendall_support: union_positive_credit_cells

statistics:
  confidence_level: 0.95
  bootstrap_unit: user_id
  bootstrap_interval: percentile
  bootstrap_seed: 20260725
  fast_repetitions: 200
  full_repetitions: 1000
```

删除旧 top campaign、conversion threshold、cost utility、legacy soft routes、policy seeds 和 trajectory bins 配置。

---

# 14. 运行模式与命令

```text
python main.py fast
python main.py full
python promote.py --run-id <full_run_id>
python clean.py
```

Fast 包含 synthetic contract fixture 和稳定 UID-hash 真实数据子集，不能简单读取前 n 行。Fast 不得改变 support threshold，永远 `paper_result=false`。

Full 使用完整 route-independent eligible cohort、30-day window、所有 support-eligible campaigns、1000 UID bootstrap、targeted/appendix outputs 和 full self-check。Full 完成后仍 `paper_result=false`，直到独立 promotion。

Promotion 只允许在 engineering/scientific PASS、primary outputs 完整、bootstrap 完整、figures/tables 可重建、claims within scope 时执行；不得重算。

---

# 15. 输出合同

Run ID：

```text
exp2-<tier>-YYYYMMDDTHHMMSS+ZZZZ
```

目录：

```text
outputs/<run_id>/
├── run_manifest.json
├── derived/
├── figures/
├── tables/
├── audit/
└── logs/
```

Derived：

```text
cohort_summary.csv
journey_manifest.parquet
decision_cell_universe.parquet
route_assignments.parquet
route_allocations.parquet
arrival_displacement.csv
source_route_pairwise.csv
kendall_support.csv
ambiguity_strata.csv
bootstrap_draws.parquet
targeted_validation.csv
exclusion_summary.csv
```

所有文件必须包含或关联 run/tier/paper/analysis/config/code/input/cohort/cell hashes。

`source_route_pairwise.csv` 至少包含：route pair、allocation TV 和 CI、journey TV、top-k overlap 和 CI、ranking displacement 和 CI、Kendall 和 CI、common support、journey/user counts。

---

# 16. 正文图表

## 16.1 Main figure：两面板

### Panel A：Arrival-anchor displacement

横向 dot-and-whisker。四条 source routes 固定顺序；横轴为 \(TV(Q_{arrival},Q_r)\in[0,1]\)；显示 point estimate、95% UID CI 和右侧 Top-10 overlap。Arrival anchor 不画成 method point。

### Panel B：Pairwise allocation-TV dot-and-whisker

六个 source-route pairs 按固定顺序置于纵轴。横轴为 allocation TV，显示 point estimate 与横向 95% UID-bootstrap interval；每行右侧直接标注共享 Top-10 decision cells 的 point estimate 与 interval。不得使用 scatter-map、纵向误差条或 legend 映射 route pair。横轴从 0 开始，上界按最大 CI upper 向上取整至 0.05，且至少为 0.15、最多为 1.0。

## 16.2 正文表

Cohort table 只保留 retained journeys/UIDs、eligible campaigns/cells、1/2/3+ candidate shares、ambiguity rate、candidate count median/p90、bootstrap unit/repetitions。

Primary route table 可报告 TV vs arrival、CI、Overlap@10、ranking displacement、positive-credit cells。

## 16.3 附录

- 三个 pairwise matrices：TV、Overlap@10、Kendall；
- ambiguity strata；
- rank-shift；
- delay composition；
- EM 和 logged reference audit；
- targeted sensitivities。

图表统一 95% intervals、固定 route order、不聚类、不截断、不用 3D/双轴/彩虹色阶/显著性星号。Panel A 与 overlap matrix 保持理论范围；pairwise TV 主图和 TV matrix 使用从 0 开始的审计式动态上界，避免小差异被压缩在 [0,1] 左端。PDF/SVG 为论文主格式，PNG 仅预览。Plotting 只能读 frozen derived files。

---

# 17. Self-check 与 hard gates

## 17.1 Input/cohort

- required columns 完整；
- timestamps 为 UTC；
- ambiguous duplicates = 0；
- retained journey UID 唯一；
- missing UID 未形成伪 cluster；
- complete lookback 已执行；
- multi-campaign 未进入 primary；
- campaign universe route-independent；
- common cohort hashes 一致。

## 17.2 Routes

- credit 非负；
- journey-route credit sum = 1；
- route total credit = retained journeys；
- Arrival 无 modal fallback；
- Linear 按 unique cells；
- Time-decay 在 cell level；
- EM 不进入 primary；
- logged reference 不标 ground truth。

## 17.3 Metrics

- allocation sum = 1；
- TV 范围、对称、对角 0；
- overlap 范围、对称、对角 1；
- Kendall 在 [-1,1] 且 common support 明确；
- ranking denominator 所有 routes 相同；
- cell universe 大于最大 top-k；
- tie-break deterministic。

## 17.4 Bootstrap/reporting

- UID 不拆分；
- 1000 replicates 完整；
- 并行一致；
- CI 可由 draws 重建；
- pairwise metrics 纳入 bootstrap；
- plotting 不读 raw、不重算；
- figure source-data 等于 plotted values；
- fast/full 不自动 paper eligible。

## 17.5 Scientific gates

只检查设计与证据条件，不要求特定结果。禁止设置 TV 必须大于某值、Overlap 必须等于 0、Kendall 必须小于某值。新结果弱于旧结果时，减弱正文结论，不调整参数追求旧数值。

---

# 18. STOP_AND_REVIEW

以下任一触发停止：

1. multi-campaign 排除导致 primary cohort 严重失去代表性；
2. Arrival anchor 无法在不引入 campaign attribution 时定义；
3. ambiguity 几乎消失；
4. source-route difference 主要由 support mismatch 驱动；
5. Kendall common support 不足；
6. 1000 bootstrap 无法完整运行；
7. credit 不守恒；
8. figure 与 source-data 不一致；
9. 新结果与论文当前叙述发生实质冲突。

STOP_AND_REVIEW 不允许自动放宽门槛或静默 fallback。

---

# 19. Migration manifest

至少记录：

| Legacy | New | 处理 |
|---|---|---|
| `action_id` | `decision_cell_id` | rename |
| `arrival_anchor` | `arrival_bin_anchor` | normalize |
| `first_click` | `first_touch` | normalize |
| `last_click` | `last_touch` | normalize |
| `linear_attribution` | `linear_credit` | normalize |
| `time_decay_soft` | `time_decay_credit` | normalize |
| `soft_attribution_em` | `em_soft_credit` | appendix only |
| `source_linked_reference` | `logged_attribution_reference` | audit only |
| old pairwise TV | `mean_journey_assignment_tv` | rename estimand |
| aggregate allocation TV | `allocation_tv` | recompute |
| cost utility | — | retire |
| sequential replay | — | retire |
| top-50 filter | — | remove |
| modal campaign anchor | — | remove |

---

# 20. 实施顺序

1. **Freeze**：记录 commit、旧 manifest、旧 figure hashes、migration manifest。
2. **Contracts**：schemas、route/metric registries、metadata、errors、no-fallback。
3. **Data/cohort**：读取、UTC、去重、journey、lookback、UID/campaign、cells、common cohort。
4. **Routes**：Arrival、First、Last、Linear、Time-decay、EM、reference、conservation。
5. **Metrics**：credit、allocation、scores、TV、Overlap、Kendall、ambiguity。
6. **Bootstrap**：UID sample、deterministic seeds、parallel consistency、CI。
7. **Reporting**：正文图表、附录、LaTeX、source-data、metadata。
8. **Fast**：synthetic + deterministic real subset；双重 self-check。
9. **Full**：完整 cohort、1000 bootstrap、targeted/appendix、PASS/STOP。
10. **Promotion**：独立验证、paper bundle、release manifest/tag。

---

# 21. 论文接口

最强允许结论：

> Holding the eligible journeys and decision-cell support fixed, alternative attribution routes induce different source-time credit allocations and may prioritize different high-ranked campaign-day cells.

若 source routes 差异较小，应相应减弱：

> The arrival-side accounting route differs from source-time routes, while disagreement among source-time attribution rules is limited on the retained cohort.

禁止写 route causally correct、improves policy value、reduces causal regret、increases conversions、should be deployed 或 logged reference validates a route。

---

# 22. 冻结项

```text
experiment_directory = exp2_delayed_conversion_attribution
task = logged attribution sensitivity only

timezone = UTC
decision_cell = campaign_id × source_date_utc
primary_candidate_window_days = 30
targeted_candidate_window_days = 7
campaign_scope = all route-independent support-eligible campaigns
minimum_impressions_per_cell = 50
support_sensitivity = [25, 100]

complete_lookback = required
unique_uid = required
unique_candidate_campaign = required
modal_campaign_fallback = prohibited

primary_routes = [
  arrival_bin_anchor,
  first_touch,
  last_touch,
  linear_credit,
  time_decay_credit
]
em_route = appendix_only
logged_reference = audit_reference_only

time_decay_rate_per_day = 0.5
time_decay_cell_timestamp = latest_event_in_cell

allocation_metric = aggregate decision-cell allocation TV
journey_metric = mean journey assignment TV
ranking_score = credited conversion mass / eligible impressions

primary_top_k = 10
targeted_top_k = [20, 50]
kendall_variant = tau_b
kendall_support = union positive-credit cells

bootstrap_unit = user_id
bootstrap_repetitions_fast = 200
bootstrap_repetitions_full = 1000
bootstrap_interval = percentile
confidence_level = 0.95

main_figure_panels = 2
main_panel_a = arrival-anchor allocation displacement
main_panel_b = pairwise allocation-TV dot-and-whisker
pairwise_matrices = appendix
ambiguity_strata = appendix
delay_composition = appendix

plotting_recomputes_estimands = false
fast_paper_result = false
full_paper_result = false until promotion
```

---

# 23. 最终实施原则

Exp2 的完成标准不是结果差异必须大，而是：

1. cohort route-independent；
2. routes 只改变 credit assignment；
3. allocation 与 ranking estimands 准确区分；
4. UID uncertainty 正确；
5. 主图直观展示 attribution sensitivity；
6. 结果可重建和审计；
7. 结论严格限于 logged-data diagnostic。

不得通过增加 route、参数网格、政策 replay、经济指标或额外模型提高“实验丰富度”。
