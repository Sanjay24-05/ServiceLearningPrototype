"""A spoken map of one slide: every object in reading order, with location and size (spec §8.2)."""
from __future__ import annotations

from slideproof.describe.copy import cap
from slideproof.describe.coverage import plural
from slideproof.describe.names import element_label
from slideproof.describe.spatial import grid_location

_ROW_BAND = 0.10  # objects whose centres are within 10% of the slide height share a row


def _size(area_share: float) -> str:
    if area_share < 0.05:
        return "small"
    if area_share < 0.25:
        return "medium"
    if area_share < 0.60:
        return "large"
    return "covers most of the slide"


def slide_map(slide, deck) -> list[str]:
    rect = deck.slide_rect
    band = _ROW_BAND * rect.h

    def key(e):
        cx, cy = e.bbox.center
        return (int(cy // band), cx)

    lines = []
    for e in sorted(slide.elements, key=key):
        label = cap(element_label(e, slide))
        if e.bbox.intersect(rect) is None and not rect.contains(e.bbox):
            b = e.bbox
            if b.right < rect.x or b.x > rect.right or b.bottom < rect.y or b.y > rect.bottom:
                lines.append(f"{label}, off the slide")
                continue
        share = e.bbox.area / rect.area if rect.area else 0
        lines.append(f"{label}, {grid_location(e.bbox, rect)}, {_size(share)}")
    if slide.skipped_shapes:
        n = len(slide.skipped_shapes)
        lines.append(f"{plural(n, 'other object')} that could not be read")
    return lines
