"""C11: an element is (almost) completely hidden behind an opaque one (spec §7.1 C11, §7.2)."""
from __future__ import annotations

from slideproof.checks.overlap import hidden_coverage, overlap_pairs
from slideproof.findings import Finding


def check_hidden(deck, render=None) -> list[Finding]:
    """Uses rendered text spans for the lower element's content box when available,
    otherwise M2's estimate, so it runs with or without rendering."""
    out: list[Finding] = []
    for s, lower, upper in overlap_pairs(deck):
        cov = hidden_coverage(lower, upper, render)
        if cov is not None:
            out.append(Finding("C11", s.index, s.slide_id, (upper.id, lower.id), "visible",
                               "likely", cov, {"coverage": cov}))
    return out
