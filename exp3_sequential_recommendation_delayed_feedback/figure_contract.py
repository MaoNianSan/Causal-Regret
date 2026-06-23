from __future__ import annotations

from pathlib import Path
from typing import Any
import shutil

import matplotlib.pyplot as plt
import pandas as pd

from utils import save_dataframe, write_json

FIGURE_SIZE = (6.85, 2.75)


def write_figure_bundle(
    fig,
    rows: list[dict[str, Any]],
    output_dir: Path,
    figure_id: str,
    metadata: dict[str, Any],
    run_mode: str,
    paper_result: bool,
    input_data_status: str = "unknown",
) -> None:
    paths = {
        "pdf": output_dir / "figures" / "pdf" / f"{figure_id}.pdf",
        "png": output_dir / "figures" / "png" / f"{figure_id}.png",
        "data": output_dir / "figures" / "data" / f"{figure_id}_data.csv",
        "meta": output_dir / "figures" / "metadata" / f"{figure_id}_metadata.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    figure_size = list(fig.get_size_inches())
    fig.savefig(paths["pdf"], bbox_inches="tight")
    fig.savefig(paths["png"], dpi=600, bbox_inches="tight")
    plt.close(fig)
    save_dataframe(pd.DataFrame(rows), paths["data"])
    payload = {
        "figure_id": figure_id,
        "figure_status": "complete",
        "run_mode": run_mode,
        "paper_result": bool(paper_result),
        "input_data_status": input_data_status,
        "figure_size_in": figure_size,
        "dpi": 600,
        "ci_level": 0.95,
        **metadata,
    }
    write_json(paths["meta"], payload)


def retire_figure_bundle(output_dir: Path, figure_id: str, reason: str) -> None:
    """Move obsolete active figure artifacts into ``legacy`` before rerendering.

    Retired figures remain auditable but cannot be picked up accidentally by the
    active LaTeX-facing figure paths or artifact manifest.
    """
    active = {
        "pdf": output_dir / "figures" / "pdf" / f"{figure_id}.pdf",
        "png": output_dir / "figures" / "png" / f"{figure_id}.png",
        "data": output_dir / "figures" / "data" / f"{figure_id}_data.csv",
        "meta": output_dir / "figures" / "metadata" / f"{figure_id}_metadata.json",
    }
    destination = output_dir / "legacy" / "retired_figures" / reason / figure_id
    for name, source in active.items():
        if not source.exists():
            continue
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / source.name
        if target.exists():
            target.unlink()
        shutil.move(str(source), str(target))
