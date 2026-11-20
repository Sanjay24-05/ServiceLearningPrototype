"""Ground-truth loading and matching for the demo deck.

`expected` rows and findings' `slide_index` are both 1-based;
Findings/DeckModel are duck-typed (no imports).
"""
from __future__ import annotations

import json
from pathlib import Path


def load_expected(path, checks: set[str]) -> list[dict]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [r for r in rows if r["check"] in checks]


def _key(slide: int, check: str, names) -> tuple:
    return (slide, check, frozenset(names))


def match(findings, deck, expected):
    """Return (true_positives, false_positives, missed)."""
    remaining: dict[tuple, list] = {}
    for row in expected:
        remaining.setdefault(_key(row["slide"], row["check"], row["shapes"]), []).append(row)
    tp, fp = [], []
    for f in findings:
        names = [deck.element(eid).name for eid in f.element_ids]
        # both slide numbers are 1-based
        k = _key(f.slide_index, f.check_id, names)
        if remaining.get(k):
            remaining[k].pop()
            tp.append(f)
        else:
            fp.append(f)
    missed = [r for rows in remaining.values() for r in rows]
    return tp, fp, missed
