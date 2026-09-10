"""Presentation-only output layer for CR-EXP-OUTPUT-V1.

The package deliberately reads frozen experiment artifacts and writes only to
an explicit preview destination.  It has no scientific execution entry point.
"""

SPEC_ID = "CR-EXP-OUTPUT-V1"

__all__ = ["SPEC_ID"]


def _apply_house_style() -> None:
    """Apply the publication rcParams at package import time.

    Matplotlib resolves a Text object's font when the text is created, so the
    house style must be in place *before* any figure is built.  Relying on the
    call inside ``write_figure_bundle`` (which runs at save time) leaves every
    figure rendered with the default DejaVu fonts.
    """
    try:
        from .common import configure_matplotlib
    except Exception:
        return
    configure_matplotlib()


_apply_house_style()
