# Exp3 V5.1 重构说明

本轮在 V5 的 strict history/main separation 基础上加入了一个 history-only static control，并对机制对比的推断和图内标签进行了规范化。

- `history_mean_static`：只使用 history-standard 中每个 action category 的 6h target 均值；不使用任何 main 期短期 proxy、到达消息或 source label。该路线用于分辨稳定 category persistence 与 lagged short-term proxy 的增益。
- `oracle_action_dynamics_summary.csv`：报告 oracle top action 的 unique count、switch rate 和最大占比，作为任务稳定性审计。
- `paired_mechanism_contrast.csv`：使用同一 bootstrap replicate 的 user weights 在 independent 与 coupled 机制间形成 paired contrast。
- 图中采用 `plot_label`，而 metadata 和 CSV 仍保留完整 `method_display_name`。
- 主图 Panel A 仅显示 `ST ridge` 的 held-out calibration；`Hist-EWMA ridge` 留在完整表和原始 calibration outputs 中。

V5.1 没有改变实验的解释边界：它仍是 logged-support、semi-synthetic、offline 6h target recoverability diagnostic，不是 OPE、线上 policy uplift 或 causal-regret result。
