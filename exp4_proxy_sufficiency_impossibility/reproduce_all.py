"""Canonical one-command reproduction entry point.

Examples:
    python reproduce_all.py --mode fast
    python reproduce_all.py --mode full --n-jobs 32
"""

from main import main

if __name__ == "__main__":
    main()
