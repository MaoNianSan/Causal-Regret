"""Unit tests for the Exp1 main-figure Panel (a) auxiliary column layout.

Verifies that the ``Mean delay`` and ``Conflict rate`` headers and their
numeric rows are drawn at separate positions, right-aligned per column, and
never overlap at render time.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plot_main import MECHANISM_ORDER, _draw_panel_a_columns  # noqa: E402


def _synthetic_panel_a_data() -> pd.DataFrame:
    """Small synthetic Panel (a) frame with the same schema as frozen figure data."""
    rows = []
    for mechanism in MECHANISM_ORDER:
        rows.append(
            {
                "figure_id": "fig_exp1_alignment_transfer",
                "panel_id": "A",
                "mechanism_id": mechanism,
                "series_id": "alignment_budget_rate",
                "estimate": 0.10,
                "ci_lower": 0.09,
                "ci_upper": 0.11,
            }
        )
        rows.append(
            {
                "figure_id": "fig_exp1_alignment_transfer",
                "panel_id": "A",
                "mechanism_id": mechanism,
                "series_id": "generated_mean_delay",
                "estimate": 14.97,
                "ci_lower": 14.9,
                "ci_upper": 15.0,
            }
        )
        rows.append(
            {
                "figure_id": "fig_exp1_alignment_transfer",
                "panel_id": "A",
                "mechanism_id": mechanism,
                "series_id": "ranking_reversal_rate",
                "estimate": 0.55,
                "ci_lower": 0.54,
                "ci_upper": 0.56,
            }
        )
    return pd.DataFrame(rows)


class TestMainFigureHeadersDoNotOverlap(unittest.TestCase):
    """Panel (a) auxiliary column headers and rows must never overlap."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _synthetic_panel_a_data()
        cls.fig, cls.ax = plt.subplots(figsize=(4.4, 3.2))
        cls.ax.set_xlim(0, 0.5)
        cls.ax.set_ylim(-0.6, float(len(MECHANISM_ORDER) - 1) + 0.9)
        y = np.arange(len(MECHANISM_ORDER))[::-1]
        cls.texts = _draw_panel_a_columns(
            cls.ax, cls.data, list(MECHANISM_ORDER), y, 0.70, 0.955
        )
        cls.fig.canvas.draw()
        cls.renderer = cls.fig.canvas.get_renderer()

    @classmethod
    def tearDownClass(cls) -> None:
        plt.close(cls.fig)

    def _box(self, index: int):
        return self.texts[index].get_window_extent(renderer=self.renderer)

    def test_headers_do_not_overlap(self) -> None:
        header1 = self._box(0)
        header2 = self._box(1)
        self.assertLess(
            header1.x1,
            header2.x0,
            f"'Mean delay' right edge {header1.x1} must precede 'Conflict rate' "
            f"left edge {header2.x0}",
        )
        self.assertFalse(header1.overlaps(header2))

    def test_no_pairwise_text_overlap(self) -> None:
        boxes = [self._box(i) for i in range(len(self.texts))]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                self.assertFalse(
                    boxes[i].overlaps(boxes[j]),
                    f"annotation texts {i} and {j} overlap at render time",
                )

    def test_value_columns_right_aligned(self) -> None:
        col1_right = {self._box(i).x1 for i in range(2, len(self.texts), 2)}
        col2_right = {self._box(i).x1 for i in range(3, len(self.texts), 2)}
        self.assertEqual(
            len(col1_right), 1, f"Mean delay column not aligned: {col1_right}"
        )
        self.assertEqual(
            len(col2_right), 1, f"Conflict rate column not aligned: {col2_right}"
        )

    def test_display_names_are_canonical(self) -> None:
        self.assertEqual(self.texts[0].get_text(), "Mean delay")
        self.assertEqual(self.texts[1].get_text(), "Conflict rate")


if __name__ == "__main__":
    unittest.main()
