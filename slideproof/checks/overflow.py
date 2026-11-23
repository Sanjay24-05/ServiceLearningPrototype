"""C3: rendered text runs past the bottom or right of its box (spec §7.1)."""
from __future__ import annotations

from slideproof.findings import Finding

_TOLERANCE = 91440  # 0.1 in: smaller overflows are font-substitution noise (Review Focus 1)


def check_overflow(deck, render=None) -> list[Finding]:
    if render is None or render.status != "ok":
        return []
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            spans = render.linked.get(e.id)
            if not spans or e.rotation % 360:
                continue  # rotated frames are not axis-aligned with the rendered spans
            f = e.frame
            if f.w <= 0 or f.h <= 0:
                continue
            below = max(x.bbox.bottom for x in spans) - f.bottom
            right = max(x.bbox.right for x in spans) - f.right
            if max(below, right) <= _TOLERANCE:
                continue
            if below >= right:
                edge, amount = "bottom", below / f.h
            else:
                edge, amount = "right", right / f.w
            out.append(Finding("C3", s.index, s.slide_id, (e.id,), "visible", "likely",
                               min(1.0, amount), {"edge": edge, "amount": amount}))
    return out
