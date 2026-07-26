# Experiment 4 编程与正文补写备忘录

## Controlled Route Alignment and Evidence-Qualified Audit

**版本：** Exp4 Programming Memo v1.0  
**冻结日期：** 2026-07-24  
**适用目录：** `exp4_controlled_route_audit`  
**替代旧目录：** `exp4_proxy_sufficiency_impossibility`  
**适用范围：** Experiment 4 的代码重构、fast/full 运行、科学验收、论文出图、表格生成、正文 Section 6.5 与 Appendix D.4 补写。  

---

# 0. 文档定位

本备忘录是 Experiment 4 后续实现的正式边界文件。

后续编程应以本文件为直接依据，不再以旧代码中的以下任务作为主设计：

```text
proxy_diagnostic
source_label_sweep
phase_grid
delay_coupling
```

旧代码和旧结果仅保留为历史版本、回归对照和迁移审计，不再具有新的 paper-eligible 资格。

本备忘录冻结以下总结构：

$$
\text{Module A: controlled route boundary}
\quad\longrightarrow\quad
\text{Module B: audit reliability}.
$$

其中：

1. Module A 提供已知 structural truth 下的 route-alignment population target；
2. Module B 检验有限且可能具有选择偏倚的 audit evidence 能否可靠估计该 target；
3. calibration controls 检验预先指定的 affine calibration family 能恢复什么、不能证明什么；
4. 实际 online learner consequence 只作为附录结果，不再承担 Exp4 正文主命题。

---

# 1. Exp4 在全文与四实验中的任务边界

## 1.1 四实验分工

| 实验 | 核心任务 | 主要证据层级 |
|---|---|---|
| Exp1 | action-gap alignment 是否决定 regret transfer；同一 learner 的 arrival/source update consequence | controlled validity mechanism |
| Exp2 | 相同 delayed-conversion journeys 在不同 attribution rules 下是否产生不同 allocation 与 ranking | logged attribution sensitivity |
| Exp3 | score recovery 是否传递为 action-gap recovery 与 ranking recovery | semi-synthetic proxy recoverability |
| Exp4 | 已知 structural truth 下 route alignment 的边界，以及有限 audit evidence 对该 alignment 的估计可靠性 | controlled evidence-qualified audit |

Exp4 不再重复 Exp1 的 matched-delay、delay-state coupling、systematic misbinding 或 learner regret 主实验。

Exp4 不再重复 Exp3 的 score prediction、proxy calibration 或 ranking performance 主实验。

## 1.2 Exp4 唯一主问题

Exp4 回答两个连续问题。

第一层：

> 当 source-label retention 和 attribution-proxy quality 改变时，operational route 与 structural action comparisons 的真实偏离如何变化？

第二层：

> 当只有有限、可能非代表性的 source-grounded audit evidence 时，raw defect、calibrated defect 和 recoverability 能否被可靠估计？

因此 Exp4 的正式名称冻结为：

> **Experiment 4: Controlled Route Alignment and Evidence-Qualified Audit**

代码目录和稳定 experiment ID 冻结为：

```text
directory_name = exp4_controlled_route_audit
experiment_id = exp4_controlled_route_audit
experiment_display_name = Controlled Route Alignment and Evidence-Qualified Audit
result_schema = exp4_controlled_route_audit_v1
```

不再使用：

```text
proxy_sufficiency_impossibility
recoverability_boundary
proxy-only impossibility
```

有限模拟不能支持 information-theoretic impossibility 结论。

---

# 2. 当前稿件与旧代码审计结论

## 2.1 当前稿件中的旧 Exp4

当前稿件 Section 6.5 和 Appendix D.4 主要报告：

1. proxy-state error 与 absolute loss-map distortion；
2. 固定 attribution-proxy noise 下的 source-label retention sweep；
3. 完整 $q\times\sigma$ causal-regret recovery heatmap；
4. delay-state coupling；
5. arrival-to-oracle recovery；
6. source-binding normalized recovery；
7. proxy-only route 相对 history surrogate 的 paired contrast。

这些内容与旧代码一致，但与新的 v3.1 定位不一致。

后续新的 full run 完成后，以下稿件内容全部需要替换：

```text
旧 Section 6.5 标题与正文
旧 Figure 6
旧 Appendix D.4
旧 Tables 15--17
旧 Figure 11
```

## 2.2 当前代码结构

旧代码目前包括：

```text
config.py
simulator.py
policies.py
engine.py
run_experiment4.py
aggregate_results.py
plot_results.py
make_tables.py
self_check.py
code_check.py
main.py
write_audit_report.py
write_output_manifest.py
```

可以保留这一紧凑工程风格，但需要重构科学职责。

## 2.3 当前代码的主要科学错位

### 结构损失和随机反馈混合

旧 `Trace.potential_losses` 同时承担：

- learner 的 realized feedback；
- regret benchmark；
- best action；
- route diagnostic。

新版必须拆分为：

```text
structural_loss_map
realized_potential_feedback
```

### 旧 route 是 learner 类，不是 full-map route

旧类：

```text
ArrivalTimeNaiveUCB
ObservableHistorySurrogate
ProxyLabelRecoveryUCB
SourceLabelledReferenceUCB
```

描述的是 scalar-feedback learner update，不是理论中的：

$$
\widetilde L_t^r(a).
$$

新版必须把 route-map construction 与 learner update 完全分离。

### 旧 distortion 不是 action-gap defect

旧指标：

```text
absolute_proxy_distortion_per_round
```

实质是：

$$
\frac1{TK}
\sum_{t,a}
\left|
L^c(a;S_t)-L^c(a;\widehat S_t)
\right|.
$$

理论 primary object 是：

$$
\delta_t^r
=
\max_{a<b}
\left|
G_t^r(a,b)-G_t^c(a,b)
\right|.
$$

旧指标只能改名为：

```text
absolute_loss_map_error_appendix
```

不得直接改名为 action-gap defect。

### 旧 label stream 只有一条

旧 `Trace.label_uniforms` 不能同时承担：

- route construction labels；
- audit evidence labels。

新版必须建立独立 random streams 和 masks。

### 旧 horizon 丢弃尾部 arrivals

旧 simulator 只构造长度为 $T$ 的 arrival clock。若：

$$
s+\tau_s\geq T,
$$

该 source outcome 不再进入 route processing。

新版必须延长 observation clock 到：

$$
T_{\mathrm{clock}}
=
T+d_{\max}.
$$

### 旧 full 自动 paper promotion

旧 `main.py` 在 full checks 通过后直接修改：

```text
paper_result=true
```

新版禁止这一行为。full run 和 paper promotion 必须完全分开。

### 旧输出层级重叠

旧目录同时存在：

```text
processed/
summaries/
```

职责重复。新版统一为：

```text
derived/
```

---

# 3. 总体科学层级

新版 Exp4 严格分为三个层级。

## 3.1 Layer A：Full-map route validity diagnostic

controlled simulator 保存完整 structural action-level map：

$$
L_t^c
=
\left(
L_t^c(1),\ldots,L_t^c(K)
\right).
$$

每个 route 构造：

$$
\widetilde L_t^r
=
\left(
\widetilde L_t^r(1),\ldots,\widetilde L_t^r(K)
\right).
$$

该层计算：

- structural action gaps；
- route action gaps；
- per-round action-gap defect；
- population raw defect；
- ranking reversal；
- margin preservation；
- secondary structural regret。

所有 full-map objects 必须标记：

```text
simulator_only_full_map = true
online_available = false
```

## 3.2 Layer B：Actual learner consequence

保留实际 scalar-feedback learner，只读取 admissible information。

该层回答：

> 在相同 structural path 和 realized feedback path 下，route information 对 online action consequences 有何影响？

该层进入附录，不用于定义 population action-gap defect。

## 3.3 Layer C：Evidence-qualified audit

固定 route 后，通过有限 audit evidence 估计：

$$
d_{\mathrm{pop,raw}}^r,
$$

$$
d_{\mathrm{pop,cal}}^r(\widehat m),
$$

以及：

$$
\operatorname{Rec}_{\mathrm{pop}}^r(\widehat m).
$$

该层是 Exp4 正文核心。

---

# 4. 命名规范

## 4.1 命名原则

稳定 machine ID、论文 display name 和 analysis role 必须分开。

每个 route 至少具有：

```text
route_id
route_display_name
information_interface
analysis_role
reference_role
is_deployable
uses_source_labels
uses_latent_information
uses_future_information
```

## 4.2 Module IDs

```text
route_boundary
audit_reliability
calibration_control
learner_consequence_appendix
```

不再使用旧 subexperiment IDs。

## 4.3 Route IDs

| `route_id` | 论文展示 | 角色 |
|---|---|---|
| `arrival_time` | Arrival time | arrival-clock route |
| `history_surrogate` | History surrogate | anonymous observable-history route |
| `proxy_label` | Proxy-label | partial source labels + proxy attribution |
| `source_bound` | Source-labelled | source-binding reference |
| `noisy_state_oracle` | Noisy-state oracle | appendix diagnostic |
| `latent_state_oracle` | Latent-state oracle | appendix diagnostic |

稳定 ID 不使用：

```text
naive
recovery
impossibility
final
new
v2
oracle_recovery
```

`recovery` 是结果量，不应默认写进 route 名称。

## 4.4 参数命名

| 数学符号 | 稳定代码字段 |
|---|---|
| $q_{\mathrm{route}}$ | `route_label_rate` |
| $\rho_{\mathrm{audit}}$ | `audit_evidence_rate` |
| $\sigma_{\mathrm{proxy}}$ | `attribution_proxy_noise_sd` |
| context noise | `context_proxy_noise_sd` |
| $T$ | `decision_horizon` |
| $W$ | `warmup_rounds` |
| $K$ | `num_actions` |
| $d_{\max}$ | `maximum_candidate_delay` |
| $h$ | `proxy_kernel_bandwidth` |
| $\lambda$ | `recency_decay_rate` |
| $M_{\mathrm{MC}}$ | `monte_carlo_replications` |
| $B$ | `bootstrap_replications` |

禁止将输出列命名为：

```text
q
sigma
beta
rate
noise
metric
value
oracle
truth
```

除非同时存在完整语义前缀。

## 4.5 Estimand 命名

Module A：

```text
structural_loss_map
realized_potential_feedback
route_loss_map
structural_action_gap
route_action_gap
round_action_gap_defect
population_raw_action_gap_defect
ranking_reversal_rate
margin_preservation_rate
structural_regret_per_round
absolute_loss_map_error_appendix
```

Module B：

```text
sample_raw_action_gap_defect
population_raw_action_gap_defect
sample_calibrated_action_gap_defect
population_calibrated_action_gap_defect_conditional_on_fitted_map
estimated_recoverability
population_recoverability_conditional_on_fitted_map
labelled_audit_sample_size
effective_labelled_sample_size
labelled_support_coefficient
pair_coverage_rate
calibration_estimable_rate
```

禁止使用：

```text
validity_score
audit_quality
support_score
true_recoverability
oracle_calibrated_defect
intrinsic_recoverability
```

## 4.6 类与函数

类使用 PascalCase：

```python
StructuralTrajectory
ArrivalTimeRoute
HistorySurrogateRoute
ProxyLabelRoute
SourceBoundRoute
AuditSampler
TemporalCrossFitter
CalibrationControl
```

函数使用动词开头：

```python
generate_structural_trajectory()
construct_route_loss_map()
compute_action_gap_defect()
sample_audit_evidence()
fit_cross_fitted_calibration()
evaluate_population_targets()
summarize_monte_carlo_results()
validate_paper_promotion()
```

布尔字段使用：

```text
is_paper_eligible
is_calibration_estimable
is_source_label_observed
has_complete_pair_support
uses_latent_information
uses_future_information
```

---

# 5. Structural process

## 5.1 固定 DGP

保留旧代码的：

- $K=10$ actions；
- state dimension $=3$；
- piecewise-stable latent states；
- action centers；
- state-dependent loss shape；
- delay-state coupling parameter的主值；
- target mean delay；
- maximum delay；
- shared path design。

不增加新的 DGP family。

Module A full：

$$
K=10,
\qquad
T=5000,
\qquad
W=250.
$$

Module B full：

$$
K=10,
\qquad
T_{\mathrm{audit}}=2000,
\qquad
W_{\mathrm{audit}}=100.
$$

## 5.2 Structural loss map

定义：

$$
L_t^c(a)
=
L^c(a;S_t).
$$

代码字段：

```text
structural_loss_map.shape = [decision_horizon, num_actions]
dtype = float64
```

该 map 用于：

- action gaps；
- best action；
- structural regret；
- population route defect；
- audit reference signal。

## 5.3 Realized potential feedback

定义：

$$
Y_t(a)
=
\operatorname{clip}
\left[
L_t^c(a)+\varepsilon_{t,a},
0,1
\right].
$$

代码字段：

```text
realized_potential_feedback.shape = [decision_horizon, num_actions]
dtype = float64
```

只用于实际 learner 的 factual feedback：

$$
Y_t(A_t).
$$

不得用于定义 population action-gap truth。

## 5.4 State transition

本实验 DGP 中 state transition 保持外生：

```text
state_transition_action_dependent = false
```

因此不同 routes 可以合法共享：

- latent state path；
- structural loss map；
- realized feedback noise；
- delay path；
- route-label uniforms；
- attribution-proxy standard noise。

该性质只属于 Exp4 controlled DGP，不写成全文结构假设。

## 5.5 Observation clock

定义：

$$
T_{\mathrm{clock}}
=
T+d_{\max}.
$$

structural rounds：

$$
t=0,\ldots,T-1.
$$

observation clocks：

$$
u=0,\ldots,T+d_{\max}-1.
$$

所有 source outcomes 都必须完成 arrival processing。

evaluation 仍只使用：

$$
t=W,\ldots,T-1.
$$

---

# 6. Random streams 与共享路径

## 6.1 禁止 magic offsets

旧代码中的：

```text
100003 + seed
200003 + seed
300003 + seed
400003 + seed
```

改为 `numpy.random.SeedSequence` 命名分流。

每个 seed 或 replication 至少包含：

```text
state_stream
structural_feedback_stream
delay_stream
context_proxy_stream
attribution_proxy_stream
route_label_stream
audit_mcar_stream
audit_biased_stream
calibration_noise_stream
shuffle_control_stream
learner_randomization_stream
bootstrap_stream
```

## 6.2 嵌套 parameter paths

不同 attribution-proxy noise 共用同一个标准噪声：

$$
P_t(\sigma)
=
S_t+\sigma Z_t.
$$

不同 route label rates 共用同一个 uniform stream：

$$
Z_t^{\mathrm{route}}(q)
=
\mathbf 1
\left\{
U_t^{\mathrm{route}}<q
\right\}.
$$

不同 audit evidence rates 共用对应 inclusion uniform stream，以形成 paired/nested comparisons。

## 6.3 Path manifest

每个 structural trajectory 生成：

```text
path_id
state_path_hash
structural_loss_map_hash
realized_feedback_hash
delay_path_hash
context_proxy_hash
attribution_proxy_base_noise_hash
route_label_uniform_hash
```

Module A 同一 seed 的所有 cells 必须共享相同 `path_id`。

---

# 7. Module A：Controlled Route Boundary

## 7.1 任务

Module A 提供：

$$
q_{\mathrm{route}}
\times
\sigma_{\mathrm{proxy}}
\mapsto
d_{\mathrm{pop,raw}}^{\mathrm{proxy\_label}}.
$$

它不是 learner leaderboard，也不是 proxy algorithm benchmark。

## 7.2 Primary grid

冻结：

$$
q_{\mathrm{route}}
\in
\{0,0.3,0.7,1\},
$$

$$
\sigma_{\mathrm{proxy}}
\in
\{0.10,0.25,1.00\}.
$$

共：

$$
4\times3=12
$$

个 primary cells。

30 shared seeds。

主 delay-state coupling 固定为旧 DGP 的主值：

```text
delay_state_coupling = 2.0
```

不再运行 delay-coupling sweep。

## 7.3 四类 route maps

所有 route 输出：

```text
route_loss_map.shape = [T, K]
dtype = float64
```

---

## 7.4 Source-bound route

定义：

$$
\widetilde L_t^{\mathrm{source}}
=
L_t^c.
$$

因此：

$$
d_{\mathrm{pop,raw}}^{\mathrm{source}}=0.
$$

代码：

```text
route_id = source_bound
route_display_name = Source-labelled
reference_role = source_binding_reference
is_deployable = false
simulator_only_full_map = true
```

这里的 `is_deployable=false` 表示完整 counterfactual map 不是在线可观测对象，不表示 source-labelled scalar learner 不可实现。

---

## 7.5 Arrival-time route

令：

$$
\mathcal B_u
=
\{s:s+\tau_s=u\}.
$$

若：

$$
\mathcal B_u\neq\varnothing,
$$

定义：

$$
\widetilde L_u^{\mathrm{arrival}}
=
\frac1{|\mathcal B_u|}
\sum_{s\in\mathcal B_u}L_s^c.
$$

即 equal-weight aggregation。

若当前 clock 无 arrival：

$$
\widetilde L_u^{\mathrm{arrival}}
=
\widetilde L_{u-1}^{\mathrm{arrival}}.
$$

初值：

$$
\widetilde L_0^{\mathrm{arrival}}
=
0.5\mathbf 1_K.
$$

不得：

- 删除 no-arrival rounds；
- 使用 structural map 填充；
- 使用 history route 填充；
- 每个空 round 重置为零。

---

## 7.6 History-surrogate route

固定：

```text
context_proxy_noise_sd = 0.25
history_ema_rate = 0.08
```

根据 observable context proxy 映射 coarse context：

$$
C_t
=
\arg\min_c
\|P_t-\mu_c\|^2.
$$

为每个 context 维护：

$$
H_{c,t}\in\mathbb R^K.
$$

arrival batch map：

$$
\overline L_u^{\mathrm{batch}}
=
\frac1{|\mathcal B_u|}
\sum_{s\in\mathcal B_u}L_s^c.
$$

若有 arrival：

$$
H_{C_u,u}
=
(1-\alpha)H_{C_u,u-1}
+
\alpha\overline L_u^{\mathrm{batch}},
$$

其中：

$$
\alpha=0.08.
$$

其他 contexts 保持不变。

route map：

$$
\widetilde L_u^{\mathrm{history}}
=
H_{C_u,u}.
$$

所有 contexts 初始化为：

$$
0.5\mathbf 1_K.
$$

该 full-map route 仅用于 simulator diagnostic；对应实际 learner 仍只使用 factual scalar arrivals。

---

## 7.7 Proxy-label route

固定参数：

```text
maximum_candidate_delay = 20
proxy_kernel_bandwidth = 0.55
recency_decay_rate = 0.035
```

source event $s$ 在：

$$
u_s=s+\tau_s
$$

到达。

### 有 route label

若：

$$
Z_s^{\mathrm{route}}=1,
$$

则：

$$
w_{s\rightarrow t}
=
\mathbf 1\{t=s\}.
$$

### 无 route label

候选 source rounds：

$$
\mathcal C(u_s)
=
\left\{
t:
\max(0,u_s-d_{\max})
\leq t<u_s,
\quad t<T
\right\}.
$$

weights：

$$
w_{u_s,t}
\propto
\exp
\left[
-\frac{
\|P_t-P_{u_s}\|^2
}{
2h^2
}
-\lambda(u_s-t)
\right].
$$

归一化：

$$
\sum_{t\in\mathcal C(u_s)}
w_{u_s,t}
=
1.
$$

### Route map

定义归因质量：

$$
m_t
=
\sum_s
w_{s\rightarrow t}.
$$

route map：

$$
\widetilde L_t^{\mathrm{proxy}}
=
\frac{
\sum_s
w_{s\rightarrow t}L_s^c
}{
m_t
}.
$$

由于 observation clock 延长且 true source 位于候选窗口内，理论上所有 structural rounds 应满足：

$$
m_t>0.
$$

若任一 post-warmup round 出现：

$$
m_t=0,
$$

必须 hard fail，不得 fallback 到 History route。

### Full-label invariant

当：

$$
q_{\mathrm{route}}=1,
$$

必须有：

$$
\widetilde L_t^{\mathrm{proxy}}
=
L_t^c
$$

对所有 $t$ 成立。

---

# 8. Module A estimands

## 8.1 Action gaps

对固定 orientation：

$$
1\leq a<b\leq K,
$$

定义：

$$
G_t^c(a,b)
=
L_t^c(a)-L_t^c(b),
$$

$$
G_t^r(a,b)
=
\widetilde L_t^r(a)-\widetilde L_t^r(b).
$$

当 $K=10$：

$$
|\mathcal P|
=
\binom{10}{2}
=
45.
$$

pair orientation 字段固定为：

```text
action_pair_low
action_pair_high
```

## 8.2 Unit defect

$$
\delta_t^r
=
\max_{a<b}
\left|
G_t^r(a,b)-G_t^c(a,b)
\right|.
$$

## 8.3 Population raw defect

$$
d_{\mathrm{pop,raw}}^r
=
\frac1{T-W}
\sum_{t=W}^{T-1}
\delta_t^r.
$$

这是 Module A 正文 primary metric。

## 8.4 Ranking reversal

令：

$$
\mathcal A_t^{r,\star}
=
\arg\min_a\widetilde L_t^r(a),
$$

$$
\mathcal A_t^{c,\star}
=
\arg\min_aL_t^c(a).
$$

定义：

$$
\operatorname{RevRate}^r
=
\frac1{T-W}
\sum_{t=W}^{T-1}
\mathbf 1
\left\{
\mathcal A_t^{r,\star}
\not\subseteq
\mathcal A_t^{c,\star}
\right\}.
$$

## 8.5 Margin preservation

structural margin：

$$
\gamma_t
=
\min_{a\notin\mathcal A_t^{c,\star}}
\left[
L_t^c(a)-\min_bL_t^c(b)
\right].
$$

定义：

$$
\operatorname{MarginPreserve}^r
=
\frac1{T-W}
\sum_{t=W}^{T-1}
\mathbf 1
\left\{
\delta_t^r<\gamma_t
\right\}.
$$

## 8.6 Structural regret

实际 learner secondary metric：

$$
R_{\mathrm{post}}^c
=
\frac1{T-W}
\sum_{t=W}^{T-1}
\left[
L_t^c(A_t)-\min_aL_t^c(a)
\right].
$$

该量只进入附录 learner consequence。

## 8.7 旧 absolute loss metric

旧指标只保留为：

```text
absolute_loss_map_error_appendix
```

定义：

$$
\frac1{(T-W)K}
\sum_{t=W}^{T-1}
\sum_a
\left|
\widetilde L_t^r(a)-L_t^c(a)
\right|.
$$

不得进入正文主图。

---

# 9. Actual learner consequence

## 9.1 定位

保留 actual learner 是为了说明 route alignment 可能对应 online action consequences，但不能用其内部统计量定义 full-map route validity。

## 9.2 Learner family

可以保留当前 contextual UCB family，但应规范类名：

```python
ArrivalTimeUCB
HistorySurrogateUCB
ProxyLabelUCB
SourceBoundUCB
```

移除稳定类名中的：

```text
Naive
Recovery
Reference
```

role 通过 metadata 表示。

## 9.3 Information boundary

actual learner 不得读取：

```text
structural_loss_map
full_realized_potential_feedback
structural_best_action
structural_action_gaps
hidden_source_id_for_unlabelled_arrival
future_proxy_values
future_arrivals
```

允许读取：

- current observable context；
- past actions；
- arrivals processed after current action；
- factual scalar loss；
- retained source IDs；
- historical proxy values；
- fixed candidate attribution rule。

## 9.4 正文与附录边界

正文不展示 actual learner causal-regret sweep。

附录可以展示：

1. alignment–regret scatter；
2. fixed $\sigma=0.25$ 的 source-label sweep；
3. four-route learner comparison；
4. source-bound and full-label invariants。

---

# 10. Module B：Audit Reliability

## 10.1 任务

Module B 检验：

$$
\widehat d_{\mathrm{raw}}^r
\leftrightarrow
d_{\mathrm{pop,raw}}^r,
$$

$$
\widehat d_{\mathrm{cal}}^r
\leftrightarrow
d_{\mathrm{pop,cal}}^r(\widehat m),
$$

$$
\widehat{\operatorname{Rec}}^r
\leftrightarrow
\operatorname{Rec}_{\mathrm{pop}}^r(\widehat m).
$$

## 10.2 Full configuration

$$
T_{\mathrm{audit}}=2000,
$$

$$
W_{\mathrm{audit}}=100,
$$

$$
M=1900,
$$

$$
M_{\mathrm{MC}}=200.
$$

每个 replication 同时构造四个 route maps：

```text
arrival_time
history_surrogate
proxy_label
source_bound
```

## 10.3 Primary audit route

正文 primary route 固定为：

```text
primary_audit_route = proxy_label
route_label_rate = 0.30
attribution_proxy_noise_sd = 0.25
```

原因是该 route 同时具有：

- 部分 factual source binding；
- 部分 proxy attribution；
- 非零 population defect；
- 独立的 audit evidence problem。

其他 routes 进入附录完整审计表。

## 10.4 Audit unit

audit unit 固定为一个 post-warmup structural round：

$$
i=t,
\qquad
t=100,\ldots,1999.
$$

## 10.5 Pair support

主 pair set：

$$
\mathcal P
=
\{(a,b):1\leq a<b\leq10\}.
$$

controlled design 中：

$$
\operatorname{PairCoverage}=1.
$$

否则 hard fail。

---

# 11. Route labels 与 audit labels

## 11.1 独立 random streams

必须生成：

```text
route_label_uniforms
audit_uniforms_mcar
audit_uniforms_biased
```

route construction label：

$$
Z_i^{\mathrm{route}}
=
\mathbf 1
\left\{
U_i^{\mathrm{route}}
<
q_{\mathrm{route}}
\right\}.
$$

audit evidence inclusion 由独立 random stream 产生。

## 11.2 独立性检查

至少检查：

1. random stream IDs 不同；
2. seed spawn keys 不同；
3. hashes 不同；
4. Monte Carlo empirical correlation 接近零。

empirical correlation 只作为实现检查，不作为统计独立性的唯一证明。

---

# 12. Observable ambiguity score

## 12.1 构造原则

ambiguity-biased audit sampling 不能使用：

- latent state；
- $\phi_i$；
- structural defect；
- $|q_i-\phi_i|$；
- future outcome；
- route label mask。

否则 audit inclusion 会使用 structural truth。

## 12.2 Label-blind attribution base

在计算 ambiguity 时，将所有 arrivals 暂时视为 anonymous，使用相同 proxy kernel 和 recency prior 构造：

```text
base_anonymous_assignment
```

该对象不读取 route-label mask。

## 12.3 主 ambiguity score

对 audit unit $i$，令所有 incoming attribution weights 归一化为：

$$
p_{j,i}
=
\frac{
w_{j\rightarrow i}
}{
\sum_{j'}w_{j'\rightarrow i}
}.
$$

contributor count：

$$
c_i
=
\#\{j:w_{j\rightarrow i}>0\}.
$$

normalized assignment entropy：

$$
h_i
=
\begin{cases}
-\dfrac{
\sum_jp_{j,i}\log p_{j,i}
}{
\log c_i
},
&
c_i>1,
\\[1.2ex]
0,
&
c_i=1.
\end{cases}
$$

因此：

$$
h_i\in[0,1].
$$

附录 diagnostics：

```text
candidate_contributor_count
maximum_assignment_mass
arrival_congestion
```

不额外构造 composite ambiguity score。

---

# 13. Audit evidence rates 与 inclusion mechanisms

## 13.1 Audit rates

冻结：

$$
\rho_{\mathrm{audit}}
\in
\{0.1,0.3,0.5,1.0\}.
$$

所有输出同时保存：

```text
route_label_rate
audit_evidence_rate
```

## 13.2 MCAR

$$
\pi_i
=
\rho_{\mathrm{audit}}.
$$

$$
Z_i^{\mathrm{audit}}
=
\mathbf 1
\left\{
U_i^{\mathrm{MCAR}}<\rho_{\mathrm{audit}}
\right\}.
$$

主 estimator：

```text
inclusion_mechanism = mcar
weighting_method = unweighted
```

## 13.3 Ambiguity-biased sampling

标准化：

$$
z_i
=
\frac{h_i-\bar h}{s_h}.
$$

定义：

$$
\pi_i
=
\operatorname{clip}
\left[
\operatorname{logit}^{-1}
\left(
c_\rho+1.5z_i
\right),
0.05,
0.95
\right].
$$

用 bisection 求解 $c_\rho$，满足：

$$
\frac1M\sum_i\pi_i
=
\rho_{\mathrm{audit}}.
$$

数值容差：

$$
\left|
M^{-1}\sum_i\pi_i-\rho_{\mathrm{audit}}
\right|
<
10^{-8}.
$$

biased mask：

$$
Z_i^{\mathrm{audit}}
=
\mathbf 1
\left\{
U_i^{\mathrm{biased}}<\pi_i
\right\}.
$$

正文估计器：

1. biased unweighted；
2. biased IPW。

IPW：

$$
v_i
=
\frac1{\pi_i}.
$$

不增加：

- propensity estimation；
- weight trimming；
- stabilized weights；
- doubly robust estimator。

当：

$$
\rho_{\mathrm{audit}}=1,
$$

直接使用完整 population，只保留一个 full-population condition。

---

# 14. Audit signals 与 raw estimator

## 14.1 Route-side signal

$$
q_i^{r,a,b}
=
G_i^r(a,b).
$$

## 14.2 Source-grounded signal

$$
\phi_i^{a,b}
=
G_i^c(a,b).
$$

controlled simulator 直接提供 structural comparison truth。

## 14.3 Unit raw defect

$$
\widehat\delta_{i,\mathrm{raw}}^r
=
\max_{a<b}
\left|
q_i^{r,a,b}-\phi_i^{a,b}
\right|.
$$

## 14.4 Sample raw estimator

$$
\widehat d_{\mathrm{raw}}^r
=
\frac{
\sum_{i:Z_i^{\mathrm{audit}}=1}
v_i\widehat\delta_{i,\mathrm{raw}}^r
}{
\sum_{i:Z_i^{\mathrm{audit}}=1}
v_i
}.
$$

## 14.5 Population raw target

$$
d_{\mathrm{pop,raw}}^r
=
\frac1M
\sum_{i\in\mathcal I}
\widehat\delta_{i,\mathrm{raw}}^r.
$$

---

# 15. Cross-fitting 与 affine calibration

## 15.1 Temporal folds

固定 5 个 contiguous folds：

```python
temporal_folds = np.array_split(audit_rounds, 5)
```

folds：

- 连续；
- 互斥；
- 完整覆盖 audit population；
- 不随机打乱时间。

## 15.2 Pair-specific calibration

对每个 pair 单独拟合：

$$
\phi_i^{a,b}
=
\alpha_{a,b}^{(-k)}
+
\beta_{a,b}^{(-k)}
q_i^{r,a,b}
+
e_i.
$$

保留 intercept。

不使用：

- feature standardization；
- ridge penalty；
- slope clipping；
- monotonicity constraint；
- robust regression；
- nonlinear model selection。

## 15.3 Estimator-specific fitting

| Condition | Calibration fit | Defect aggregation |
|---|---|---|
| MCAR unweighted | OLS | unweighted |
| Biased unweighted | OLS | unweighted |
| Biased IPW | WLS，weight $1/\pi_i$ | IPW |

## 15.4 Minimum support

每个 training split 至少：

```text
minimum_labelled_units_per_training_split = 30
```

controlled pair support 完整，因此该值对所有 45 pairs 相同。

不足时：

```text
is_calibration_estimable = false
calibration_status = not_estimable
sample_calibrated_action_gap_defect = NA
estimated_recoverability = NA
```

禁止退化为 full-sample fit。

## 15.5 Pair coherence 边界

pair-specific calibrated gaps 不要求满足：

$$
\widehat G(a,b)+\widehat G(b,c)
=
\widehat G(a,c).
$$

该 calibration 只是 comparison audit diagnostic，不是 deployable corrected loss map。

禁止：

- 从 calibrated pair signals 重建 policy；
- 在 calibrated signals 上求 argmin；
- 计算 calibrated policy regret；
- 将 calibration 解释为 benchmark correction。

---

# 16. Calibrated targets 与 recoverability

## 16.1 Out-of-fold calibrated signal

$$
\widehat G_{i,\mathrm{cal}}^{r,(-k(i))}(a,b)
=
\widehat\alpha_{a,b}^{(-k(i))}
+
\widehat\beta_{a,b}^{(-k(i))}
q_i^{r,a,b}.
$$

## 16.2 Sample calibrated defect

$$
\widehat d_{\mathrm{cal}}^r
=
\frac{
\sum_{i:Z_i^{\mathrm{audit}}=1}
v_i
\max_{a<b}
\left|
\widehat G_{i,\mathrm{cal}}^{r,(-k(i))}(a,b)
-\phi_i^{a,b}
\right|
}{
\sum_{i:Z_i^{\mathrm{audit}}=1}v_i
}.
$$

## 16.3 Conditional population calibrated target

将本次 audit sample 拟合出的 fold-specific map 应用于对应完整 held-out population fold：

$$
d_{\mathrm{pop,cal}}^r(\widehat m)
=
\frac1M
\sum_{i\in\mathcal I}
\max_{a<b}
\left|
\widehat m_{a,b}^{(-k(i))}
\left(
q_i^{r,a,b}
\right)
-
\phi_i^{a,b}
\right|.
$$

字段必须完整命名：

```text
population_calibrated_action_gap_defect_conditional_on_fitted_map
```

## 16.4 Recoverability

当：

$$
d_{\mathrm{raw}}>10^{-12},
$$

定义：

$$
\widehat{\operatorname{Rec}}
=
1-
\frac{
\widehat d_{\mathrm{cal}}
}{
\widehat d_{\mathrm{raw}}
}.
$$

population conditional target：

$$
\operatorname{Rec}_{\mathrm{pop}}(\widehat m)
=
1-
\frac{
d_{\mathrm{pop,cal}}(\widehat m)
}{
d_{\mathrm{pop,raw}}
}.
$$

若 raw defect 为零：

```text
estimated_recoverability = NA
recoverability_reason = raw_defect_zero
```

不得赋值为 0 或 1。

---

# 17. Evidence support

对每个 replication、route、audit rate 和 audit design 计算：

$$
n_{\mathrm{lab}}
=
\sum_iZ_i^{\mathrm{audit}},
$$

$$
n_{\mathrm{eff}}
=
\frac{
\left(
\sum_i v_i
\right)^2
}{
\sum_i v_i^2
},
$$

$$
\omega_M
=
\frac{
\log(1+n_{\mathrm{eff}})
}{
\log(1+M)
}.
$$

代码字段：

```text
labelled_audit_sample_size
effective_labelled_sample_size
labelled_support_coefficient
```

解释冻结为：

- $n_{\mathrm{lab}}$：实际观察的 audit units；
- $n_{\mathrm{eff}}$：考虑 weight concentration 后的 effective support；
- $\omega_M$：相对目标 population 的 labelled support coefficient。

它们均不是：

- validity probability；
- confidence level；
- identification strength；
- statistical power；
- route quality score。

---

# 18. Calibration controls

## 18.1 Affine positive control

在 pair-signal 层构造：

$$
\phi_i^{a,b}
=
0.2
+
1.5q_i^{a,b}
+
\varepsilon_i^{a,b},
$$

$$
\varepsilon_i^{a,b}
\sim
N
\left(
0,0.1^2s_\phi^2
\right).
$$

$s_\phi$ 使用独立 calibration-generation sample 冻结。

该 control 检验 affine pipeline 在正确函数族下的表现。

## 18.2 Shuffled negative control

在每个 temporal fold 和每个 action pair 内打乱 unit correspondence。

保留：

- pair-specific marginals；
- fold-level粗时间结构；
- sample size；
- support pattern。

破坏：

- unit-level $q$ 与 $\phi$ correspondence。

不设置 recoverability 必须等于 0 的 hard gate。

## 18.3 Nonlinear monotone control

仅附录：

$$
\phi_i^{a,b}
=
\tanh
\left(
c q_i^{a,b}
\right)
+
\varepsilon_i^{a,b}.
$$

不增加 nonlinear calibration model。

其任务只是说明 affine-family-specific limitation。

---

# 19. Monte Carlo 汇总

## 19.1 Raw defect

$$
\operatorname{Bias}
(
\widehat d_{\mathrm{raw}}
)
=
\frac1{M_{\mathrm{MC}}}
\sum_m
\left[
\widehat d_{\mathrm{raw},m}
-
d_{\mathrm{pop,raw},m}
\right].
$$

$$
\operatorname{RMSE}
(
\widehat d_{\mathrm{raw}}
)
=
\sqrt{
\frac1{M_{\mathrm{MC}}}
\sum_m
\left[
\widehat d_{\mathrm{raw},m}
-
d_{\mathrm{pop,raw},m}
\right]^2
}.
$$

## 19.2 Calibrated defect

以相同方法计算：

$$
\operatorname{Bias}
(
\widehat d_{\mathrm{cal}}
),
$$

$$
\operatorname{RMSE}
(
\widehat d_{\mathrm{cal}}
).
$$

每个 replication 的对照是该 replication 自己的 conditional population calibrated target。

## 19.3 Recoverability

$$
\operatorname{MAE}_{\mathrm{Rec}}
=
\frac1{M_{\mathrm{MC}}}
\sum_m
\left|
\widehat{\operatorname{Rec}}_m
-
\operatorname{Rec}_{\mathrm{pop},m}(\widehat m_m)
\right|.
$$

同时报告：

```text
negative_recoverability_rate
calibration_estimable_rate
mean_labelled_audit_sample_size
mean_effective_labelled_sample_size
mean_labelled_support_coefficient
```

## 19.4 不做正式 coverage study

当前 $M_{\mathrm{MC}}=200$ 不承担 nominal interval coverage 主研究。

不输出：

- formal coverage table；
- p-values；
- significance stars。

如未来增加 coverage study，必须单独 change memo，并至少使用 500 replications。

---

# 20. Fast / Full / Paper Promotion

## 20.1 Fast

Module A fast：

```text
decision_horizon = 1000
warmup_rounds = 100
seeds = 3
primary grid = complete 12 cells
```

Module B fast：

```text
decision_horizon = 1000
warmup_rounds = 100
monte_carlo_replications = 5
audit evidence grid = complete
calibration controls = complete
```

fast 用途：

- smoke test；
- schema validation；
- invariant test；
- figure/table pipeline；
- cross-fit estimability path；
- no-silent-fallback test。

必须写入：

```text
run_tier = fast
paper_result = false
is_paper_eligible = false
```

## 20.2 Full

Module A full：

```text
decision_horizon = 5000
warmup_rounds = 250
shared_seeds = 30
```

Module B full：

```text
decision_horizon = 2000
warmup_rounds = 100
monte_carlo_replications = 200
```

full 完成后仍写：

```text
run_tier = full
paper_result = false
is_paper_eligible = false
```

## 20.3 Paper promotion

独立命令：

```powershell
python promote_results.py --run-dir outputs/runs/<full_run_id>
```

只有 promotion script 可以修改：

```text
paper_result = true
run_tier = paper
is_paper_eligible = true
```

plotting、aggregation 和 `main.py` 均不得自动 promotion。

---

# 21. 不确定性

## 21.1 Module A

30 shared seeds。

使用：

```text
interval_method = paired_seed_percentile_bootstrap
resampling_unit = seed
bootstrap_replications = 2000
confidence_level = 0.95
```

## 21.2 Module B

200 independent Monte Carlo replications。

Bias、RMSE、MAE 等汇总使用：

```text
interval_method = monte_carlo_replication_bootstrap
resampling_unit = replication
bootstrap_replications = 2000
confidence_level = 0.95
```

不在每个 Monte Carlo replication 内再嵌套 bootstrap。

## 21.3 Metadata

每个 figure/table metadata 至少记录：

```text
interval_method
resampling_unit
bootstrap_replications
confidence_level
```

---

# 22. 代码结构与职责

保持单层紧凑结构：

```text
exp4_controlled_route_audit/
├─ config.py
├─ simulator.py
├─ route_maps.py
├─ policies.py
├─ audit_engine.py
├─ engine.py
├─ run_experiment4.py
├─ aggregate_results.py
├─ plot_results.py
├─ make_tables.py
├─ self_check.py
├─ code_check.py
├─ promote_results.py
├─ main.py
├─ reproduce_all.py
├─ write_audit_report.py
├─ write_output_manifest.py
├─ clean.py
├─ README.md
└─ requirements.txt
```

## 22.1 `config.py`

只包含：

- frozen parameters；
- mode settings；
- route registry；
- module registry；
- output display registry；
- figure/table registry；
- tolerances。

禁止包含 estimand calculation。

## 22.2 `simulator.py`

只负责：

- structural trajectory；
- structural loss map；
- realized potential feedback；
- delay path；
- arrival index；
- observable proxy banks；
- random stream manifest；
- path hashes。

核心 dataclass：

```python
@dataclass(frozen=True)
class StructuralTrajectory:
    seed: int
    decision_horizon: int
    observation_horizon: int
    latent_states: np.ndarray
    action_centers: np.ndarray
    structural_loss_map: np.ndarray
    realized_potential_feedback: np.ndarray
    delays: np.ndarray
    arrivals_by_clock: tuple[tuple[int, ...], ...]
    route_label_uniforms: np.ndarray
    audit_uniforms_mcar: np.ndarray
    audit_uniforms_biased: np.ndarray
    context_proxy: np.ndarray
    attribution_proxy_base_noise: np.ndarray
    path_id: str
```

## 22.3 `route_maps.py`

只负责：

- `ArrivalTimeRoute`；
- `HistorySurrogateRoute`；
- `ProxyLabelRoute`；
- `SourceBoundRoute`；
- route map construction；
- ambiguity construction；
- route-map invariants；
- route-map hashes。

不得包含 learner action selection。

## 22.4 `policies.py`

只负责 actual scalar-feedback learners。

不得构造 full route maps。

## 22.5 `audit_engine.py`

只负责：

- audit evidence masks；
- MCAR / biased inclusion；
- IPW；
- contiguous folds；
- OLS / WLS cross-fitting；
- raw/calibrated estimators；
- conditional population targets；
- support quantities；
- calibration controls。

## 22.6 `engine.py`

提供两类单任务执行：

```python
run_route_boundary_task()
run_audit_replication()
```

以及 optional：

```python
run_learner_consequence_task()
run_calibration_control_task()
```

不再通过旧 `kind` 运行四种旧 subexperiments。

## 22.7 `aggregate_results.py`

只读取 raw/derived outputs，计算：

- seed summaries；
- Monte Carlo summaries；
- bootstrap intervals；
- condition contrasts；
- support summaries。

不得重新生成 structural paths 或 route maps。

## 22.8 `plot_results.py`

只读取冻结 figure-data files。

不得：

- 重新拟合 calibration；
- 重新计算 defects；
- 重新 bootstrap；
- 根据结果重排 routes；
- silent drop NA。

## 22.9 `promote_results.py`

只负责独立 paper gate。

## 22.10 `clean.py`

只能独立调用。

不得由 `main.py` 自动调用。

功能：

- 显示将删除的 run directories；
- 要求显式确认；
- 仅清理 Exp4 outputs；
- 不删除 source code、README 或 legacy git tag。

---

# 23. 执行流程

## 23.1 主命令

```powershell
python main.py fast
python main.py full
python promote_results.py --run-dir outputs/runs/<full_run_id>
```

可选：

```powershell
python main.py fast --n-jobs 8
python main.py full --n-jobs 32
```

## 23.2 阶段顺序

```text
[1/10] Validate configuration and estimand registry
[2/10] Audit legacy trajectory reuse
[3/10] Generate shared structural trajectories
[4/10] Construct Module A route maps
[5/10] Compute route-boundary estimands
[6/10] Run Module B Monte Carlo audit
[7/10] Run calibration controls
[8/10] Aggregate derived results
[9/10] Generate figures, tables, and report
[10/10] Run engineering and scientific checks
```

## 23.3 终端摘要

运行结束必须区分：

```text
Engineering status : PASS / FAIL
Scientific status  : PASS / STOP_AND_REVIEW / FAIL
Paper promotion    : NOT RUN / PASS / FAIL
Paper result       : false / true
```

不得只输出：

```text
PIPELINE=PASSED
```

---

# 24. Run matrix

## 24.1 Module A

Primary：

$$
12\text{ cells}
\times
30\text{ seeds}
=
360
$$

个 Proxy-label route-map evaluations。

同一 seed 的：

- structural trajectory；
- arrival route；
- history route；
- source-bound route；

只构造一次并复用。

## 24.2 Module B

每个 replication：

- 1 structural trajectory；
- 4 route maps；
- 4 audit evidence rates；
- MCAR unweighted；
- biased unweighted；
- biased IPW；
- 5-fold pair-specific calibration。

当 $\rho=1$ 时只保留一个 full-population condition。

共 200 replications。

## 24.3 Controls

Affine positive 和 shuffled negative 使用同一 audit infrastructure，但必须具有独立：

```text
control_id
calibration_noise_stream
shuffle_stream
```

Nonlinear monotone 只进入 appendix。

---

# 25. Output directory

```text
outputs/
└─ runs/
   └─ <run_id>/
      ├─ raw/
      │  ├─ trajectories/
      │  └─ route_maps/
      ├─ derived/
      ├─ figures/
      │  ├─ pdf/
      │  ├─ png/
      │  ├─ data/
      │  └─ metadata/
      ├─ tables/
      ├─ checks/
      ├─ reports/
      └─ logs/
```

不再建立：

```text
processed/
summaries/
legacy/
```

legacy 通过 git tag 和旧 run manifest 管理，不在每个新 run 内复制。

---

# 26. Output contracts

所有 derived files 包含：

```text
run_id
run_tier
paper_result
analysis_tier
experiment_id
module_id
configuration_id
seed_or_replication
code_commit
config_hash
input_manifest_hash
result_schema
```

## 26.1 Trajectory reuse audit

```text
exp4_trajectory_reuse_audit.json
```

字段：

```text
state_transition_action_dependent
structural_loss_map_saved
realized_feedback_saved
delay_path_policy_independent
route_action_path_saved
route_label_mask_saved
audit_label_mask_saved
proxy_features_saved
path_hash_consistent
reuse_status
```

旧 run 预计：

```text
reuse_status = REQUIRES_RERUN
```

原因是旧 outputs 未保存新 estimand 所需的完整 structural maps、route maps 和独立 masks。

## 26.2 Module A

```text
exp4_route_boundary_seed_level.parquet
exp4_route_boundary_summary.csv
exp4_route_boundary_pairwise_metrics.parquet
exp4_learner_consequence_appendix.csv
```

`exp4_route_boundary_seed_level.parquet` 至少包含：

```text
seed
route_id
route_label_rate
attribution_proxy_noise_sd
population_raw_action_gap_defect
ranking_reversal_rate
margin_preservation_rate
structural_regret_per_round
absolute_loss_map_error_appendix
route_map_hash
structural_map_hash
path_id
analysis_tier
```

## 26.3 Module B audit units

```text
exp4_audit_unit_level.parquet
```

至少包含：

```text
replication_id
audit_round
route_id
raw_unit_action_gap_defect
base_ambiguity_score
candidate_contributor_count
maximum_assignment_mass
is_source_label_observed
audit_uniform_mcar
audit_uniform_biased
structural_map_hash
route_map_hash
```

## 26.4 Raw estimates

```text
exp4_raw_estimates.csv
```

字段：

```text
replication_id
route_id
route_label_rate
audit_evidence_rate
inclusion_mechanism
weighting_method
sample_raw_action_gap_defect
population_raw_action_gap_defect
raw_estimation_error
labelled_audit_sample_size
effective_labelled_sample_size
labelled_support_coefficient
pair_coverage_rate
```

## 26.5 Calibrated estimates

```text
exp4_calibrated_estimates.csv
```

字段：

```text
replication_id
route_id
route_label_rate
audit_evidence_rate
inclusion_mechanism
weighting_method
sample_calibrated_action_gap_defect
population_calibrated_action_gap_defect_conditional_on_fitted_map
estimated_recoverability
population_recoverability_conditional_on_fitted_map
recoverability_error
is_calibration_estimable
calibration_status
minimum_pair_training_support
```

## 26.6 Calibration parameters

```text
exp4_calibration_fold_parameters.parquet
```

字段：

```text
replication_id
route_id
audit_evidence_rate
inclusion_mechanism
weighting_method
fold_id
action_pair_low
action_pair_high
calibration_intercept
calibration_slope
training_labelled_units
training_weight_sum
```

## 26.7 Summaries

```text
exp4_route_boundary_summary.csv
exp4_audit_condition_summary.csv
exp4_effective_support_summary.csv
exp4_calibration_control_summary.csv
exp4_population_targets.csv
```

## 26.8 Checks and reports

```text
exp4_self_check.json
exp4_scientific_check.json
exp4_code_check.json
exp4_promotion_check.json
exp4_run_summary.md
output_manifest.json
output_manifest.csv
run_config.json
```

---

# 27. Raw storage

不保存 6800 万行以上的 pair-long CSV。

每个 replication 保存压缩 route maps：

```text
raw/route_maps/replication_<id>.npz
```

内部：

```text
structural_loss_map: [T, K]
arrival_time_route_map: [T, K]
history_surrogate_route_map: [T, K]
proxy_label_route_map: [T, K]
source_bound_route_map: [T, K]
```

使用：

```text
dtype = float64
```

pair-level quantities由 route maps 可重建。

manifest 保存每个 `.npz` 的 SHA-256。

---

# 28. 正文 Figure 6

正式图名建议：

> **Controlled route alignment and reliability of evidence-qualified auditing**

文件：

```text
fig_exp4_route_alignment_and_audit.pdf
fig_exp4_route_alignment_and_audit.png
fig_exp4_route_alignment_and_audit_data.csv
fig_exp4_route_alignment_and_audit_metadata.json
```

视觉上是三个 scientific blocks，实际使用四个 axes：

```text
(a) Route alignment boundary
(b1) Raw-defect estimation bias
(b2) Raw-defect estimation RMSE
(c) Calibration controls
```

## 28.1 Panel A：Route alignment boundary

正文使用 interaction point-range，不使用简单 heatmap。

横轴：

$$
q_{\mathrm{route}}
\in
\{0,0.3,0.7,1\}.
$$

纵轴：

$$
d_{\mathrm{pop,raw}}^{\mathrm{proxy\_label}}.
$$

三条曲线：

$$
\sigma_{\mathrm{proxy}}
\in
\{0.10,0.25,1.00\}.
$$

每点：

- 30-seed mean；
- 95% paired seed-bootstrap CI；
- frozen order；
- grayscale-safe marker/linetype；
- zero-defect horizontal reference。

不在图中逐个写长句解释。

3-by-4 exact value heatmap 放附录。

## 28.2 Panel B1：Signed bias

横轴：

$$
\rho_{\mathrm{audit}}.
$$

纵轴：

$$
\operatorname{Bias}
(
\widehat d_{\mathrm{raw}}
).
$$

三种 estimator：

```text
MCAR unweighted
Ambiguity-biased unweighted
Ambiguity-biased IPW
```

增加 bias $=0$ reference line。

## 28.3 Panel B2：RMSE

纵轴：

$$
\operatorname{RMSE}
(
\widehat d_{\mathrm{raw}}
).
$$

与 B1 共用 audit-rate ordering 和 estimator encoding。

不得使用双纵轴。

Panel B 下方可增加紧凑 support strip，展示：

```text
mean n_eff
mean omega_M
```

不使用点大小编码 support。

## 28.4 Panel C：Calibration-control dumbbell

两行：

```text
Affine positive control
Shuffled negative control
```

每行展示：

- raw defect point-range；
- calibrated defect point-range；
- paired connecting line；
- 95% Monte Carlo interval；
- estimated recoverability；
- negative recoverability rate。

不使用 significance stars。

---

# 29. 正文主表

文件：

```text
tbl_exp4_audit_reliability.csv
tbl_exp4_audit_reliability.tex
```

primary route 仅为 `proxy_label`。

行按：

```text
audit_evidence_rate
audit_design
```

组织。

列：

```text
raw_bias
raw_rmse
calibrated_bias
calibrated_rmse
recoverability_mae
mean_labelled_audit_sample_size
mean_effective_labelled_sample_size
mean_labelled_support_coefficient
calibration_estimable_rate
```

当 $\rho=1$ 时只保留一行 full population。

NA 不得自动填 0。

---

# 30. 附录图表

## 30.1 Route-boundary heatmap

```text
fig_app_exp4_route_boundary_heatmap
```

展示 12 primary cells 的：

$$
d_{\mathrm{pop,raw}}.
$$

## 30.2 Alignment–regret association

```text
fig_app_exp4_alignment_regret_association
```

横轴：

$$
d_{\mathrm{pop,raw}}.
$$

纵轴：

$$
R_{\mathrm{post}}^c.
$$

只解释为 association。

## 30.3 Four-route comparison

```text
fig_app_exp4_route_comparison
```

展示：

- population raw defect；
- ranking reversal rate；
- margin preservation；
- learner structural regret。

## 30.4 Effective support

```text
fig_app_exp4_effective_support
```

展示：

$$
n_{\mathrm{lab}},
\qquad
n_{\mathrm{eff}},
\qquad
\omega_M.
$$

## 30.5 Calibration distributions

```text
fig_app_exp4_calibration_distributions
```

展示：

- recoverability distributions；
- negative-recoverability rate；
- calibration-not-estimable frequency；
- nonlinear monotone control。

## 30.6 Appendix tables

```text
tbl_app_exp4_route_boundary_values
tbl_app_exp4_four_route_audit
tbl_app_exp4_calibration_controls
tbl_app_exp4_effective_support
tbl_app_exp4_learner_consequence
tbl_app_exp4_metric_definitions
```

---

# 31. Figure-data contract

每个 figure 必须包含：

```text
figure_<id>.pdf
figure_<id>.png
figure_<id>_data.csv
figure_<id>_metadata.json
```

metadata 至少记录：

```text
figure_id
experiment_id
module_ids
source_derived_files
source_file_hashes
code_commit
config_hash
generated_at
run_tier
paper_result
panel_definitions
axis_definitions
route_order
uncertainty_definition
resampling_unit
bootstrap_replications
confidence_level
```

figure source-data 必须等于最终 plotted values。

---

# 32. 图表统一规则

1. absolute defect、RMSE、error 从 0 开始；
2. signed bias 和 recoverability 可以跨 0；
3. proportions 固定在 $[0,1]$；
4. 不使用双纵轴；
5. 不截断纵轴放大微小差异；
6. route order 固定；
7. audit design order 固定；
8. 不按结果排序；
9. 统一 95% intervals；
10. 不使用 significance stars；
11. support 不足显示 NA；
12. heatmap 色标从 0 开始；
13. PDF 为正文主格式；
14. PNG 使用高分辨率；
15. 图内不堆叠完整结果句；
16. 详细解释进入 caption 和正文。

---

# 33. Hard gates

## 33.1 Structural and route gates

1. `structural_loss_map` 与 `realized_potential_feedback` 分离；
2. route-map engine 不调用 learner state；
3. learner 不读取完整 structural map；
4. observation clock 覆盖全部 source arrivals；
5. `source_bound`：

$$
d_{\mathrm{pop,raw}}^{\mathrm{source\_bound}}
<
10^{-12}.
$$

6. `proxy_label` 在 $q_{\mathrm{route}}=1$ 时，对所有 $\sigma$：

$$
d_{\mathrm{pop,raw}}^{\mathrm{proxy\_label}}
<
10^{-12}.
$$

7. 每个 post-warmup proxy-label denominator：

$$
m_t>0.
$$

8. action pairs 恰好 45；
9. PairCoverage $=1$。

## 33.2 Audit gates

1. route-label 和 audit-label streams 分离；
2. ambiguity score 不读取 latent truth；
3. ambiguity score 不读取 route-label mask；
4. inclusion probabilities 满足：

$$
0.05\leq\pi_i\leq0.95.
$$

5. expected inclusion rate tolerance：

$$
\left|
M^{-1}\sum_i\pi_i-\rho
\right|
<
10^{-8}.
$$

6. IPW 使用真实已知 $1/\pi_i$；
7. temporal folds 连续、互斥且完整；
8. held-out fold 不参与 fit；
9. calibration-not-estimable 不 fallback；
10. raw population target 可从 unit defects 重建；
11. conditional calibrated target 可从 fold maps 重建；
12. raw defect 为零时 recoverability 为 NA。

## 33.3 Reproducibility gates

1. shared path IDs 一致；
2. hash reconstruction 通过；
3. raw-to-derived reconstruction 通过；
4. derived-to-figure reconstruction 通过；
5. bootstrap 可复现；
6. full 不读取旧 result schema；
7. plotting 不重新计算 estimands；
8. full 后 `paper_result=false`；
9. 只有 promotion script 可写 `paper_result=true`。

---

# 34. 不能作为门禁的结果

不得要求：

- defect 随 route-label rate 严格单调；
- defect 随 proxy noise 严格增加；
- Proxy-label 必须优于 History；
- IPW RMSE 必须低于 unweighted；
- calibrated defect 必须低于 raw defect；
- shuffled control recoverability 必须等于零；
- affine positive control 必须达到指定效果量；
- 任意 CI 必须包含或排除零。

这些属于研究结果，不属于工程正确性。

---

# 35. STOP_AND_REVIEW 条件

出现以下任一情况时停止 full 或 paper promotion：

1. full-map route 无法对应预先定义的数学对象；
2. old `potential_losses` 仍同时承担 structural truth 和 learner feedback；
3. $q=1$ Proxy-label 不等于 Source-bound；
4. Source-bound defect 非零；
5. route-label 和 audit-label masks 不独立；
6. ambiguity score 使用 latent truth；
7. pair support 不完整；
8. inclusion probability solver 不满足目标 rate；
9. cross-fitting 退化为 full-sample fit；
10. calibrated population target 被命名为 intrinsic truth；
11. result schema 仍为 legacy；
12. main figure 读取旧 summaries；
13. full 自动设置 paper result；
14. 任何 primary parameter 在查看结果后调整；
15. main result 无法从 manifest 重建。

---

# 36. Legacy migration

## 36.1 Git freeze

修改前创建：

```text
git tag exp4-legacy-source-label-sweep
```

## 36.2 旧 run metadata

旧 run 增加或记录：

```text
result_schema = legacy_exp4_v1
paper_result = false
is_paper_eligible = false
superseded_by = exp4_controlled_route_audit
```

## 36.3 旧 outputs 的使用边界

旧 outputs 可用于：

- regression comparison；
- migration audit；
- old figure reproduction；
- DGP consistency check。

旧 outputs 不可用于：

- 新 action-gap defect；
- 新 audit estimators；
- 新 Figure 6；
- paper promotion。

## 36.4 重新运行结论

旧 output 未保存：

- deterministic structural loss map；
- full route maps；
- independent route/audit masks；
- extended observation clock；
- cross-fit maps。

因此：

```text
reuse_status = REQUIRES_RERUN
```

无需重新设计 DGP，但必须重新生成 trajectories 并运行新 estimands。

---

# 37. README 必须说明的边界

README 开头应明确：

1. Exp4 是 controlled synthetic audit；
2. Module A 使用 simulator-only full maps；
3. Module B 检验 finite evidence reliability；
4. Source-labelled identity 不自动识别 observational counterfactual gaps；
5. 本 controlled design 直接提供 structural pair truth；
6. affine calibration 是 diagnostic，不是 benchmark correction；
7. IPW 使用已知 simulated inclusion probability；
8. 不主张 general proxy impossibility；
9. fast results 不进入论文；
10. full 结果必须独立 promotion。

---

# 38. 正文补写接口

后续 Section 6.5 建议分为以下逻辑，而不是堆叠实现细节。

## 38.1 Subsection 标题

```latex
\subsection{Experiment 4: Controlled Route Alignment and Evidence-Qualified Audit}
```

## 38.2 第一段：实验任务

承担：

- 连接 Section 4 的 action-gap defect；
- 连接 Section 5 的 evidence-qualified audit；
- 说明 structural truth 在 controlled simulator 中可直接获得。

建议主句：

> Experiment 4 separates the population alignment of a fixed operational route from the reliability of an audit based on limited source-grounded comparison evidence.

## 38.3 第二段：Module A design

只交代：

- $K=10,T=5000,W=250$；
- Proxy-label route；
- route-label rate；
- attribution-proxy noise；
- primary population raw action-gap defect；
- 30 shared seeds。

正文不展开全部 kernel implementation，细节放 Appendix D.4。

## 38.4 第三段：Module A result

根据运行结果填写：

- route-label retention 与 population defect 的关系；
- proxy noise 的 interaction；
- $q=1$ source-bound invariant；
- 不把非严格单调解释为失败；
- 不将结果扩展为所有 proxy methods。

## 38.5 第四段：Module B design

只交代：

- $T_{\mathrm{audit}}=2000$；
- 200 Monte Carlo replications；
- audit evidence rates；
- MCAR、biased unweighted、biased IPW；
- raw/calibrated defects；
- $n_{\mathrm{eff}}$ 与 $\omega_M$；
- 5-fold temporal cross-fitting。

## 38.6 第五段：Audit result

根据运行结果填写：

- selective evidence 是否产生 signed bias；
- IPW 对 bias 的修正；
- 是否伴随 RMSE 变化；
- audit support 对 estimability 的影响。

禁止写：

> IPW restores causal truth.

可写：

> Under the known simulated inclusion mechanism, inverse-probability weighting reduced the selection-induced bias in the audited defect, with the corresponding variance reflected in RMSE.

## 38.7 第六段：Calibration controls

说明：

- affine positive control；
- shuffled negative control；
- recoverability 是 calibration-family-specific；
- calibrated improvement 不等于 route validity。

## 38.8 结论段

Exp4 最终只能支持：

1. route alignment 和 audit reliability 是不同问题；
2. labels used to construct a route 与 labels used to audit it 必须分开；
3. selective audit evidence 可扭曲 observed route discrepancy；
4. known-probability weighting 可以纠正 representation bias，但不保证低方差；
5. affine recoverability 只描述指定 calibration family。

---

# 39. Appendix D.4 补写接口

Appendix D.4 建议包含：

1. structural DGP；
2. deterministic structural map 与 realized feedback 的分离；
3. delay generation；
4. route maps 的完整定义；
5. route-label mask；
6. observation-clock extension；
7. action-pair orientation；
8. raw defect；
9. audit population；
10. ambiguity score；
11. inclusion probabilities；
12. IPW；
13. temporal cross-fitting；
14. conditional calibrated population target；
15. calibration controls；
16. Monte Carlo aggregation；
17. full parameter table；
18. supplementary figures and tables；
19. reproducibility and promotion status。

---

# 40. Figure caption 模板

后续根据真实结果填数，不提前写方向性结论。

```latex
\caption{
Experiment 4: controlled route alignment and evidence-qualified auditing.
Panel (a) reports the population raw action-gap defect of the Proxy-label route across source-label retention and attribution-proxy noise. Points are means over 30 shared structural trajectories and whiskers are 95\% paired seed-bootstrap intervals.
Panels (b1) and (b2) report the Monte Carlo bias and RMSE of the raw-defect estimator under MCAR evidence, ambiguity-biased evidence without weighting, and ambiguity-biased evidence with inverse-probability weighting. Results use 200 independent audit replications.
Panel (c) compares raw and out-of-fold calibrated defects under an affine positive control and a temporally blocked shuffled control. Calibration is diagnostic and conditional on the prespecified affine family.
}
```

---

# 41. Table note 模板

```latex
\begin{flushleft}
\footnotesize
Notes: The primary audited route is Proxy-label with route-label rate $0.3$ and attribution-proxy noise standard deviation $0.25$.
The audit-evidence rate is varied independently of the labels used to construct the route.
The calibrated population target is conditional on the fold-specific affine maps fitted in each audit replication.
The effective labelled sample size and support coefficient summarize evidence support and are not probabilities of route validity.
\end{flushleft}
```

---

# 42. 结果句式边界

允许：

- “The estimated raw defect was biased under ambiguity-selective audit inclusion.”
- “IPW reduced the signed bias under the known simulated inclusion probabilities.”
- “The reduction in bias was accompanied by the RMSE shown in Panel (b2).”
- “Affine calibration reduced discrepancy in the positive control.”
- “The shuffled control did not provide stable unit-level recoverability evidence.”
- “The source-bound route satisfied the zero-defect invariant.”

禁止：

- “Labels prove validity.”
- “IPW identifies the causal benchmark.”
- “Calibration validates the route.”
- “Proxy-only recovery is impossible.”
- “Negative recoverability proves no structural information.”
- “A low $\omega_M$ means the route is invalid.”

---

# 43. 编程顺序

## Phase 0：Freeze and migration

1. 创建 legacy tag；
2. 保存旧 manifests 和 figure hashes；
3. 修改目录名；
4. 写 migration record；
5. 阻止新 runner 读取 legacy schema。

## Phase 1：Configuration and naming

1. 重写 `config.py`；
2. 建立 route/module registries；
3. 建立 full parameter registry；
4. 建立 fast/full/paper status；
5. 建立 tolerances。

## Phase 2：Simulator

1. 建立 `StructuralTrajectory`；
2. 分离 structural map 和 realized feedback；
3. 延长 observation clock；
4. 实现 SeedSequence streams；
5. 实现 path hashes；
6. 保存 trajectories。

## Phase 3：Route maps

1. Source-bound；
2. Arrival-time；
3. History-surrogate；
4. Proxy-label；
5. ambiguity base assignment；
6. action gaps；
7. route invariants。

首先必须通过：

$$
d_{\mathrm{pop,raw}}^{\mathrm{source\_bound}}=0,
$$

以及：

$$
q_{\mathrm{route}}=1
\Longrightarrow
d_{\mathrm{pop,raw}}^{\mathrm{proxy\_label}}=0.
$$

## Phase 4：Module A

1. 12-cell grid；
2. 30 shared seeds；
3. seed-level outputs；
4. paired seed bootstrap；
5. route-boundary figure data；
6. appendix learner consequences。

## Phase 5：Audit engine

1. independent audit masks；
2. ambiguity score；
3. MCAR；
4. biased inclusion；
5. IPW；
6. support metrics；
7. temporal folds；
8. OLS/WLS calibration；
9. conditional population targets；
10. calibration controls。

## Phase 6：Module B

1. fast 5 replications；
2. full 200 replications；
3. replication-level outputs；
4. Monte Carlo summaries；
5. replication bootstrap；
6. primary table。

## Phase 7：Paper outputs

1. Figure 6；
2. main audit table；
3. appendix figures；
4. appendix tables；
5. figure-data bundles；
6. report；
7. manifest；
8. scientific checks。

## Phase 8：Promotion

1. independent promotion script；
2. confirm all full outputs；
3. confirm manuscript claims within scope；
4. write paper status；
5. freeze release candidate tag。

---

# 44. 实现验收清单

## Engineering PASS

```text
[ ] all commands run
[ ] required schemas complete
[ ] route maps persisted
[ ] hashes consistent
[ ] no silent fallback
[ ] fast and full isolated
[ ] plotting reads derived data only
[ ] figures reconstructable
[ ] tables reconstructable
[ ] full remains non-paper before promotion
```

## Scientific PASS

```text
[ ] structural and realized losses separated
[ ] route maps match definitions
[ ] source-bound defect zero
[ ] q=1 proxy-label defect zero
[ ] route/audit labels independent
[ ] ambiguity uses observable information only
[ ] pair coverage complete
[ ] inclusion probabilities valid
[ ] IPW uses known probabilities
[ ] temporal cross-fitting honest
[ ] conditional calibrated target correctly named
[ ] recoverability NA when raw defect zero
[ ] claims within design scope
```

## Paper PASS

```text
engineering_status = PASS
scientific_status = PASS
all_primary_full_runs_complete = true
all_primary_self_checks_pass = true
all_main_figures_reconstructable = true
all_main_tables_reconstructable = true
paper_claims_within_scope = true
```

只有全部成立，才允许：

```text
paper_result = true
```

---

# 45. 冻结项

以下内容正式冻结：

1. Exp4 正式名称为 Controlled Route Alignment and Evidence-Qualified Audit；
2. 目录名为 `exp4_controlled_route_audit`；
3. Exp4 分 Module A 与 Module B；
4. Module B 是正文核心；
5. Module A primary route 为 Proxy-label；
6. Module A grid 为 4-by-3，共 12 cells；
7. Module A primary metric 为 population raw action-gap defect；
8. absolute loss-map error 只进入附录；
9. actual learner consequence 只进入附录；
10. structural map 与 realized feedback 分离；
11. observation clock 延长至 $T+d_{\max}$；
12. route labels 与 audit evidence labels 独立；
13. ambiguity score使用 label-blind observable assignment entropy；
14. audit rates为 $0.1,0.3,0.5,1.0$；
15. audit designs为 MCAR unweighted、biased unweighted、biased IPW；
16. IPW 使用已知 simulated inclusion probabilities；
17. 5 个 contiguous temporal folds；
18. pair-specific affine calibration；
19. calibrated pair signals不重建 policy；
20. calibrated population target条件于 fitted map；
21. affine positive和 shuffled negative进入正文；
22. nonlinear monotone control仅进附录；
23. Module B full 使用200 replications；
24. 正文 Figure 6 使用 A、B1、B2、C 四 axes；
25. 正文增加 audit reliability table；
26. full 不自动 paper promotion；
27. plotting 不重新计算科学量；
28. 旧 Figure 6、旧 Tables 15--17 和旧 Figure 11 被新结果替换；
29. 旧 outputs 不可直接重建新 estimands；
30. 不增加新的模型 family、数据集或第五个实验。

---

# 46. Change control

后续任何修改必须新增 change memo：

```text
change_id
date
affected_module
affected_estimand
old_rule
new_rule
scientific_reason
code_impact
rerun_required
existing_outputs_invalidated
approval_status
```

影响以下任一内容时，必须重新判断既有 full outputs 是否失效：

- structural DGP；
- route definition；
- action-gap estimand；
- audit unit；
- ambiguity score；
- inclusion mechanism；
- route-label rate；
- audit evidence rates；
- calibration family；
- cross-fit folds；
- main figure；
- paper table；
- paper promotion rule。

---

# 47. 最终实现原则

Exp4 后续编程只优化以下目标：

1. route map 是否严格对应理论 action-comparison object；
2. population truth 与 audit estimator 是否明确分离；
3. route-construction labels 与 audit-evidence labels 是否独立；
4. finite evidence、selective evidence、weighting 和 calibration 的作用是否能够被分别识别；
5. output 是否达到科研论文的证据表达和可重建标准；
6. 正文结论是否不超过 controlled design 的识别范围。

不以增加参数、增加算法、扩大完整网格、增加图数量或自动制造显著结果作为实验质量标准。
