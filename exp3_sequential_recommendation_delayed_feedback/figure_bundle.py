"""Write synchronized figure PDF, PNG, source data, and metadata."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import matplotlib.figure
import pandas as pd

from utilities import save_json


FigureSection = Literal["main", "appendix"]


def write_figure_bundle(
    figure: matplotlib.figure.Figure,
    source_data: pd.DataFrame,
    output_dir: Path,
    figure_id: str,
    metadata: dict[str, Any],
    *,
    figure_section: FigureSection = "main",
) -> None:
    """Write one immutable figure bundle under the requested paper section."""
    if figure_section not in {"main", "appendix"}:
        raise ValueError(f"Unsupported figure section: {figure_section}")

    pdf_path = output_dir / "figures" / figure_section / f"{figure_id}.pdf"
    png_path = output_dir / "figures" / figure_section / f"{figure_id}.png"
    data_path = output_dir / "figures" / "data" / f"{figure_id}_data.csv"
    metadata_path = output_dir / "figures" / "metadata" / f"{figure_id}_metadata.json"
    for path in (pdf_path, png_path, data_path, metadata_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=300, bbox_inches="tight")
    source_data.to_csv(data_path, index=False)
    save_json(
        {
            "figure_id": figure_id,
            "figure_section": figure_section,
            "figure_pdf": pdf_path.relative_to(output_dir).as_posix(),
            "figure_png": png_path.relative_to(output_dir).as_posix(),
            "figure_source_data": data_path.relative_to(output_dir).as_posix(),
            **metadata,
        },
        metadata_path,
    )
