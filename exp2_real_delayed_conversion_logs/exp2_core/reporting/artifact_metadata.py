from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def save_figure(fig: plt.Figure, base: Path, config: dict[str, Any]) -> list[Path]:
    plots = config["plots"]
    saved: list[Path] = []
    if bool(plots.get("save_pdf", True)):
        path = base.with_suffix(".pdf")
        fig.savefig(path, bbox_inches="tight")
        saved.append(path)
    if bool(plots.get("save_svg", True)):
        path = base.with_suffix(".svg")
        fig.savefig(path, bbox_inches="tight")
        saved.append(path)
    if bool(plots.get("save_png", True)):
        path = base.with_suffix(".png")
        fig.savefig(path, dpi=int(plots.get("dpi", 600)), bbox_inches="tight")
        saved.append(path)
    return saved
