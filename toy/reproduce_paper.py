#!/usr/bin/env python3
"""Alias for the full Toy reproduction pipeline."""

from reproduce_full import run, ROOT
import sys

if __name__ == "__main__":
    run([sys.executable, "main.py", "--mode", "full"])
    run([sys.executable, "self_check.py", "--mode", "full"])
    run([sys.executable, "analyze_results.py", "--mode", "full"])
