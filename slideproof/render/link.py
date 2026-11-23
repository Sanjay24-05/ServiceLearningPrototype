"""Link rendered text spans to the deck's text elements (spec §6 step 4)."""
from __future__ import annotations

from slideproof.render.pdf import RenderedSpan

_TEXT_KINDS = ("title", "body", "textbox", "shape")
_TOL = 91440  # 0.1 in


def _norm(t: str) -> str:
    return " ".join(t.split())


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
            hits = [e for e, et in cands if t in et]
            if not hits:
                continue
            px, py = sp.bbox.x, sp.bbox.y + sp.bbox.h / 2
            inside = [e for e in hits
                      if e.bbox.x - _TOL <= px <= e.bbox.right + _TOL
                      and e.bbox.y - _TOL <= py <= e.bbox.bottom + _TOL]
            best = max(inside or hits, key=lambda e: e.z)
            linked.setdefault(best.id, []).append(sp)
    return linked
