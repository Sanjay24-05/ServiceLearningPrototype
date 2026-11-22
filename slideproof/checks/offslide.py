"""C1: element extends past the slide edge."""
from __future__ import annotations

from slideproof.checks.distortion import f2_fix
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
            empty_text = e.kind in ("textbox", "body", "title") and not e.filled
            if not has_text and (e.kind in ("picture", "shape") or empty_text):
                # Deliberate bleed: backgrounds, banners, full-width strips.
                if b.w >= 0.9 * slide.w or b.h >= 0.9 * slide.h:
                    continue
                if empty_text:
                    severity = "minor"  # invisible stray box; C10 covers it in M2
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
                res = pull_on_slide(e.frame, b, slide, rotated=e.rotation % 360 != 0)
                if res:
                    frame, scaled = res
                    fix = Fix("F1", "safe", e.id, {"frame": frame.as_list(), "scaled": scaled})
            out.append(Finding("C1", s.index, s.slide_id, (e.id,), severity, "definite",
                               outside, {"outside": outside, "edges": edges}, fix))
    return out
