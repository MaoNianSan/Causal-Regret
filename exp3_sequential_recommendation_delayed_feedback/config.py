"""Frozen configuration for Experiment 3.

Experiment 3 is a logged-support diagnostic of score, held-out action-gap, and
cross-fitted ranking recovery. It is not online policy evaluation, OPE, or an
estimator of structural causal regret.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MS_HOUR = 60 * 60 * 1000
MS_DAY = 24 * MS_HOUR


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str = "exp3"
    experiment_slug: str = "proxy_score_gap_ranking_recovery"
    timezone_name: str = "Asia/Shanghai"
    timezone_rule: str = "Asia/Shanghai_epoch_day"
    history_start_local_date: str = "2022-04-08"
    split_boundary_local_date: str = "2022-04-22"
    max_prestart_history_fraction: float = 0.001
    max_preboundary_evaluation_fraction: float = 0.001

    # Required KuaiRand inputs.
    history_log: str = "log_standard_4_08_to_4_21_1k.csv"
    evaluation_log: str = "log_standard_4_22_to_5_08_1k.csv"
    video_basic_file: str = "video_features_basic_1k.csv"

    # Raw schema.
    user_col: str = "user_id"
    video_col: str = "video_id"
    time_col: str = "time_ms"
    tag_col: str = "tag"
    duration_col: str = "duration_ms"
    play_time_col: str = "play_time_ms"
    click_col: str = "is_click"
    long_view_col: str = "long_view"
    like_col: str = "is_like"
    follow_col: str = "is_follow"
    comment_col: str = "is_comment"
    forward_col: str = "is_forward"

    # Target and action abstraction.
    target_horizon_hours: int = 6
    target_horizon_ms: int = 6 * MS_HOUR
    action_top_k_full: int = 20
    action_top_k_fast: int = 6
    residual_action_bucket: str = "residual_action_bucket"
    unknown_action_bucket: str = "unknown_action_bucket"
    include_residual_in_candidate_set: bool = False
    future_value_weights: dict[str, float] = field(
        default_factory=lambda: {
            "long_view": 0.5,
            "like": 1.0,
            "comment": 1.0,
            "forward": 1.0,
            "follow": 1.5,
        }
    )

    # Audit design. Full values are the paper-scale specification. Fast values
    # reduce real-data computation and are also used by the explicit software fixture;
    # neither fast path is paper eligible.
    user_group_candidates_full: tuple[int, ...] = (10, 5)
    user_group_candidates_fast: tuple[int, ...] = (4, 2)
    support_min_events_per_fold_full: int = 500
    support_min_events_per_fold_fast: int = 15
    history_support_pass_threshold: float = 0.80
    support_limited_threshold: float = 0.50
    group_hash_salt: str = "exp3-user-group-v1"
    reference_fold_hash_salt: str = "exp3-reference-fold-v1"
    reference_fold_count: int = 2
    near_tie_multiplier: float = 0.10

    # Routes and model.
    primary_route_ids: tuple[str, ...] = (
        "arrival_carrier",
        "history_mean_control",
        "ridge_proxy",
    )
    history_prior_count: float = 10.0
    ridge_alpha: float = 4.0

    # Pseudo-arrival construction.
    pseudo_delay_seed: int = 20260725
    pseudo_delay_min_hours: float = 6.0
    pseudo_delay_max_hours: float = 10.0

    # User-cluster resampling sensitivity. The empirical percentile range is a
    # stability diagnostic, not a formally validated confidence interval.
    fast_bootstrap_repetitions: int = 100
    full_bootstrap_repetitions: int = 1000
    bootstrap_seed: int = 31072026
    resampling_range_level: float = 0.95
    resampling_range_method: str = "percentile_user_cluster_sensitivity"
    resampling_output_role: str = "sensitivity_only"
    formal_ci_validated: bool = False
    valid_bootstrap_fraction_gate: float = 0.95
    bootstrap_bias_sd_warning_threshold: float = 1.0

    # Fast fixture only.
    fast_fixture_seed: int = 314159
    fast_fixture_users: int = 48
    fast_fixture_history_days: int = 8
    fast_fixture_evaluation_days: int = 8
    fast_fixture_events_per_user_day: int = 90

    def action_top_k(self, run_tier: str) -> int:
        return self.action_top_k_fast if run_tier == "fast" else self.action_top_k_full

    def group_candidates(self, run_tier: str) -> tuple[int, ...]:
        return (
            self.user_group_candidates_fast
            if run_tier == "fast"
            else self.user_group_candidates_full
        )

    def support_min_events_per_fold(self, run_tier: str) -> int:
        return (
            self.support_min_events_per_fold_fast
            if run_tier == "fast"
            else self.support_min_events_per_fold_full
        )

    def bootstrap_repetitions(self, run_tier: str) -> int:
        return (
            self.fast_bootstrap_repetitions
            if run_tier == "fast"
            else self.full_bootstrap_repetitions
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_CONFIG = ExperimentConfig()


def ensure_output_dirs(output_dir: Path) -> None:
    for relative in (
        "design",
        "processed",
        "derived",
        "tables",
        "figures/main",
        "figures/appendix",
        "figures/data",
        "figures/metadata",
        "diagnostics",
        "checks",
        "metadata",
        "reports",
        "legacy",
    ):
        (output_dir / relative).mkdir(parents=True, exist_ok=True)
