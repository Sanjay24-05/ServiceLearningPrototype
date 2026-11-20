"""Turn findings into spoken-friendly descriptions."""
from __future__ import annotations

from dataclasses import dataclass

from slideproof.describe.names import element_label
from slideproof.describe.spatial import grid_location, portion_phrase
from slideproof.findings import Finding
from slideproof.units import Rect


@dataclass
class Description:
    headline: str
    short: str
    full: str
    fix_label: str | None
    change_log: str | None


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _slide_of(deck, n: int):
    return next(s for s in deck.slides if s.index == n)


def _fix_label(f: Finding) -> str | None:
    if f.fix is None:
        return None
    if f.fix.kind == "F1":
        if f.fix.params.get("scaled"):
            return "Move it back onto the slide and shrink it to fit. Safe fix."
        return "Move it back onto the slide. Safe fix."
    if f.fix.kind == "F2":
        return "Restore its natural shape, keeping it centred. Safe fix."
    return None


def _change_log(f: Finding, label: str, el) -> str | None:
    if f.fix is None:
        return None
    n = f.slide_index
    if f.fix.kind == "F1":
        extra = " and shrunk to fit" if f.fix.params.get("scaled") else ""
        return f"Slide {n}: {label} moved back onto the slide{extra}."
    if f.fix.kind == "F2":
        new = Rect.from_list(f.fix.params["frame"])
        if new.w != el.frame.w:
            change = "narrower" if new.w < el.frame.w else "wider"
        else:
            change = "taller" if new.h > el.frame.h else "shorter"
        return (f"Slide {n}: {label} restored to its natural shape; "
                f"it is now {change} and still centred.")
    return None


def describe(finding: Finding, deck) -> Description:
    f = finding
    n = f.slide_index
    grouped = "grouped" in f.measurements
    label = loc = None
    el = None
    if not grouped:
        el = deck.element(f.element_ids[0])
        label = element_label(el, _slide_of(deck, f.slide_index))
        loc = grid_location(el.bbox, deck.slide_rect)

    if f.check_id == "C1" and grouped:
        c = f.measurements["grouped"]
        headline = f"{c} objects stick out past the slide edges"
        full = f"{c} objects on this slide stick out past the slide edges. Confidence: definite."
    elif f.check_id == "C4" and grouped:
        c = f.measurements["grouped"]
        headline = f"{c} pictures are stretched out of shape"
        full = f"{c} pictures on this slide are stretched out of shape. Confidence: definite."
    elif f.check_id == "C1":
        edges = f.measurements["edges"]
        names = list(edges)
        edge_txt = " and ".join(names)
        word = "edges" if len(names) > 1 else "edge"
        headline = f"{label} sticks out past the {edge_txt} {word}"
        worst = max(names, key=lambda k: edges[k])
        dim = "width" if worst in ("left", "right") else "height"
        full = (f"{_cap(label)}, {loc}, sticks out past the {edge_txt} {word} of the slide "
                f"by {portion_phrase(edges[worst])} of its {dim}. "
                f"Part of it will be cut off when presented. Confidence: definite.")
    elif f.check_id == "C4":
        ratio = f.measurements["ratio"]
        wide = f.measurements["direction"] == "wide"
        headline = f"{label} is stretched {'wider' if wide else 'taller'} than its natural shape"
        r = ratio if wide else 1 / ratio
        full = (f"{_cap(label)}, {loc}, is shown {r:.1f} times as "
                f"{'wide' if wide else 'tall'} as its natural shape, so it looks distorted. "
                f"Confidence: definite.")
    else:
        raise ValueError(f"no description for check {f.check_id}")

    slide = _slide_of(deck, n)
    prefix = f"Slide {n} (hidden slide)" if slide.hidden else f"Slide {n}"
    return Description(
        headline=headline,
        short=f"{prefix}: {headline}",
        full=full,
        fix_label=_fix_label(f),
        change_log=None if grouped else _change_log(f, label, el),
    )
