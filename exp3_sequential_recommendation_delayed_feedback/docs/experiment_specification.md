# Experiment specification

Exp3 evaluates whether historical and lagged short-term proxy scores preserve the ranking of a constructed 6h future-engagement target in held-out sequential recommendation logs.

Fixed settings: `dataset_id=kuairand_1k`, `primary_horizon=6h`, `primary_target=long_value_log`, `time_bin=1d`, `candidate_action_count=20`, `main_top_k=10`, history split `log_standard_4_08_to_4_21_1k.csv`, main split `log_standard_4_22_to_5_08_1k.csv`, bootstrap unit `user_id`, full bootstraps `1000`, full partial-label mask replicates `30`.

Fast outputs are never paper results. Only full outputs with `paper_result=true` may be cited in LaTeX.
