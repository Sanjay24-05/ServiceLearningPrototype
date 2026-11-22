"""C10: empty text boxes, near-invisible leftovers, objects entirely off the slide (spec §7.1 C10)."""
from __future__ import annotations

from slideproof.findings import Finding, Fix

_TEXT_KINDS = ("title", "body", "textbox")
_TINY = 45720  # 0.05 in


def is_empty_text(e) -> bool:
    return e.kind in _TEXT_KINDS and not (e.text and e.text.strip())


def _entirely_outside(b, slide) -> bool:
    # Coordinate test, so zero-width or zero-height lines on the slide don't count as outside.
    return b.right < slide.x or b.x > slide.right or b.bottom < slide.y or b.y > slide.bottom


def check_stray(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            kind = fix = None
            severity = "minor"
            if is_empty_text(e) and e.kind == "title":
                kind = "no_title"  # never offer to delete a title; screen readers navigate by them
            elif is_empty_text(e):
                kind = "empty"
                # Empty placeholders are never shown in a slideshow, whatever their fill.
                if (e.filled or e.outlined) and e.placeholder_type is None:
                    severity = "visible"
                elif e.fixable and e.group_id is None and not e.animated:
                    fix = Fix("F4", "safe", e.id, {})
            elif e.frame.w < _TINY and e.frame.h < _TINY:
                kind = "tiny"
            elif _entirely_outside(e.bbox, slide):
                kind = "offslide_title" if e.kind == "title" else "offslide"
            if kind is None:
                continue
            out.append(Finding("C10", s.index, s.slide_id, (e.id,), severity, "definite",
                               1.0 if severity == "visible" else 0.5, {"kind": kind}, fix))
    return out
