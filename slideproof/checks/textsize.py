"""C6: rendered text that is too small to read when projected (spec §7.1)."""
from __future__ import annotations

from math import floor

from slideproof.checks.content import FURNITURE_PLACEHOLDERS as _EXEMPT  # small on purpose
from slideproof.findings import Finding

_BODY_KINDS = ("body", "textbox")
_VISIBLE_PT = 12
_MINOR_PT = 18


def check_textsize(deck, render=None) -> list[Finding]:
    if render is None or render.status != "ok":
        return []
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            spans = render.linked.get(e.id)
            if not spans or e.placeholder_type in _EXEMPT:
                continue
            size = min(x.size_pt for x in spans)
            if size < _VISIBLE_PT:
                severity = "visible"
            elif size < _MINOR_PT and e.kind in _BODY_KINDS:
                severity = "minor"
            else:
                continue
            out.append(Finding("C6", s.index, s.slide_id, (e.id,), severity, "definite",
                               (_MINOR_PT - size) / _MINOR_PT, {"size": floor(size)}))
    return out
