"""Configuration for Experiment 3: offline 6h target recoverability.

Experiment 3 is a logged-support, semi-synthetic diagnostic. It does not
identify an online policy value, an off-policy estimate, or a causal effect of
a deployed recommender.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

MS_HOUR = 60 * 60 * 1000
MS_DAY = 24 * MS_HOUR


@dataclass(frozen=True)
class ExperimentConfig:
    """All prespecified settings for the Exp3 diagnostic."""

    # Required KuaiRand-1K inputs. The random-intervention stream is excluded
    # from the primary target because the protocol has no matched random-feed
    # history split for proxy fitting.
    main_log: str = "log_standard_4_22_to_5_08_1k.csv"
    history_log: str = "log_standard_4_08_to_4_21_1k.csv"
    video_basic_file: str = "video_features_basic_1k.csv"

    # Optional audit-only inputs.
    random_log: str = "log_random_4_22_to_5_08_1k.csv"
    user_feature_file: str = "user_features_1k.csv"
    video_stat_file: str = "video_features_statistic_1k.csv"

    # Core schema.
    time_col: str = "time_ms"
    date_col: str = "date"
    user_col: str = "user_id"
    video_col: str = "video_id"
    action_source_col: str = "tag"
    click_col: str = "is_click"
    long_view_col: str = "long_view"
    play_time_col: str = "play_time_ms"
    duration_col: str = "duration_ms"
    like_col: str = "is_like"
    follow_col: str = "is_follow"
    comment_col: str = "is_comment"
    forward_col: str = "is_forward"

    # Fixed primary target.
    primary_horizon: str = "6h"
    primary_outcome_id: str = "long_value_log"
    horizons_ms: Dict[str, int] = field(
        default_factory=lambda: {
            "1h": 1 * MS_HOUR,
            "6h": 6 * MS_HOUR,
            "1d": 1 * MS_DAY,
            "3d": 3 * MS_DAY,
        }
    )
    future_value_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "long_view": 0.5,
            "like": 1.0,
            "comment": 1.0,
            "forward": 1.0,
            "follow": 1.5,
        }
    )

    # Action abstraction. The vocabulary is learned from history only. The
    # residual bucket remains in feedback accounting but never in evaluation
    # candidates.
    action_top_k: int = 20
    residual_action_bucket: str = "other"
    unknown_action_bucket: str = "unknown"
    sequential_bin_ms: int = 1 * MS_DAY
    sequential_min_cell_count: int = 50
    main_top_k: int = 10

    # Semi-synthetic pseudo-arrival mechanisms. The delay begins only after the
    # complete 6h target horizon, so an outcome cannot arrive before its target
    # window has matured.
    primary_delay_condition: str = "action_value_coupled_matched_delay_pool"
    delay_conditions: List[str] = field(
        default_factory=lambda: [
            "independent_matched_delay_pool",
            "action_value_coupled_matched_delay_pool",
        ]
    )
    pseudo_delay_min_hours: float = 6.0
    pseudo_delay_max_hours: float = 10.0

    # Main paper routes. The history-EWMA extension is an appendix robustness
    # diagnostic because it need not change the action rank relative to the
    # short-term ridge proxy.
    main_methods: List[str] = field(
        default_factory=lambda: [
            "source_aware_reference",
            "partial_source_label_q50",
            "partial_source_label_q30",
            "partial_source_label_q10",
            "history_mean_static",
            "short_term_ridge_proxy",
            "short_term_composite_surrogate",
        ]
    )
    all_methods: List[str] = field(
        default_factory=lambda: [
            "arrival_time_naive",
            "source_labelled_empirical",
            "source_aware_reference",
            "partial_source_label_q10",
            "partial_source_label_q30",
            "partial_source_label_q50",
            "history_mean_static",
            "short_term_ridge_proxy",
            "history_ewma_ridge_proxy",
            "short_term_composite_surrogate",
        ]
    )
    partial_label_rates: List[float] = field(default_factory=lambda: [0.10, 0.30, 0.50])

    # Dynamic empirical state and proxy models.
    empirical_prior_count: float = 10.0
    ridge_alpha: float = 4.0
    ewma_alpha: float = 0.30

    # The same seeds define the finite bank of independent event-level label
    # masks used for point estimates and mask-bank resampling in uncertainty
    # summaries. Full mode deliberately uses 30 independent trajectories.
    fast_replication_seeds: List[int] = field(default_factory=lambda: [0, 1, 2])
    full_replication_seeds: List[int] = field(default_factory=lambda: list(range(30)))
    fast_bootstrap_n: int = 100
    full_bootstrap_n: int = 1000
    ci_level: float = 0.95

    # Fast mode uses all real users unless a development-only limit is set.
    fast_users: int | None = None
    full_users: int | None = None


def ensure_output_dirs(output_dir: Path) -> None:
    """Create the complete output contract for one run directory."""
    for subdir in [
        "raw",
        "processed",
        "summaries",
        "tables",
        "checks",
        "legacy",
        "logs",
        "metadata",
        "reports",
        "figures/pdf",
        "figures/png",
        "figures/data",
        "figures/metadata",
    ]:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)


DEFAULT_CONFIG = ExperimentConfig()
