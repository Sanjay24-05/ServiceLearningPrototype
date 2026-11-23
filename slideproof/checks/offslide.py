"""C1: element extends past the slide edge."""
from __future__ import annotations

from slideproof.checks.content import _TEXT_KINDS, span_union
from slideproof.checks.distortion import f2_fix
from slideproof.checks.stray import is_empty_text
from slideproof.findings import Finding, Fix
from slideproof.fixes.geometry import pull_on_slide
from slideproof.units import Rect

_FITS_MARGIN = 91440  # 0.1 in: text this far inside a crossed slide edge is not cut (A6)


def _text_fits(text: Rect, box: Rect, slide: Rect) -> bool:
    """True when the rendered text stays at least 0.1 in inside every slide edge the box crosses."""
    for crossed, gap in ((box.x < slide.x, text.x - slide.x),
                         (box.right > slide.right, slide.right - text.right),
                         (box.y < slide.y, text.y - slide.y),
                         (box.bottom > slide.bottom, slide.bottom - text.bottom)):
        if crossed and gap < _FITS_MARGIN:
            return False
    return True


def check_offslide(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        lowest_z = min((e.z for e in s.elements), default=None)
        for e in s.elements:
            b = e.bbox
            if b.area <= 0:
                continue
            spans = render.linked.get(e.id) if render else None
            text_cut = False
            if spans and e.kind in _TEXT_KINDS:
                # LibreOffice does not draw glyphs off the page, so the rendered spans stop at
                # the slide edge: they can only show that the text fits (A6), never how much is cut.
                if _text_fits(span_union(spans), b, slide):
                    continue
                text_cut = True
            inter = b.intersect(slide)
            visible = inter.area / b.area if inter else 0.0
            outside = 1 - visible
            if outside <= 0.02 or inter is None:
                continue  # nearly all on the slide, or entirely off it (C10, stray objects)
            if (e.kind == "picture" and inter.area >= 0.9 * slide.area and e.z == lowest_z):
                continue
            if is_empty_text(e):
                continue  # empty text boxes belong to C10 (stray objects)
            has_text = bool(e.text and e.text.strip())
            severity = "visible" if outside >= 0.10 or text_cut else "minor"
            if not has_text and e.kind in ("picture", "shape"):
                # Deliberate bleed: backgrounds, banners, full-width strips.
                if b.w >= 0.9 * slide.w or b.h >= 0.9 * slide.h:
                    continue
            edges = {}
            for name, amount, size in (
                ("left", slide.x - b.x, b.w), ("right", b.right - slide.right, b.w),
                ("top", slide.y - b.y, b.h), ("bottom", b.bottom - slide.bottom, b.h)):
                if amount > 0:
                    edges[name] = amount / size
            fix = None
            # C4's F2 already carries the element back on-slide; offering F1
            # as well would overwrite it and get rolled back.
            if e.group_id is None and e.fixable and f2_fix(e, slide) is None:
                res = pull_on_slide(e.frame, e.bbox, slide, rotated=e.rotation % 360 != 0)
                if res:
                    frame, scaled = res
                    fix = Fix("F1", "safe", e.id, {"frame": frame.as_list(), "scaled": scaled})
            out.append(Finding("C1", s.index, s.slide_id, (e.id,), severity, "definite",
                               outside, {"outside": outside, "edges": edges}, fix))
    return out
