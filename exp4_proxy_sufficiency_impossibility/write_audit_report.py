"""Generate a concise Chinese audit report for Exp4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import config


def yn(value: object) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return str(value)


def run(run_dir: Path) -> None:
    run_config = json.loads((run_dir / "logs" / "run_config.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(run_dir / "raw" / "seed_level_results.csv")
    phase = pd.read_csv(run_dir / "summaries" / "recoverability_phase_map_summary.csv")
    source_recovery = phase
    comparisons = pd.read_csv(run_dir / "summaries" / "paired_bootstrap_comparisons.csv")
    lines = [
        "# Experiment 4 中文审计报告：source-label sufficiency and proxy-only recovery limitation", "",
        "## 0. 审计结论", "",
        "| 项目 | 结论 |", "|---|---|",
        f"| 实验版本 | {run_dir.name} |",
        f"| 当前运行是否可作为论文数值 | {'否；fast 仅用于接口、语义与方向检查' if run_config['mode'] == 'fast' else '是；须以本 full 30-seed 输出和 percentile-bootstrap CI 为准'} |",
        "| 实验定位 | source-label sufficiency and proxy-only recovery limitation 的受控压力测试 |",
        "| 不可声称 | real-world RCT、真实总体 causal effect、一般 information-theoretic impossibility theorem |",
        "| 主要证据结构 | proxy distortion diagnostic → source-label sweep → q × sigma map |", "",
        "## 1. 信息接口", "",
        "| 方法 | arrival feedback | source label | proxy | diagnostic only | deployable |", "|---|---|---|---|---|---|",
    ]
    for method_id, spec in config.METHOD_REGISTRY.items():
        lines.append(f"| {method_id} | {yn(spec['uses_arrival_feedback'])} | {yn(spec['uses_source_labels'])} | {spec['uses_proxy']} | {yn(spec['diagnostic_only'])} | {yn(spec['deployable'])} |")
    lines += [
        "", "## 2. 解释边界", "",
        "- primary outcome 是 warmup 后 structural causal regret；warmup 仅从汇总中排除早期共同探索，不删除学习历史。",
        "- proxy distortion panel 仅表明 simulator-emitted arrival-time measurement proxy 越噪，环境侧 loss-map distortion 越高；它不是可部署 proxy learner 的胜负比较。",
        "- q × sigma map 的 oracle-normalized recovery 使用 latent action oracle 作归一化锚点；因此 q=1 不必等于 1。",
        "- In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25.",
        "- A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.",
        "- 附录另报 source-labelled-normalized recovery；该指标以 source-labelled online reference 为锚点，q=1 在 action trace 相等审计通过时等于 1。",
        "- 当前环境下最应检验的是：改善指定 proxy-recovery route 的 measurement precision 是否能替代 source binding；不能将弱 sigma 效应包装成通用二维相变。",
        "- `proxy_label_recovery` 是固定 bounded-window RBF similarity + recency prior 的透明软归因路线。结果不能推出所有可能的 learned, calibrated, or delay-model-aware proxy-only algorithms 都无效。", "",
        "## 3. 图表和统计", "",
        "- 正文图： (a) proxy-state error 对 loss-map distortion；(b) 固定 sigma=0.25 的 q sweep，其中 arrival-time 和 history surrogate 作为水平参考线；(c) q × sigma arrival–oracle recovery map。",
        "- heatmap 的存储值为 raw metric；仅 colour display 使用固定 [0,1] 参考尺度。In panel (c), sigma perturbs only the attribution proxy used to weight candidate historical sources. The decision-time context proxy is held fixed at sigma = 0.25. A value of one in the arrival-oracle normalized recovery map corresponds to the latent action oracle, not to the source-labelled online reference.",
        "- appendix coupling 图只展示 ranking reversal 与 source-binding advantage，不再重复四条 regret trajectory。",
        f"- fast 使用 {len(config.SEEDS_FAST)} 个 shared seeds，只有 point estimates。full 使用 {len(config.SEEDS_FULL)} 个 shared seeds 和 {config.BOOTSTRAP_N} 次 paired percentile bootstrap resamples，报告 CI，不报告 p-value。", "",
        "## 4. 自动核对", "",
        f"- seed-level rows: {len(raw)}",
        f"- observed methods: {', '.join(sorted(raw['method_id'].unique()))}",
        f"- comparison status: {', '.join(sorted(comparisons['inference_status'].dropna().unique()))}",
        f"- raw arrival–oracle recovery range: [{phase['oracle_normalized_recovery_mean'].min():.4f}, {phase['oracle_normalized_recovery_mean'].max():.4f}]",
        f"- raw source-labelled-normalized recovery range: [{source_recovery['source_labelled_normalized_recovery_mean'].min():.4f}, {source_recovery['source_labelled_normalized_recovery_mean'].max():.4f}]", "",
        "## 5. 可用表述", "",
        "- 在此受控环境内，source-label retention 是 structural-regret recovery 的主要通道；指定 proxy-recovery route 的 measurement precision 改善会降低 loss-map distortion，但不能一般性替代 source-linked feedback。",
        "- q=1 时，proxy-label recovery 与 source-labelled reference 的 action trace 和 regret 逐 seed 一致。",
        "- coupling diagnostic 表明 source-arrival ranking mismatch 会随设定变化。The source-binding advantage is positive across the tested coupling settings, but is not claimed to increase monotonically with beta. beta = 0 denotes no additional delay-state association. It does not imply zero delay or zero source-arrival mismatch.", "",
        "## 6. 不应表述", "",
        "- 任意现实 proxy 都足以恢复 source binding，或任意 proxy-only algorithm 都不能恢复 source binding。",
        "- q 与 sigma 在所有环境中具有同等强度或相同形式的 recoverability effect。",
        "- 本模拟器已经证明一般意义上的 impossibility theorem。",
    ]
    (run_dir / "reports" / "Experiment4_audit_report_zh.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.run_dir)


if __name__ == "__main__":
    main()
