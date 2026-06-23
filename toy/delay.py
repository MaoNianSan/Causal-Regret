# delay.py
import random
import math
from dataclasses import dataclass
from typing import Callable, Dict, Any, List


def sample_geometric(p: float) -> int:
    """Sample a geometric delay with support {1, 2, ...}."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"p must be in (0,1), got {p}")
    u = random.random()
    return int(math.ceil(math.log(1.0 - u) / math.log(1.0 - p)))


@dataclass
class DelaySetting:
    name: str
    sampler: Callable[[int], int]  # maps decision time t to a sampled delay
    meta: Dict[str, Any]


def build_delay_settings(
    *,
    switch_t: int = 1000,
    w: float = 0.2,
    p_short: float = 0.6,
    p_long: float = 0.15,
    p_fast: float = 0.6,
    p_slow: float = 0.1,
) -> List[DelaySetting]:
    """
    Build the toy delay settings available for the appendix experiment.
    Only the settings selected in config.yaml are used in a run.
    """
    settings = []

    # 1) Immediate feedback
    settings.append(
        DelaySetting(
            name="0_delay",
            sampler=lambda t: 0,
            meta=dict(type="zero_delay"),
        )
    )

    # 2) Geometric delay with shorter expected lag
    settings.append(
        DelaySetting(
            name="geom_0.6",
            sampler=lambda t, p=p_short: sample_geometric(p),
            meta=dict(type="geometric", p=p_short),
        )
    )

    # 3) Geometric delay with longer expected lag
    settings.append(
        DelaySetting(
            name="geom_0.15",
            sampler=lambda t, p=p_long: sample_geometric(p),
            meta=dict(type="geometric", p=p_long),
        )
    )

    # 4) Mixture geometric delay
    def mixture_sampler(t, w=w, pf=p_fast, ps=p_slow):
        return sample_geometric(pf) if random.random() < w else sample_geometric(ps)

    settings.append(
        DelaySetting(
            name="mixed_geom_0.6+0.1_w0.2",
            sampler=mixture_sampler,
            meta=dict(type="mixture", w=w, p_fast=p_fast, p_slow=p_slow),
        )
    )

    # 5) Piecewise delay: long -> short
    def piecewise_long_to_short(t, st=switch_t, p1=p_long, p2=p_short):
        return sample_geometric(p1) if t <= st else sample_geometric(p2)

    settings.append(
        DelaySetting(
            name="piece_0.15to0.6",
            sampler=piecewise_long_to_short,
            meta=dict(type="piecewise", switch_t=switch_t, p1=p_long, p2=p_short),
        )
    )

    # 6) Piecewise delay: short -> long
    def piecewise_short_to_long(t, st=switch_t, p1=p_short, p2=p_long):
        return sample_geometric(p1) if t <= st else sample_geometric(p2)

    settings.append(
        DelaySetting(
            name="piece_0.6to0.15",
            sampler=piecewise_short_to_long,
            meta=dict(type="piecewise", switch_t=switch_t, p1=p_short, p2=p_long),
        )
    )

    return settings
