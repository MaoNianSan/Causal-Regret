"""Compatibility wrapper for v2 figure generation."""

from pathlib import Path

from exp4.reporting.figures_appendix import plot_appendix_figures
from exp4.reporting.figures_main import plot_main_figure


def run(run_dir: Path) -> None:
    plot_main_figure(run_dir)
    plot_appendix_figures(run_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    run(parser.parse_args().run_dir)
