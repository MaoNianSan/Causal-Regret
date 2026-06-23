"""Deprecated compatibility module.

The old archive exposed a GRU attribution implementation that did not estimate a
verifiable decision-time proxy state and introduced a heavyweight optional Torch
runtime. EXP1 now uses the explicit Kalman proxy in ``src.agents.ProxyAgent``.
This module remains only to prevent silent imports of the obsolete implementation.
"""

from __future__ import annotations


class GRUProxy:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "The legacy GRU proxy is retired. Use src.agents.ProxyAgent, which "
            "records a time-averaged decision-time proxy-state error."
        )


KernelProxy = GRUProxy
