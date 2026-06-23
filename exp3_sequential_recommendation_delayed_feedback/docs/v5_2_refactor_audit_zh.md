# Exp3 V5.2 图表与证据边界规范化

V5.2 不改变 6h target、history/main chronological split、carrier 规则、action
vocabulary、partial-label 更新机制或 proxy 拟合方式。它仅把上一轮 fast
分析暴露出的**解释和图表接口问题**固定到代码 contract 中。

1. 新增 `paired_effect_vs_history_mean_static.csv`。以 `history_mean_static`
   为配对 comparator，正值表示相对于纯 history category mean 的 regret
   reduction。区间跨零时，禁止将 ST ridge 写成具有已证实的增量动态价值。
2. 新增 `tbl_app_exp3_proxy_static_control.csv`，将 static control、proxy
   regret 及其 paired effect 置于同一表。
3. source-label coverage 不再绘制曲线，改为
   `tbl_app_exp3_source_label_sensitivity.csv`，同时报告 q、regret、CI、
   相对 Carrier 的 reduction 及预期 labelled source outcome 的绝对数量。
   该表不得被解释为单调性或“10% label 足够”的证据。
4. 删除 active `fig_app_exp3_arrival_mechanism_contrast`。
   `paired_mechanism_contrast.csv` 继续保留为 audit，但在当前 daily-bin
   证据不稳定时不再用图形放大其机制解释。
5. `fig_app_exp3_horizon_saturation` 改为
   `fig_app_exp3_horizon_eligibility`，展示 right-censoring rate，而非随
   horizon 几乎必然增加的 cumulative target mean。
6. 主图直接标识 `y = x`、`Carrier baseline`、`Reference (offline)`、
   points 与 95% user-bootstrap CI 的含义，并在 metadata/caption note 中
   写入 ST ridge 对 History mean 的 paired comparison。
7. 每次 rerender 先将 retired active bundles 移入
   `legacy/retired_figures/v5_2_retired_interface/`，避免遗留图被 LaTeX
   或 artifact manifest 误读取。

V5.2 仍仅是 offline logged-support、semi-synthetic 6h target
recoverability diagnostic；不是 OPE、线上 uplift、causal regret 或 platform
utility result。
