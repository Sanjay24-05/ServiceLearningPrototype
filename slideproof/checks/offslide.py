"""C1: element extends past the slide edge."""
from __future__ import annotations

from slideproof.findings import Finding, Fix
from slideproof.fixes.geometry import pull_on_slide


def check_offslide(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        lowest_z = min((e.z for e in s.elements), default=None)
        for e in s.elements:
            b = e.bbox
            if b.area <= 0:
                continue
            inter = b.intersect(slide)
            visible = inter.area / b.area if inter else 0.0
            outside = 1 - visible
            if outside <= 0.02 or inter is None:
                continue
            if (e.kind == "picture" and inter.area >= 0.9 * slide.area and e.z == lowest_z):
                continue
            has_text = bool(e.text and e.text.strip())
            severity = "visible" if outside >= 0.10 else "minor"
            if not has_text and e.kind in ("picture", "shape"):
                if visible >= 0.5:
                    continue
                severity = "minor"
            edges = {}
            for name, amount, size in (
                ("left", slide.x - b.x, b.w), ("right", b.right - slide.right, b.w),
                ("top", slide.y - b.y, b.h), ("bottom", b.bottom - slide.bottom, b.h)):
                if amount > 0:
                    edges[name] = amount / size
            fix = None
            if e.group_id is None:
                res = pull_on_slide(e.frame, b, slide, rotated=e.rotation % 360 != 0)
                if res:
                    frame, scaled = res
                    fix = Fix("F1", "safe", e.id, {"frame": frame.as_list(), "scaled": scaled})
            out.append(Finding("C1", s.index, s.slide_id, (e.id,), severity, "definite",
                               outside, {"outside": outside, "edges": edges}, fix))
    return out
