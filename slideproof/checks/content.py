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

# Slide furniture: placeholders that come with the template rather than the author's content
# (Review Focus 3). C6 skips them; C7 reports them as minor.
FURNITURE_PLACEHOLDERS = ("FOOTER", "DATE", "SLIDE_NUMBER")


def _has_text(el: Element) -> bool:
    return bool(el.text and el.text.strip())


def content_box(el: Element, spans: list | None = None) -> tuple[Rect, str] | None:
    """(rect, confidence) of what the element shows, or None when it shows nothing.

    With rendered text spans, a text element's box is their padded union (definite). For a
    "shrink text on overflow" box the union is kept inside the box: PowerPoint shrinks the text
    to fit, but LibreOffice may not, so rendered text past the box is not really there (the
    same reason C3 skips these boxes)."""
    if spans and el.kind in _TEXT_KINDS and _has_text(el):
        x0 = min(s.bbox.x for s in spans)
        y0 = min(s.bbox.y for s in spans)
        x1 = max(s.bbox.right for s in spans)
        y1 = max(s.bbox.bottom for s in spans)
        rect = Rect(x0 - _PAD, y0 - _PAD, x1 - x0 + 2 * _PAD, y1 - y0 + 2 * _PAD)
        if el.autofit == "shrink":
            rect = rect.intersect(el.bbox) or rect
        return rect, "definite"
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
    if el.align == "center":
        x = f.x + il + (usable_w - text_w) // 2
    elif el.align == "right":
        x = f.x + il + usable_w - text_w
    else:
        x = f.x + il
    if el.anchor == "middle":
        y = f.y + it + (inner_h - text_h) // 2
    elif el.anchor == "bottom":
        y = f.y + it + inner_h - text_h
    else:
        y = f.y + it
    padded = Rect(x - _PAD, y - _PAD, text_w + 2 * _PAD, text_h + 2 * _PAD)
    return padded.intersect(f) or padded
