"""C2: an object covers another object's content (spec §7.1 C2, exemptions §7.2)."""
from __future__ import annotations

from itertools import combinations

from slideproof.checks.content import content_box
from slideproof.findings import Finding

_TEXT_KINDS = ("title", "body", "textbox", "shape")
_MIN_COVER = 0.05


def _has_text(e) -> bool:
    return bool(e.text and e.text.strip())


def _is_background(e, s, slide) -> bool:
    lowest = min(x.z for x in s.elements)
    inter = e.bbox.intersect(slide)
    return e.kind == "picture" and e.z == lowest and inter is not None and inter.area >= 0.9 * slide.area


def check_overlap(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        for a, b in combinations(s.elements, 2):
            lower, upper = (a, b) if a.z < b.z else (b, a)
            if lower.group_id is not None and lower.group_id == upper.group_id:
                continue
            if _is_background(lower, s, slide):
                continue
            # A label sitting fully inside the thing it labels (caption on a photo, text on a shape).
            if _has_text(upper) and not upper.filled and lower.bbox.contains(upper.bbox):
                continue
            finding = _pair(lower, upper)
            if finding:
                cov, conf, lower_is_text = finding
                out.append(Finding("C2", s.index, s.slide_id, (upper.id, lower.id), "visible",
                                   conf, cov, {"coverage": cov, "lower_is_text": lower_is_text}))
    return out


def _pair(lower, upper):
    lc = content_box(lower)
    if lc is None:
        return None
    lower_rect, conf = lc
    lower_is_text = _has_text(lower) and lower.kind in _TEXT_KINDS and not lower.filled
    upper_is_text = _has_text(upper) and upper.kind in _TEXT_KINDS and not upper.filled
    if upper.kind == "picture" or upper.filled:
        inter = upper.bbox.intersect(lower_rect)
        if inter is None:
            return None
        cov = inter.area / lower_rect.area
    elif upper_is_text and lower_is_text:
        uc = content_box(upper)
        if uc is None:
            return None
        inter = uc[0].intersect(lower_rect)
        if inter is None:
            return None
        cov = inter.area / min(uc[0].area, lower_rect.area)
        conf = "likely" if "likely" in (conf, uc[1]) else "definite"
    else:
        return None
    if cov < _MIN_COVER:
        return None
    return cov, conf, lower_is_text
