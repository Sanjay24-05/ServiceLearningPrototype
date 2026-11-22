"""Content boxes: the part of an element that actually shows something (spec §7.1, content-box rule).

M2 estimates where text sits from the file. M3 will replace the estimate with rendered text spans.
"""
from __future__ import annotations

from math import ceil

from slideproof.model import Element
from slideproof.units import EMU_PER_PT, Rect

_TEXT_KINDS = ("title", "body", "textbox")
_DEFAULT_SIZE = 18.0
_GLYPH_EM = 0.5      # average glyph width as a fraction of the font size
_LINE_SPACING = 1.2
_PAD = 45720         # 0.05 in


def _has_text(el: Element) -> bool:
    return bool(el.text and el.text.strip())


def content_box(el: Element) -> tuple[Rect, str] | None:
    """(rect, confidence) of what the element shows, or None when it shows nothing."""
    if el.kind in ("picture", "table", "chart") or (el.filled and not _has_text(el)):
        return el.bbox, "definite"
    if not _has_text(el):
        return None
    if el.rotation % 360:
        return el.bbox, "likely"
    return _estimated_text(el), "likely"


def _estimated_text(el: Element) -> Rect:
    f = el.frame
    il, it, ir, ib = el.insets
    usable_w = max(1, f.w - il - ir)
    inner_h = max(1, f.h - it - ib)
    text_h = 0
    text_w = 0
    for chars, size in el.paragraphs or [(len(el.text), None)]:
        size = size or _DEFAULT_SIZE
        line_w = chars * _GLYPH_EM * size * EMU_PER_PT
        lines = max(1, ceil(line_w / usable_w))
        text_h += lines * size * _LINE_SPACING * EMU_PER_PT
        text_w = max(text_w, min(usable_w, line_w))
    text_h = min(int(text_h), inner_h)
    text_w = int(text_w)
    x = f.x + il
    if el.anchor == "middle":
        y = f.y + it + (inner_h - text_h) // 2
    elif el.anchor == "bottom":
        y = f.y + it + inner_h - text_h
    else:
        y = f.y + it
    padded = Rect(x - _PAD, y - _PAD, text_w + 2 * _PAD, text_h + 2 * _PAD)
    return padded.intersect(f) or padded
