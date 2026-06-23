"""Deprecated compatibility entrypoint.

Experiment 2 no longer treats temporal policy replay as a formal paper endpoint.
Use `python main.py --mode fast|full` to run the logged attribution-sensitivity pipeline.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    print("This compatibility script is deprecated. Run main.py instead.", file=sys.stderr)
    raise SystemExit(2)
