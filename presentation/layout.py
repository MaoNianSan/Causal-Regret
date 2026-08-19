"""Layout-level regression gates for presentation figures.

Measures real rendered bounding boxes with the matplotlib renderer and checks
containment / clearance / collision constraints under the fixed-canvas
contract.  This module is presentation-only and never invokes science code.

Whitelist policy: a small, per-profile set of decorative texts may be
excluded from canvas-containment checks via ``canvas_whitelist`` predicates
(matched on the rendered string).  Every whitelisted pattern must be listed
with a justification in the profile definition below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.text import Text
from matplotlib.transforms import Bbox

# Display-coordinate tolerances (pixels on the Agg canvas).  4px at the
# default 100-dpi canvas is 0.04in: it absorbs glyph-extent rounding at axes
# edges without masking any real clipping/overflow.
CANVAS_TOLERANCE_PX = 4.0
OVERLAP_SHRINK_PX = 0.6


def _renderer(figure: Figure):
    figure.canvas.draw()
    return figure.canvas.get_renderer()


def _extent(artist, renderer) -> Bbox | None:
    try:
        box = artist.get_window_extent(renderer)
    except Exception:  # defensive: a missing extent must never crash rendering
        return None
    return box if box.width > 0 or box.height > 0 else None


def _figure_bbox(figure: Figure, renderer) -> Bbox:
    return figure.get_window_extent(renderer)


def _inside(inner: Bbox, outer: Bbox, tolerance: float = CANVAS_TOLERANCE_PX) -> bool:
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.y0 >= outer.y0 - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.y1 <= outer.y1 + tolerance
    )


def _overlaps(first: Bbox, second: Bbox, shrink: float = OVERLAP_SHRINK_PX) -> bool:
    return first.shrunk(shrink, shrink).overlaps(second.shrunk(shrink, shrink))


def _texts_on_axes(axes: Iterable[Axes]) -> list[tuple[Axes, Text]]:
    pairs: list[tuple[Axes, Text]] = []
    seen: set[int] = set()
    for axis in axes:
        for text in list(axis.texts) + _axis_titles(axis):
            if id(text) not in seen:
                seen.add(id(text))
                pairs.append((axis, text))
    return pairs


def _axis_titles(axis: Axes) -> list[Text]:
    """All rendered titles: matplotlib 3.11 stores ``loc='left'/'right'``
    titles separately from the center ``axis.title`` (each is a Text)."""
    titles: list[Text] = []
    for attribute in ("_left_title", "_right_title"):
        title = getattr(axis, attribute, None)
        if isinstance(title, Text) and title.get_text():
            titles.append(title)
    if isinstance(axis.title, Text) and axis.title.get_text():
        titles.append(axis.title)
    return titles


def _tick_labels(axes: Iterable[Axes]) -> list[Text]:
    labels: list[Text] = []
    for axis in axes:
        labels.extend(axis.get_xticklabels() + axis.get_yticklabels())
        labels.extend(
            axis.get_xticklabels(minor=True) + axis.get_yticklabels(minor=True)
        )
    return labels


def _axis_labels(axes: Iterable[Axes]) -> list[Text]:
    labels: list[Text] = []
    for axis in axes:
        for label in (axis.xaxis.label, axis.yaxis.label):
            if label is not None and label.get_text():
                labels.append(label)
    return labels


def _legends(figure: Figure, axes: Iterable[Axes]) -> list[Legend]:
    legends = list(figure.legends)
    for axis in axes:
        legend = axis.get_legend()
        if legend is not None:
            legends.append(legend)
    return legends


def _check_canvas_containment(
    figure: Figure, renderer, whitelist: Iterable[Callable[[str], bool]]
) -> tuple[bool, str]:
    """All visible annotation/title/label/legend/tick texts stay on canvas.

    Whitelisted (justified) decorations are measured but not failed.
    """
    figure_box = _figure_bbox(figure, renderer)
    offenders: list[str] = []
    for axis in figure.axes:
        for text in list(axis.texts) + _axis_titles(axis):
            if not text.get_text():
                continue
            if any(predicate(text.get_text()) for predicate in whitelist):
                continue
            box = _extent(text, renderer)
            if box is None:
                continue
            if not _inside(box, figure_box):
                offenders.append(
                    f"annotation {text.get_text()!r}: "
                    f"y1={box.y1:.1f} vs canvas {figure_box.y1:.1f}"
                )
        for label in (axis.xaxis.label, axis.yaxis.label):
            if label is None or not label.get_text():
                continue
            box = _extent(label, renderer)
            if box is None:
                continue
            if not _inside(box, figure_box):
                offenders.append(f"axis label {label.get_text()!r}")
    for legend in _legends(figure, figure.axes):
        box = _extent(legend, renderer)
        if box is None:
            continue
        if not _inside(box, figure_box):
            offenders.append("legend bbox outside canvas")
    for tick in _tick_labels(figure.axes):
        if not tick.get_text():
            continue
        box = _extent(tick, renderer)
        if box is None:
            continue
        if not _inside(box, figure_box):
            offenders.append(f"tick label {tick.get_text()!r} outside canvas")
    return (
        not offenders,
        "; ".join(offenders[:6]) if offenders else "all texts on canvas",
    )


def _check_legend_inside_canvas(figure: Figure, renderer) -> tuple[bool, str]:
    figure_box = _figure_bbox(figure, renderer)
    failures: list[str] = []
    for legend in _legends(figure, figure.axes):
        box = _extent(legend, renderer)
        if box is None:
            continue
        if not _inside(box, figure_box):
            failures.append(
                f"legend y0={box.y0:.1f} below canvas y0={figure_box.y0:.1f}"
            )
    return (not failures, "; ".join(failures) if failures else "all legends on canvas")


def _check_title_inside_canvas(figure: Figure, renderer) -> tuple[bool, str]:
    figure_box = _figure_bbox(figure, renderer)
    failures: list[str] = []
    for axis in figure.axes:
        for title in _axis_titles(axis):
            box = _extent(title, renderer)
            if box is None:
                continue
            if not _inside(box, figure_box):
                failures.append(
                    f"title {title.get_text()!r}: y1={box.y1:.1f} vs canvas {figure_box.y1:.1f}"
                )
    return (not failures, "; ".join(failures) if failures else "all titles on canvas")


def _check_axis_label_inside_canvas(figure: Figure, renderer) -> tuple[bool, str]:
    figure_box = _figure_bbox(figure, renderer)
    failures: list[str] = []
    for label in _axis_labels(figure.axes):
        box = _extent(label, renderer)
        if box is None:
            continue
        if not _inside(box, figure_box):
            failures.append(f"axis label {label.get_text()!r} outside canvas")
    return (
        not failures,
        "; ".join(failures) if failures else "all axis labels on canvas",
    )


def _check_legend_xlabel_clearance(figure: Figure, renderer) -> tuple[bool, str]:
    """No figure legend intersects any axes x label."""
    figure_legends = list(figure.legends)
    if not figure_legends:
        return (True, "no figure-level legend")
    xlabels = [
        label
        for label in _axis_labels(figure.axes)
        if label is not None and label.get_text()
    ]
    failures: list[str] = []
    for legend in figure_legends:
        legend_box = _extent(legend, renderer)
        if legend_box is None:
            continue
        for label in xlabels:
            label_box = _extent(label, renderer)
            if label_box is None:
                continue
            if _overlaps(legend_box, label_box):
                failures.append(
                    f"legend overlaps xlabel {label.get_text()!r} "
                    f"(legend y0={legend_box.y0:.1f}, label y1={label_box.y1:.1f})"
                )
    return (
        not failures,
        "; ".join(failures) if failures else "legend clear of every x label",
    )


def _check_cross_panel_title_collision(figure: Figure, renderer) -> tuple[bool, str]:
    titles: list[Text] = []
    for axis in figure.axes:
        titles.extend(_axis_titles(axis))
    boxes = [(title.get_text(), _extent(title, renderer)) for title in titles]
    boxes = [(text, box) for text, box in boxes if box is not None]
    failures: list[str] = []
    for first in range(len(boxes)):
        for second in range(first + 1, len(boxes)):
            text_a, box_a = boxes[first]
            text_b, box_b = boxes[second]
            if _overlaps(box_a, box_b):
                failures.append(f"titles {text_a!r} and {text_b!r} collide")
    return (
        not failures,
        "; ".join(failures) if failures else "no panel-title collisions",
    )


def _check_exp1_mean_delay_vs_title(figure: Figure, renderer) -> tuple[bool, str]:
    """Exp1: the 'Mean delay' column header must not overlap the panel title."""
    header = None
    title = None
    for axis in figure.axes:
        for text in axis.texts:
            if text.get_text().strip() == "Mean delay":
                header = text
        for candidate in _axis_titles(axis):
            if title is None:
                title = candidate
    if header is None:
        return (True, "no Mean delay header present")
    header_box = _extent(header, renderer)
    if header_box is None:
        return (True, "header extent unavailable")
    if title is not None:
        title_box = _extent(title, renderer)
        if title_box is not None and _overlaps(header_box, title_box):
            return (
                False,
                f"Mean delay header overlaps title {title.get_text()!r} "
                f"(header y0={header_box.y0:.1f}, title y1={title_box.y1:.1f})",
            )
    return (True, "Mean delay header clear of panel title")


def _check_no_long_legend_text(figure: Figure) -> tuple[bool, str]:
    """Exp3: legend entries must be short and must not pack two semantics."""
    failures: list[str] = []
    for legend in _legends(figure, figure.axes):
        for text in legend.get_texts():
            value = text.get_text()
            if " / " in value:
                failures.append(f"legend entry packs two semantics: {value!r}")
            if len(value) > 26:
                failures.append(
                    f"legend entry too long ({len(value)} chars): {value!r}"
                )
    return (
        not failures,
        (
            "; ".join(failures)
            if failures
            else "legend entries are short and single-purpose"
        ),
    )


def _check_no_internal_ids_in_labels(figure: Figure) -> tuple[bool, str]:
    """Exp4: no snake_case internal identifiers exposed as paper-facing labels.

    LaTeX math strings (containing ``$``) are exempt because ``_`` there is a
    subscript command, not an internal identifier.
    """
    failures: list[str] = []
    candidates: list[Text] = []
    for axis in figure.axes:
        candidates.extend(list(axis.texts) + _axis_titles(axis))
        candidates.extend(_tick_labels([axis]))
        candidates.extend(_axis_labels([axis]))
    for legend in _legends(figure, figure.axes):
        candidates.extend(legend.get_texts())
    for text in candidates:
        value = text.get_text()
        if not value or "$" in value:
            continue
        if "_" in value:
            failures.append(f"snake_case identifier exposed: {value!r}")
    return (
        not failures,
        "; ".join(failures[:6]) if failures else "no internal identifiers in labels",
    )


@dataclass(frozen=True)
class LayoutProfile:
    gates: tuple[str, ...]
    canvas_whitelist: tuple[Callable[[str], bool], ...] = ()


PROFILES: dict[str, LayoutProfile] = {
    "exp1_main": LayoutProfile(
        gates=(
            "canvas_containment",
            "legend_inside_canvas",
            "title_inside_canvas",
            "axis_label_inside_canvas",
            "exp1_mean_delay_vs_title",
            "cross_panel_title_collision",
        ),
    ),
    "exp2_main": LayoutProfile(
        gates=(
            "canvas_containment",
            "legend_inside_canvas",
            "title_inside_canvas",
            "axis_label_inside_canvas",
            "legend_xlabel_clearance",
            "cross_panel_title_collision",
        ),
    ),
    "exp3_main": LayoutProfile(
        gates=(
            "canvas_containment",
            "legend_inside_canvas",
            "title_inside_canvas",
            "axis_label_inside_canvas",
            "legend_xlabel_clearance",
            "no_long_legend_text",
            "cross_panel_title_collision",
        ),
    ),
    "exp4_main": LayoutProfile(
        gates=(
            "canvas_containment",
            "legend_inside_canvas",
            "title_inside_canvas",
            "axis_label_inside_canvas",
            "no_internal_ids_in_labels",
            "cross_panel_title_collision",
        ),
    ),
    "appendix": LayoutProfile(
        gates=(
            "canvas_containment",
            "legend_inside_canvas",
            "title_inside_canvas",
            "axis_label_inside_canvas",
        ),
    ),
}

_GATE_FUNCTIONS = {
    "canvas_containment": lambda fig, renderer, profile: _check_canvas_containment(
        fig, renderer, profile.canvas_whitelist
    ),
    "legend_inside_canvas": lambda fig, renderer, profile: _check_legend_inside_canvas(
        fig, renderer
    ),
    "title_inside_canvas": lambda fig, renderer, profile: _check_title_inside_canvas(
        fig, renderer
    ),
    "axis_label_inside_canvas": lambda fig, renderer, profile: _check_axis_label_inside_canvas(
        fig, renderer
    ),
    "legend_xlabel_clearance": lambda fig, renderer, profile: _check_legend_xlabel_clearance(
        fig, renderer
    ),
    "cross_panel_title_collision": lambda fig, renderer, profile: _check_cross_panel_title_collision(
        fig, renderer
    ),
    "exp1_mean_delay_vs_title": lambda fig, renderer, profile: _check_exp1_mean_delay_vs_title(
        fig, renderer
    ),
    "no_long_legend_text": lambda fig, renderer, profile: _check_no_long_legend_text(
        fig
    ),
    "no_internal_ids_in_labels": lambda fig, renderer, profile: _check_no_internal_ids_in_labels(
        fig
    ),
}


def run_layout_gates(figure: Figure, profile: str) -> list[dict[str, object]]:
    """Run every gate of a profile on a real canvas draw.

    Returns one result dict per gate: ``{"check", "passed", "details"}``.
    """
    if profile not in PROFILES:
        raise KeyError(
            f"Unknown layout profile {profile!r}; expected {sorted(PROFILES)}"
        )
    spec = PROFILES[profile]
    renderer = _renderer(figure)
    results: list[dict[str, object]] = []
    for gate in spec.gates:
        passed, details = _GATE_FUNCTIONS[gate](figure, renderer, spec)
        results.append(
            {"check": f"layout:{gate}", "passed": bool(passed), "details": str(details)}
        )
    return results


__all__ = ["PROFILES", "run_layout_gates"]
