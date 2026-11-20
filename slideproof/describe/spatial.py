"""Spatial and quantity phrasing for spoken descriptions."""
from __future__ import annotations

from slideproof.units import Rect

_ROWS = ("top", "middle", "bottom")
_COLS = ("left", "centre", "right")


def _third(v: float, lo: float, size: float) -> int:
    return min(2, max(0, int((v - lo) / size * 3)))


def grid_location(rect: Rect, slide: Rect) -> str:
    wide = rect.w >= 0.9 * slide.w
    tall = rect.h >= 0.9 * slide.h
    cx, cy = rect.center
    row = _third(cy, slide.y, slide.h)
    col = _third(cx, slide.x, slide.w)
    if wide and tall:
        return "covering the whole slide"
    if wide:
        return f"across the whole {_ROWS[row]} of the slide"
    if tall:
        return f"down the whole {_COLS[col]} side of the slide"
    if row == 1 and col == 1:
        return "in the centre"
    return f"in the {_ROWS[row]} {_COLS[col]}"


def coverage_phrase(f: float) -> str:
    if f < 0.15:
        return "a small part of"
    if f < 0.30:
        return "about a quarter of"
    if f < 0.40:
        return "about a third of"
    if f < 0.60:
        return "about half of"
    if f <= 0.90:
        return "most of"
    return "all of"


def portion_phrase(f: float) -> str:
    if f < 0.15:
        return "a little"
    if f < 0.25:
        return "about a fifth"
    if f < 0.30:
        return "about a quarter"
    if f < 0.40:
        return "about a third"
    if f < 0.60:
        return "about half"
    if f <= 0.90:
        return "most"
    return "almost all"
