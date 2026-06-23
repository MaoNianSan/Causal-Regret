#!/usr/bin/env python3
"""Safe compatibility placeholder.

This package does not delete experiment artifacts automatically. Remove a mode
directory manually only when you intentionally want to rerun that mode; main.py
also clears its own target mode before creating a new run.
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple

def cleanup_extra_files(project_root: str) -> Tuple[bool, str]:
    root = Path(project_root).resolve()
    if not root.exists():
        return False, f"Project root does not exist: {root}"
    return True, "No automatic cleanup performed; reruns replace only the selected outputs/<mode> directory."

if __name__ == "__main__":
    ok, message = cleanup_extra_files(str(Path(__file__).resolve().parent))
    print(message)
    raise SystemExit(0 if ok else 1)
