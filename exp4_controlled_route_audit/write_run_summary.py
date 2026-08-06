"""Compatibility wrapper for the v2 run summary."""

from pathlib import Path

from exp4.reporting.run_summary import write_run_summary


def run(run_dir: Path) -> None:
    write_run_summary(run_dir)
