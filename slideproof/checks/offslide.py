"""C1: element extends past the slide edge."""
from __future__ import annotations

from slideproof.checks.content import _TEXT_KINDS
from slideproof.checks.distortion import f2_fix
from slideproof.checks.stray import is_empty_text
from slideproof.findings import Finding, Fix
from slideproof.fixes.geometry import pull_on_slide
from slideproof.units import Rect


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
            if spans and e.kind in _TEXT_KINDS:
                # Rendered text: judge where the text actually is, not the box around it.
                b = Rect(min(x.bbox.x for x in spans), min(x.bbox.y for x in spans),
                         max(x.bbox.right for x in spans) - min(x.bbox.x for x in spans),
                         max(x.bbox.bottom for x in spans) - min(x.bbox.y for x in spans))
                if b.area <= 0:
                    b = e.bbox
            inter = b.intersect(slide)
            visible = inter.area / b.area if inter else 0.0
            outside = 1 - visible
            if outside <= 0.02 or inter is None:
                continue
            if (e.kind == "picture" and inter.area >= 0.9 * slide.area and e.z == lowest_z):
                continue
            if is_empty_text(e):
                continue  # empty text boxes belong to C10 (stray objects)
            has_text = bool(e.text and e.text.strip())
            severity = "visible" if outside >= 0.10 else "minor"
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
