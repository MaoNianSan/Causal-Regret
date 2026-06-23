"""Deterministic small KuaiRand-compatible fixture for end-to-end software tests.

The fixture preserves the essential temporal contract used by the revised
experiment: history precedes main; the primary target is constructed within
each standard-log split. A random file may be emitted only to exercise optional
input discovery; it is not used by the v4 target or methods.
It is not a substitute for KuaiRand-1K and is hard-gated from paper results.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig


def _make_log(
    start_ms: int,
    n_days: int,
    n_users: int,
    n_actions: int,
    seed: int,
    cfg: ExperimentConfig,
    randomised: bool = False,
    random_offset_ms: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    day_ms = 24 * 60 * 60 * 1000
    rows: list[dict] = []
    action_effect = np.linspace(-0.8, 0.9, n_actions)
    for day in range(n_days):
        for user in range(n_users):
            user_effect = ((user % 11) - 5) * 0.04
            actions = np.arange(n_actions)
            if randomised:
                rng.shuffle(actions)
            for position, action in enumerate(actions):
                time_ms = (
                    start_ms + day * day_ms + (position + 1) * 3_600_000
                    + (user % 13) * 17_000 + random_offset_ms
                )
                latent = -0.35 + action_effect[action] + user_effect + 0.10 * np.sin(day / 2.0)
                p_click = 1.0 / (1.0 + np.exp(-latent))
                p_long = 1.0 / (1.0 + np.exp(-(latent - 0.15)))
                is_click = int(rng.random() < p_click)
                long_view = int(rng.random() < p_long)
                is_like = int(rng.random() < min(0.35, 0.025 + 0.12 * p_long))
                is_comment = int(rng.random() < min(0.18, 0.008 + 0.05 * p_long))
                is_forward = int(rng.random() < min(0.12, 0.004 + 0.035 * p_long))
                is_follow = int(rng.random() < min(0.15, 0.006 + 0.045 * p_long))
                duration = int(20_000 + 1_000 * (action % 5))
                ratio = np.clip(0.18 + 0.55 * long_view + 0.15 * is_click + rng.normal(0, 0.07), 0.02, 1.0)
                rows.append({
                    cfg.user_col: str(user),
                    cfg.video_col: f"video_{action:02d}",
                    cfg.time_col: int(time_ms),
                    cfg.date_col: f"fixture_day_{day:02d}",
                    cfg.duration_col: duration,
                    cfg.play_time_col: int(duration * ratio),
                    cfg.click_col: is_click,
                    cfg.long_view_col: long_view,
                    cfg.like_col: is_like,
                    cfg.comment_col: is_comment,
                    cfg.forward_col: is_forward,
                    cfg.follow_col: is_follow,
                })
    return pd.DataFrame(rows)


def create_fast_fixture(root: Path, cfg: ExperimentConfig = DEFAULT_CONFIG) -> Path:
    """Create a deterministic, schema-compatible fixture under ``root/data``."""
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    n_users, n_actions, n_days = 60, 20, 12
    day_ms = 24 * 60 * 60 * 1000
    history_start = 1_700_000_000_000
    main_start = history_start + n_days * day_ms
    history = _make_log(history_start, n_days, n_users, n_actions, 20260301, cfg)
    main = _make_log(main_start, n_days, n_users, n_actions, 20260302, cfg)
    # Optional intervened file for schema discovery only; v4 does not use it in
    # target construction because the primary protocol is standard-log only.
    random = _make_log(main_start, n_days, n_users, n_actions, 20260303, cfg, randomised=True, random_offset_ms=1_800_000)
    history.to_csv(data_dir / cfg.history_log, index=False)
    main.to_csv(data_dir / cfg.main_log, index=False)
    random.to_csv(data_dir / cfg.random_log, index=False)

    tags = pd.DataFrame({
        cfg.video_col: [f"video_{a:02d}" for a in range(n_actions)],
        cfg.action_source_col: [f"fixture_action_{a:02d}" for a in range(n_actions)],
    })
    tags.to_csv(data_dir / cfg.video_basic_file, index=False)
    pd.DataFrame({cfg.user_col: [str(u) for u in range(n_users)], "fixture_user_feature": np.arange(n_users)}).to_csv(
        data_dir / cfg.user_feature_file, index=False
    )
    pd.DataFrame({cfg.video_col: tags[cfg.video_col], "fixture_video_feature": np.arange(n_actions)}).to_csv(
        data_dir / cfg.video_stat_file, index=False
    )
    return root
