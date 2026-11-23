"""C3: rendered text runs past the bottom or right of its box (spec §7.1)."""
from __future__ import annotations

from slideproof.checks.content import estimated_text_extent, span_union
from slideproof.checks.overlap import hidden_ids
from slideproof.findings import Finding

_TOLERANCE = 91440  # 0.1 in: smaller overflows are font-substitution noise (Review Focus 1)
_AT_EDGE = 12700    # 1 pt: rendered text this close to the slide edge may be cut off there


def check_overflow(deck, render=None) -> list[Finding]:
    if render is None or render.status != "ok":
        return []
    slide = deck.slide_rect
    hidden = hidden_ids(deck, render)  # reported once, by C11
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            spans = render.linked.get(e.id)
            if not spans or e.id in hidden:
                continue
            if e.rotation % 360:
                continue  # rotated frames are not axis-aligned with the rendered spans
            if e.autofit in ("shrink", "grow"):
                continue  # PowerPoint shrinks the text or grows the box; LibreOffice does not
            f = e.frame
            if f.w <= 0 or f.h <= 0:
                continue
            text = span_union(spans)
            # LibreOffice draws no glyphs off the page: when the rendered text reaches the slide
            # edge and the box goes on past it, the lines beyond are missing, so use the estimate.
            est = None
            if text.bottom >= slide.bottom - _AT_EDGE and f.bottom > slide.bottom:
                est = estimated_text_extent(e)
                below = est.bottom - f.bottom
            else:
                below = text.bottom - f.bottom
            if text.right >= slide.right - _AT_EDGE and f.right > slide.right:
                est = est or estimated_text_extent(e)
                right = est.right - f.right
            else:
                right = text.right - f.right
            if not e.wrap:
                right = 0  # unwrapped text legitimately runs sideways; only its bottom counts
            if max(below, right) <= _TOLERANCE:
                continue
            if below >= right:
                edge, amount = "bottom", below / f.h
            else:
                edge, amount = "right", right / f.w
            out.append(Finding("C3", s.index, s.slide_id, (e.id,), "visible", "likely",
                               min(1.0, amount), {"edge": edge, "amount": amount}))
    return out
