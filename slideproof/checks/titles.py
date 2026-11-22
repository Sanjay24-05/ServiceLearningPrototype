"""C8: a slide title sits in a different place from the rest (spec §7.1 C8), with F3."""
from __future__ import annotations

from slideproof.findings import Finding, Fix

_CLUSTER_TOL = 91440   # 0.1 in
_FLAG_TOL = 137160     # 0.15 in
_MIN_TITLES = 3


def _candidates(deck):
    for s in deck.slides:
        if s.hidden:
            continue
        for e in s.elements:
            if e.kind == "title" and e.placeholder_type == "TITLE" and not e.rotation % 360:
                yield s, e
                break


def _dominant(cands):
    clusters: list[list] = []
    for s, e in cands:
        for c in clusters:
            ref = c[0][1].frame
            if abs(e.frame.x - ref.x) <= _CLUSTER_TOL and abs(e.frame.y - ref.y) <= _CLUSTER_TOL:
                c.append((s, e))
                break
        else:
            clusters.append([(s, e)])
    best = max(clusters, key=len)
    return best[0][1].frame if len(best) * 2 > len(cands) else None


def check_titles(deck, render=None) -> list[Finding]:
    cands = list(_candidates(deck))
    if len(cands) < _MIN_TITLES:
        return []
    dom = _dominant(cands)
    if dom is None:
        return []
    out: list[Finding] = []
    for s, e in cands:
        dx, dy = e.frame.x - dom.x, e.frame.y - dom.y
        if abs(dx) <= _FLAG_TOL and abs(dy) <= _FLAG_TOL:
            continue
        fix = Fix("F3", "safe", e.id, {"frame": dom.as_list()}) if e.fixable and e.group_id is None else None
        out.append(Finding("C8", s.index, s.slide_id, (e.id,), "visible", "definite",
                           min(1.0, max(abs(dx), abs(dy)) / deck.slide_h),
                           {"dx": dx, "dy": dy, "others": len(cands) - 1}, fix))
    return out
