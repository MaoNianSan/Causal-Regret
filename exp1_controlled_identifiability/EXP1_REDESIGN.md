# EXP1 重构与本轮定向修复说明

## 1. 已固定的信息结构与 estimand

每一轮均生成

\[
S_t=0.98S_{t-1}+\varepsilon_t,\qquad X_t=S_t+\xi_t,
\]

并且所有 learner 在决定 \(A_t\) 前观察 \(X_t\)。AR(1) 过程不再截断，故
环境中用于 conditional-risk oracle 的 Gaussian posterior 与 EM 的
observable-state integration 使用同一个状态分布。报告

\[
R_T^X=\sum_{t=1}^T\left[
\mathbb E\{\ell(A_t,S_t)\mid X_t\}
-\min_a\mathbb E\{\ell(a,S_t)\mid X_t\}
\right].
\]

因此 EXP1 不再将“看不到 \(S_t\) 的不可避免损失”混入 source-binding
效应。

## 2. 主 delay 比较

`geometric_matched_15`、`mixture_matched_15`、
`state_structural_matched_15` 在每个 seed 内预生成并共享状态、上下文、
delay 和 censoring path。校准目标是最终未删失、有限 horizon 的 realised
mean delay=15。

`action_structural_stress` 仍含 \(\alpha_{A_t}\)，因而可能被 policy 改变；
它仅作为压力测试，不能进入 matched-delay 主结论。

## 3. 本轮修复 A：proxy 的训练--决策特征一致性

旧风险是 proxy 在 action 时使用 \(\widehat S_t\)，但在 visible labelled
arrival 时可能以环境给出的 \(X_s\) 更新 table。这会使

\[
\text{act}:\widehat S_t,
\qquad
\text{train}:X_s,
\]

落在不同 feature space。

现在 ProxyAgent 在每个 source time 保存

\[
(t,A_t,\widehat S_t,\operatorname{Var}(S_t\mid\text{proxy history}))
\]

并且 labelled 与 unlabelled update 都调用该 source record。环境的
`item['src_x']` 在 proxy labelled branch 中被明确禁止。每个 run 输出

`labelled_feature_alignment_max`

作为可审计证据；适用 run 必须不超过 \(10^{-12}\)。

## 4. 本轮修复 B：structural EM 的可观测条件 delay likelihood

旧实现把 noisy context 直接代入 latent-state hazard：

\[
p(X_s)(1-p(X_s))^d.
\]

这不是 \(P(D=d\mid X_s)\)。新实现使用

\[
P(D=d\mid Z_s)
\approx
\int \sigma(\beta s+c)\{1-\sigma(\beta s+c)\}^d
p(s\mid Z_s)\,ds,
\]

其中 \(Z_s=X_s\) 对 Gaussian-integrated EM，\(Z_s=\widehat S_s\) 对
proxy。积分以与 learner table 相同的 feature bin centre 为条件、采用
15-point Gauss--Hermite quadrature。这个方法称为
**Gaussian-integrated EM**，不再被称为“correctly specified EM”。

`causal_em_misspecified` 被明确命名为 **Stationary-geometric EM**；它是
丢弃 source-state dependence 的模型错设 ablation。

## 5. 代理质量压力测试

`proxy_good_matched_15` 与 `proxy_bad_matched_15` 除额外 proxy noise 外完全
相同：分别为 0.20 和 4.00。proxy 质量图只使用该二元受控比较；runner 对
两者使用共享 learner random tape，以免无关的 exploration randomness 成为
quality contrast 的来源。self-check 强制 low-quality condition 的 time-averaged
proxy error 大于 high-quality condition。

## 6. 本地验证范围

已运行：

1. `py_compile` 覆盖所有 Python 文件；
2. `python code_check.py`，其中完整 smoke design 为 264/264 组合；
3. 5,000 轮定向路径：Gaussian-integrated EM、stationary-geometric ablation、
   labelled proxy feature alignment、high/low proxy quality contrast。

该压缩包不携带旧版或本轮的 `outputs/fast`，避免任何 smoke/定向运行被误用
为正式结果。正式 fast 仍须由 `python reproduce_fast.py` 完整生成，随后运行
`python self_check.py --mode fast`。
