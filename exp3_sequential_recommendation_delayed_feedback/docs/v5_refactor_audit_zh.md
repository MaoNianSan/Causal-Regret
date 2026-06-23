# Exp3 V5 审计与规范化完成说明

## 结论

上一版 real-data fast 的主要设计边界已基本正确：target 在 standard log 内构造、random log 不混入主 target、action vocabulary 来自 history、carrier 不使用未来 exposure、partial label 路线为 source update 与 carrier fallback 的混合规则。

但仍发现两项会改变 proxy 数值的时序实现问题，因此不能直接运行旧版 full：

1. proxy 的缺失 action fallback 使用了全体 main period 的 proxy/composite 平均，包含当前决策时点之后的 main bins；
2. history ridge 训练的最早 action-bin features 使用了完整 history 的 global average，包含未来 history bins。

V5 已移除这两类 look-ahead。旧 real-data fast 仅保留为工程审计，不可作为 V5 论文数值。

## V5 的固定建模口径

- **source event**：standard-feed video exposure；
- **target**：同一用户在 source 后 6h 内、同一 standard-log stream 的构造 future engagement；
- **pseudo-arrival**：6h--10h，位于完整 target window 后；
- **carrier**：pseudo-arrival 时点之前该用户最近一次 standard exposure；
- **partial labels**：被抽中时更新 source action，未抽中时更新 carrier action；
- **proxy**：history split 拟合 ridge；main score 只能使用 completed history 与 earlier main bins 的 immediate feedback；
- **metric**：support-restricted daily action-category ranking regret；
- **scope**：offline target recoverability diagnostic，不是 causal regret、OPE 或 online policy effect。

## 不确定性口径

- full point estimate：30 个独立 event-level label-mask trajectories 的均值；
- interval：user-cluster resampling，proxy score 与 support mask 固定；
- 每个 partial-label bootstrap draw 从有限 mask bank 中抽取一条 event-level trajectory；
- 因此该 interval 表示固定 calendar window、固定 history-fit proxy 与固定 support 约束下的 user-composition / label-availability diagnostic uncertainty；不声称其为 OPE CI 或跨时间泛化区间。

## 代码规范化

1. `--n-jobs` 现在实际用于 target construction 的 user-level parallelization；
2. manifest 新增 `run_id`、`config_hash`、`main_feature_information`；
3. full promotion 重新生成所有 figure CSV/JSON/PDF/PNG，并更新 artifact manifest；
4. `PreparedCondition` 明确定义 proxy coefficient table 字段，不再运行时动态附加属性；
5. 新增 `tests/test_temporal_contracts.py`：验证 carrier 不使用未来 exposure，且 main proxy state 对未来 main-bin 修改不敏感；
6. 更新 README、metric specification、output contract、literature alignment 与 previous-fast audit。

## V5 real fast / full 运行顺序

```bash
python code_check.py
python tests/test_temporal_contracts.py
python reproduce_fast.py --n-jobs 12
python self_check.py --mode fast

# 审计 real fast 后再运行
python reproduce_full.py --n-jobs 24
python self_check.py --mode full
python self_check.py --mode full --promote-paper-result
```

`full` 必须使用完整 KuaiRand 原始输入。V5 fast 如发现原始输入缺失，会自动改用 synthetic fixture；此时 manifest 的 `input_data_status=synthetic_test_fixture` 且 `paper_result=false`，不得用于论文。
