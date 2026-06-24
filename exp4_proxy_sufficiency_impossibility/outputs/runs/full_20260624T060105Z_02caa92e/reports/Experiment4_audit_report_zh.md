# Experiment 4 中文审计报告：source-label sufficiency and proxy-only recovery limitation

## 0. 审计结论

| 项目 | 结论 |
|---|---|
| 实验版本 | full_20260624T060105Z_02caa92e |
| 当前运行是否可作为论文数值 | 是；须以本 full 30-seed 输出和 percentile-bootstrap CI 为准 |
| 实验定位 | source-label sufficiency and proxy-only recovery limitation 的受控压力测试 |
| 不可声称 | real-world RCT、真实总体 causal effect、一般 information-theoretic impossibility theorem |
| 主要证据结构 | proxy distortion diagnostic → source-label sweep → q × sigma map |

## 1. 信息接口

| 方法 | arrival feedback | source label | proxy | diagnostic only | deployable |
|---|---|---|---|---|---|
| arrival_time_naive | 是 | 否 | coarse_context_only | 否 | 是 |
| observable_history_surrogate | 是 | 否 | coarse_context_only | 否 | 是 |
| proxy_label_recovery | 是 | partial | candidate_source_similarity | 否 | 是 |
| source_labelled_reference | 是 | 是 | coarse_context_only | 否 | 否 |
| proxy_noisy_oracle_diagnostic | 否 | 否 | instantaneous_noisy_measurement | 是 | 否 |
| proxy_oracle_diagnostic | 否 | 否 | latent_state | 是 | 否 |

## 2. 解释边界

- primary outcome 是 warmup 后 structural causal regret；warmup 仅从汇总中排除早期共同探索，不删除学习历史。
- proxy distortion panel 仅表明 simulator-emitted arrival-time measurement proxy 越噪，环境侧 loss-map distortion 越高；它不是可部署 proxy learner 的胜负比较。
- q × sigma map 的 oracle-normalized recovery 使用 latent action oracle 作归一化锚点；因此 q=1 不必等于 1。
- In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25.
- A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.
- 附录另报 source-labelled-normalized recovery；该指标以 source-labelled online reference 为锚点，q=1 在 action trace 相等审计通过时等于 1。
- 当前环境下最应检验的是：改善指定 proxy-recovery route 的 measurement precision 是否能替代 source binding；不能将弱 sigma 效应包装成通用二维相变。
- `proxy_label_recovery` 是固定 bounded-window RBF similarity + recency prior 的透明软归因路线。结果不能推出所有可能的 learned, calibrated, or delay-model-aware proxy-only algorithms 都无效。

## 3. 图表和统计

- 正文图： (a) proxy-state error 对 loss-map distortion；(b) 固定 sigma=0.25 的 q sweep，其中 arrival-time 和 history surrogate 作为水平参考线；(c) q × sigma arrival–oracle recovery map。
- heatmap 的存储值为 raw metric；仅 colour display 使用固定 [0,1] 参考尺度。In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25. A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.
- appendix coupling 图只展示 ranking reversal 与 source-binding advantage，不再重复四条 regret trajectory。
- fast 使用 3 个 shared seeds，只有 point estimates。full 使用 30 个 shared seeds 和 2000 次 paired percentile bootstrap resamples，报告 CI，不报告 p-value。

## 4. 自动核对

- seed-level rows: 2340
- observed methods: arrival_time_naive, observable_history_surrogate, proxy_label_recovery, proxy_noisy_oracle_diagnostic, proxy_oracle_diagnostic, source_labelled_reference
- comparison status: formal_full_paired_percentile_bootstrap_ci
- raw arrival–oracle recovery range: [0.0641, 0.5403]
- raw source-labelled-normalized recovery range: [0.1170, 1.0000]

## 5. 可用表述

- 在此受控环境内，source-label retention 是 structural-regret recovery 的主要通道；指定 proxy-recovery route 的 measurement precision 改善会降低 loss-map distortion，但不能一般性替代 source-linked feedback。
- q=1 时，proxy-label recovery 与 source-labelled reference 的 action trace 和 regret 逐 seed 一致。
- coupling diagnostic 表明 source-arrival ranking mismatch 会随设定变化。The source-binding advantage is positive across the tested coupling settings, but is not claimed to increase monotonically with beta. beta = 0 denotes no additional delay-state association. It does not imply zero delay or zero source-arrival mismatch.

## 6. 不应表述

- 任意现实 proxy 都足以恢复 source binding，或任意 proxy-only algorithm 都不能恢复 source binding。
- q 与 sigma 在所有环境中具有同等强度或相同形式的 recoverability effect。
- 本模拟器已经证明一般意义上的 impossibility theorem。
