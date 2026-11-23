"""Features and raw candidates for the intent model (spec 5.2-5.3a)."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from slideproof.checks.content import content_box
from slideproof.checks.stray import is_empty_text
from slideproof.units import inches

FEATURES = [
    "is_c1", "is_c2", "magnitude", "edges_touched", "span_w", "span_h", "area_share",
    "has_text", "kind_picture", "kind_shape", "kind_text", "kind_other", "is_placeholder",
    "in_group", "z_rank", "repeats", "same_layout_repeats", "elements_on_slide",
    "rotated", "lower_is_text", "upper_inside_lower",
]

_EDGE = inches(0.05)
_SAME = inches(0.1)
_TEXT_KINDS = ("title", "body", "textbox")


@dataclass
class Candidate:
    check_id: str
    slide_index: int
    element_ids: tuple[str, ...]
    magnitude: float


def _has_text(e) -> bool:
    return bool(e.text and e.text.strip())


def c1_outside(el, slide) -> float:
    """Fraction of the element's box outside the slide (the C1 magnitude the model trains on)."""
    b = el.bbox
    if b.area <= 0:
        return 0.0
    inter = b.intersect(slide)
    return 1 - (inter.area / b.area if inter else 0.0)


def c2_coverage(upper, lower) -> float | None:
    """Share of the lower element's estimated content box covered by the upper's box, or None."""
    lc = content_box(lower)
    if lc is None or lc[0].area <= 0:
        return None
    inter = upper.bbox.intersect(lc[0])
    return inter.area / lc[0].area if inter else None


def raw_candidates(deck) -> list[Candidate]:
    slide = deck.slide_rect
    out: list[Candidate] = []
    for s in deck.slides:
        for e in s.elements:
            b = e.bbox
            if b.area <= 0 or is_empty_text(e):
                continue
            outside = c1_outside(e, slide)
            if outside > 0.02:
                out.append(Candidate("C1", s.index, (e.id,), outside))
        for a, b in combinations(s.elements, 2):
            lower, upper = (a, b) if a.z < b.z else (b, a)
            if not (upper.kind == "picture" or upper.filled):
                continue
            cov = c2_coverage(upper, lower)
            if cov is not None and cov >= 0.05:
                out.append(Candidate("C2", s.index, (upper.id, lower.id), cov))
    return out


def _same_spot(a, b) -> bool:
    fa, fb = a.frame, b.frame
    return (abs(fa.x - fb.x) <= _SAME and abs(fa.y - fb.y) <= _SAME
            and abs(fa.w - fb.w) <= _SAME and abs(fa.h - fb.h) <= _SAME)


def features_for(check_id: str, element_ids, magnitude: float, deck) -> list[float]:
    e = deck.element(element_ids[0])
    home = next(s for s in deck.slides if s.index == e.slide_index)
    slide = deck.slide_rect
    b = e.bbox
    edges = sum([b.x <= slide.x + _EDGE, b.y <= slide.y + _EDGE,
                 b.right >= slide.right - _EDGE, b.bottom >= slide.bottom - _EDGE])
    n = len(home.elements)
    ordered = sorted(home.elements, key=lambda x: x.z)
    z_rank = ordered.index(e) / (n - 1) if n > 1 else 0.0
    repeats = same_layout = 0
    for s in deck.slides:
        if s.index == home.index:
            continue
        if any(o.kind == e.kind and _same_spot(o, e) for o in s.elements):
            repeats += 1
            if s.layout_key == home.layout_key:
                same_layout += 1
    is_c2 = check_id == "C2"
    lower_is_text = upper_inside_lower = 0.0
    if is_c2 and len(element_ids) > 1:
        lower = deck.element(element_ids[1])
        lower_is_text = float(_has_text(lower) and lower.kind in _TEXT_KINDS + ("shape",)
                              and not lower.filled)
        upper_inside_lower = float(lower.bbox.contains(b))
    kind_text = e.kind in _TEXT_KINDS
    kind_picture, kind_shape = e.kind == "picture", e.kind == "shape"
    vec = [
        check_id == "C1", is_c2, magnitude, edges,
        min(2.0, b.w / slide.w), min(2.0, b.h / slide.h), b.area / slide.area,
        _has_text(e), kind_picture, kind_shape, kind_text,
        not (kind_text or kind_picture or kind_shape),
        e.placeholder_type is not None, e.group_id is not None,
        z_rank, repeats, same_layout, n, e.rotation % 360 != 0,
        lower_is_text, upper_inside_lower,
    ]
    return [float(v) for v in vec]
