"""Deterministic fast fixture for software and figure-contract testing only."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG, ExperimentConfig, MS_DAY
from utilities import save_json


def _make_split(
    *,
    start_day: str,
    day_count: int,
    user_count: int,
    events_per_user_day: int,
    action_count: int,
    seed: int,
    cfg: ExperimentConfig,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start_ms = int(pd.Timestamp(start_day, tz=cfg.timezone_name).timestamp() * 1000)
    rows: list[dict[str, object]] = []
    action_quality = np.linspace(-0.6, 0.9, action_count)
    for user_index in range(user_count):
        user_id = f"user_{user_index:04d}"
        user_shift = rng.normal(0.0, 0.18)
        preferred = user_index % action_count
        for day_index in range(day_count):
            day_shift = 0.18 * np.sin(2.0 * np.pi * day_index / max(day_count, 2))
            base = start_ms + day_index * MS_DAY
            # Balanced cyclic actions guarantee that the fixture exercises the
            # full support logic instead of passing through a degenerate action.
            action_indices = (np.arange(events_per_user_day) + user_index + day_index) % action_count
            jitter = np.sort(rng.integers(0, MS_DAY - 1, size=events_per_user_day))
            for event_index, (action_index, offset) in enumerate(zip(action_indices, jitter)):
                preference = 0.35 if int(action_index) == preferred else 0.0
                latent = action_quality[int(action_index)] + user_shift + day_shift + preference
                p_click = 1.0 / (1.0 + np.exp(-(latent - 0.15)))
                p_long = 1.0 / (1.0 + np.exp(-(latent - 0.45)))
                p_deep = 1.0 / (1.0 + np.exp(-(latent - 1.1)))
                duration = int(rng.integers(8_000, 45_000))
                watch_fraction = np.clip(rng.normal(0.48 + 0.18 * p_long, 0.18), 0.02, 1.0)
                rows.append(
                    {
                        cfg.user_col: user_id,
                        cfg.video_col: f"video_{int(action_index):02d}",
                        cfg.time_col: int(base + int(offset)),
                        cfg.duration_col: duration,
                        cfg.play_time_col: int(duration * watch_fraction),
                        cfg.click_col: int(rng.random() < p_click),
                        cfg.long_view_col: int(rng.random() < p_long),
                        cfg.like_col: int(rng.random() < 0.45 * p_deep),
                        cfg.follow_col: int(rng.random() < 0.15 * p_deep),
                        cfg.comment_col: int(rng.random() < 0.12 * p_deep),
                        cfg.forward_col: int(rng.random() < 0.08 * p_deep),
                        "fixture_event_index": event_index,
                    }
                )
    return pd.DataFrame(rows).sort_values([cfg.user_col, cfg.time_col], kind="stable").reset_index(drop=True)


def create_fast_fixture(input_root: Path, cfg: ExperimentConfig = DEFAULT_CONFIG) -> dict[str, object]:
    data_dir = input_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    action_count = cfg.action_top_k_fast + 2
    video = pd.DataFrame(
        {
            cfg.video_col: [f"video_{index:02d}" for index in range(action_count)],
            cfg.tag_col: [f"tag_{index:02d}" for index in range(action_count)],
        }
    )
    history = _make_split(
        start_day="2022-04-08",
        day_count=cfg.fast_fixture_history_days,
        user_count=cfg.fast_fixture_users,
        events_per_user_day=cfg.fast_fixture_events_per_user_day,
        action_count=action_count,
        seed=cfg.fast_fixture_seed,
        cfg=cfg,
    )
    evaluation = _make_split(
        start_day="2022-04-22",
        day_count=cfg.fast_fixture_evaluation_days,
        user_count=cfg.fast_fixture_users,
        events_per_user_day=cfg.fast_fixture_events_per_user_day,
        action_count=action_count,
        seed=cfg.fast_fixture_seed + 1,
        cfg=cfg,
    )
    history.to_csv(data_dir / cfg.history_log, index=False)
    evaluation.to_csv(data_dir / cfg.evaluation_log, index=False)
    video.to_csv(data_dir / cfg.video_basic_file, index=False)
    payload = {
        "fixture": True,
        "paper_result": False,
        "user_count": cfg.fast_fixture_users,
        "history_day_count": cfg.fast_fixture_history_days,
        "evaluation_day_count": cfg.fast_fixture_evaluation_days,
        "events_per_user_day": cfg.fast_fixture_events_per_user_day,
        "available_action_count": action_count,
        "seed": cfg.fast_fixture_seed,
    }
    save_json(payload, input_root / "FAST_FIXTURE_MANIFEST.json")
    return payload
