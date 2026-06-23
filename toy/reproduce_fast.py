#!/usr/bin/env python3
"""Run and validate the fast Toy experiment."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    run([sys.executable, "main.py", "--mode", "fast"])
    run([sys.executable, "self_check.py", "--mode", "fast"])
