"""Execution tiers for development, pre-formal validation, and formal candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RunModeSettings:
    mode: str
    module_a_seed_count: int
    module_b_replications: int
    bootstrap_replications: int
    promotion_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


RUN_MODES = {
    "fast": RunModeSettings("fast", 3, 10, 0),
    "middle": RunModeSettings("middle", 20, 100, 500),
    "full": RunModeSettings("full", 100, 1000, 2000),
}


def mode_settings(mode: str) -> RunModeSettings:
    try:
        return RUN_MODES[mode]
    except KeyError as exc:
        raise ValueError(f"Unknown run mode: {mode}") from exc
