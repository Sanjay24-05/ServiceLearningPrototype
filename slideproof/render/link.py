"""Link rendered text spans to the deck's text elements (spec §6 step 4)."""
from __future__ import annotations

import re
from math import hypot

from slideproof.render.pdf import RenderedSpan

# "shape" is included so shape text can be linked (used by C3/C7) even though
# content_box does not use rendered spans for shapes.
_TEXT_KINDS = ("title", "body", "textbox", "shape")
_TOL = 91440       # 0.1 in: a start point this close to a box counts as inside
_MAX_DIST = 1371600  # 1.5 in: farther than this from every match, leave unlinked


def _norm(t: str) -> str:
    return " ".join(t.split())


def _dist(e, px: float, py: float) -> float:
    b = e.bbox
    return hypot(max(b.x - px, 0, px - b.right), max(b.y - py, 0, py - b.bottom))


def _best_tier(t: str, cands):
    exact = [e for e, et in cands if et == t]
    if exact:
        return exact
    word = re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)")
    words = [e for e, et in cands if word.search(et)]
    if words:
        return words
    return [e for e, et in cands if t in et]


def link_spans(deck, render) -> dict[str, list[RenderedSpan]]:
    linked: dict[str, list[RenderedSpan]] = {}
    if render is None or render.status != "ok":
        return linked
    for slide, rs in zip(deck.slides, render.slides):
        if rs is None:
            continue
        cands = [(e, _norm(e.text)) for e in slide.elements
                 if e.kind in _TEXT_KINDS and e.text and e.text.strip()]
        for sp in rs.spans:
            t = _norm(sp.text)
            if not t:
                continue
            hits = _best_tier(t, cands)
            if not hits:
                continue
            px, py = sp.bbox.x, sp.bbox.y + sp.bbox.h / 2
            if len(t) < 3 or not any(c.isalnum() for c in t):
                hits = [e for e in hits if _dist(e, px, py) == 0]
                if not hits:
                    continue
            scored = [(0.0 if d <= _TOL else d, e) for e in hits for d in [_dist(e, px, py)]]
            d, best = min(scored, key=lambda s: (s[0], -s[1].z))
            if d > _MAX_DIST:
                continue
            linked.setdefault(best.id, []).append(sp)
    return linked
