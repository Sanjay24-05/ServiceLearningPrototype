"""C2: an object covers another object's content (spec §7.1 C2, exemptions §7.2).

The pair iteration, exemptions and opaque coverage are shared with C11 (checks/hidden.py)."""
from __future__ import annotations

from itertools import combinations

from slideproof.checks.content import content_box
from slideproof.findings import Finding

_TEXT_KINDS = ("title", "body", "textbox", "shape")
_MIN_COVER = 0.05
HIDDEN_COVER = 0.95


def _has_text(e) -> bool:
    return bool(e.text and e.text.strip())


def _is_background(e, s, slide) -> bool:
    lowest = min(x.z for x in s.elements)
    inter = e.bbox.intersect(slide)
    return e.kind == "picture" and e.z == lowest and inter is not None and inter.area >= 0.9 * slide.area


def overlap_pairs(deck):
    """(slide, lower, upper) for every pair on every slide that is not exempt (spec §7.2):
    members of one group, a background picture as the lower element, and a label sitting
    inside the thing it labels. Shared by C2 and C11."""
    slide = deck.slide_rect
    for s in deck.slides:
        for a, b in combinations(s.elements, 2):
            lower, upper = (a, b) if a.z < b.z else (b, a)
            if lower.group_id is not None and lower.group_id == upper.group_id:
                continue
            if _is_background(lower, s, slide):
                continue
            # A label sitting fully inside the thing it labels (caption on a photo, text on a shape).
            if _has_text(upper) and lower.bbox.contains(upper.bbox) and (
                    not upper.filled or lower.kind == "picture"):
                continue
            yield s, lower, upper


def _lower_content(lower, render):
    """(rect, confidence) of the lower element's content box, or None when covering it doesn't
    matter. A plain shape without text is decoration (icons, badges, frames)."""
    if lower.kind == "shape" and not _has_text(lower):
        return None
    return content_box(lower, render.linked.get(lower.id) if render else None)


def opaque_cover(lower, upper, render=None) -> tuple[float, str] | None:
    """(coverage, confidence) when an opaque upper element (a picture or filled) covers the
    lower element's content box, or None."""
    if not is_opaque(upper):
        return None
    lc = _lower_content(lower, render)
    if lc is None or lc[0].area <= 0:
        return None
    inter = upper.bbox.intersect(lc[0])
    if inter is None:
        return None
    return inter.area / lc[0].area, lc[1]


def hidden_coverage(lower, upper, render=None) -> float | None:
    """The coverage when the lower element is hidden (C11, >= 95% covered), otherwise None.
    C2 skips exactly these pairs, so a pair is never reported twice."""
    oc = opaque_cover(lower, upper, render)
    return oc[0] if oc is not None and oc[0] >= HIDDEN_COVER else None


def hidden_ids(deck, render=None) -> set[str]:
    """Ids of the elements C11 reports as hidden. C3, C6 and C7 skip them: text nobody can
    see is reported once, as hidden, not also for its overflow, size or contrast."""
    return {lower.id for _, lower, upper in overlap_pairs(deck)
            if hidden_coverage(lower, upper, render) is not None}


def is_opaque(e) -> bool:
    """A picture or a filled shape: what is under it does not show through."""
    return e.kind == "picture" or bool(e.filled)


def check_overlap(deck, render=None) -> list[Finding]:
    out: list[Finding] = []
    for s, lower, upper in overlap_pairs(deck):
        if hidden_coverage(lower, upper, render) is not None:
            continue
        finding = _pair(lower, upper, render)
        if finding:
            cov, conf, lower_is_text = finding
            out.append(Finding("C2", s.index, s.slide_id, (upper.id, lower.id), "visible",
                               conf, cov, {"coverage": cov, "lower_is_text": lower_is_text}))
    return out


def _pair(lower, upper, render=None):
    # Only covering something that shows content matters: text or a picture (or a table/chart).
    lower_is_text = _has_text(lower) and lower.kind in _TEXT_KINDS and not lower.filled
    upper_is_text = _has_text(upper) and upper.kind in _TEXT_KINDS and not upper.filled
    if is_opaque(upper):
        oc = opaque_cover(lower, upper, render)
        if oc is None:
            return None
        cov, conf = oc
    elif upper_is_text and lower_is_text:
        lc = _lower_content(lower, render)
        uc = content_box(upper, render.linked.get(upper.id) if render else None)
        if lc is None or uc is None:
            return None
        inter = uc[0].intersect(lc[0])
        if inter is None:
            return None
        cov = inter.area / min(uc[0].area, lc[0].area)
        conf = "likely" if "likely" in (lc[1], uc[1]) else "definite"
    else:
        return None
    if cov < _MIN_COVER:
        return None
    return cov, conf, lower_is_text
