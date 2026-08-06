"""Compatibility entry point for the Exp4 v2 pipeline."""

from pathlib import Path

from exp4.pipeline import run_pipeline


def run_experiment4(run_context, resume: bool = False):
    return run_pipeline(run_context, Path(__file__).resolve().parent, resume=resume)


__all__ = ["run_experiment4"]
