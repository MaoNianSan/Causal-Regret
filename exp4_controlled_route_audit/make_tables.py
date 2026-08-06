"""Compatibility wrapper for v2 table generation."""

from pathlib import Path

from exp4.reporting.tables import make_tables


def run(run_dir: Path) -> None:
    make_tables(run_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    run(parser.parse_args().run_dir)
