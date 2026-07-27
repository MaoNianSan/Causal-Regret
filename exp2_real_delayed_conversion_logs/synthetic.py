from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def create_synthetic_fixture(path: str | Path, *, seed: int = 20260725) -> Path:
    """Create a deterministic contract fixture with nondegenerate source-time ambiguity.

    The fixture intentionally covers all five reporting delay bins while keeping the
    primary cohort, decision-cell definition, and attribution-route contracts unchanged.
    """

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    base = pd.Timestamp("2026-01-01T00:00:00Z")
    campaigns = [f"campaign_{index:02d}" for index in range(8)]
    support_days = list(range(10, 50))
    arrival_days = list(range(40, 50))
    rows: list[dict[str, object]] = []

    # An early row establishes a complete 30-day lookback boundary.
    rows.append(
        {
            "timestamp": int(base.timestamp()),
            "uid": "background_early",
            "campaign": "background",
            "conversion": 0,
            "conversion_timestamp": 0,
            "conversion_id": "",
            "attribution": 0,
            "click": 0,
            "cost": 0.0,
            "cpo": 0.0,
        }
    )

    # Route-independent exposure support: 8 campaigns x 40 dates.
    for campaign in campaigns:
        for day in support_days:
            event_time = base + pd.Timedelta(days=day, hours=8)
            for replicate in range(60):
                rows.append(
                    {
                        "timestamp": int((event_time + pd.Timedelta(seconds=replicate)).timestamp()),
                        "uid": f"background_{campaign}_{day}_{replicate}",
                        "campaign": campaign,
                        "conversion": 0,
                        "conversion_timestamp": 0,
                        "conversion_id": "",
                        "attribution": 0,
                        "click": 0,
                        "cost": 0.0,
                        "cpo": 0.0,
                    }
                )

    n_journeys = 900
    same_day_offsets = [
        pd.Timedelta(minutes=30),   # <= 1 h
        pd.Timedelta(hours=4),      # 1--6 h
        pd.Timedelta(hours=11),     # 6--24 h
    ]
    prior_day_offsets = [
        pd.Timedelta(days=2, hours=11),   # 1--7 d
        pd.Timedelta(days=5, hours=11),   # 1--7 d
        pd.Timedelta(days=10, hours=11),  # 7--30 d
        pd.Timedelta(days=20, hours=11),  # 7--30 d
        pd.Timedelta(days=28, hours=11),  # 7--30 d
    ]

    for journey_index in range(n_journeys):
        user_id = f"user_{journey_index % 420:04d}"
        campaign = campaigns[journey_index % len(campaigns)]
        arrival_day = arrival_days[journey_index % len(arrival_days)]
        conversion_time = base + pd.Timedelta(days=arrival_day, hours=20)
        candidate_count = int(rng.choice([1, 2, 3, 4], p=[0.55, 0.25, 0.15, 0.05]))

        # Every journey has one same-date source. Rotating its clock time covers the
        # three sub-day bins without creating multiple same-date decision cells.
        offsets = [same_day_offsets[journey_index % len(same_day_offsets)]]
        if candidate_count > 1:
            start = journey_index % len(prior_day_offsets)
            ordered_prior = prior_day_offsets[start:] + prior_day_offsets[:start]
            offsets.extend(ordered_prior[: candidate_count - 1])

        source_times = sorted(conversion_time - offset for offset in offsets)
        conversion_id = f"conversion_{journey_index:06d}"
        click_index = int(rng.integers(0, len(source_times))) if rng.random() < 0.65 else -1
        labelled_index = len(source_times) - 1
        for local_index, source_time in enumerate(source_times):
            rows.append(
                {
                    "timestamp": int(source_time.timestamp()),
                    "uid": user_id,
                    "campaign": campaign,
                    "conversion": 1,
                    "conversion_timestamp": int(conversion_time.timestamp()),
                    "conversion_id": conversion_id,
                    "attribution": int(local_index == labelled_index),
                    "click": int(local_index == click_index),
                    "cost": float(rng.uniform(0.0, 1.0)),
                    "cpo": float(rng.uniform(0.0, 1.0)),
                }
            )

    frame = pd.DataFrame(rows)
    frame.to_csv(output, sep="\t", index=False)
    return output
