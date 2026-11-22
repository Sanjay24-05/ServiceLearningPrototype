"""Turn findings into spoken-friendly descriptions."""
from __future__ import annotations

from dataclasses import dataclass

from slideproof.describe.copy import COPY, FALLBACK, GROUPED, Ctx
from slideproof.describe.names import element_label
from slideproof.describe.spatial import grid_location
from slideproof.findings import Finding
from slideproof.units import Rect


@dataclass
class Description:
    headline: str
    short: str
    full: str
    fix_label: str | None
    change_log: str | None


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

    if grouped:
        c = f.measurements["grouped"]
        h, fl = GROUPED.get(f.check_id, FALLBACK)
        headline, full = h.format(c=c, conf=f.confidence), fl.format(c=c, conf=f.confidence)
    elif f.check_id in COPY:
        headline, full = COPY[f.check_id](f, Ctx(deck, _slide_of(deck, n), el, label, loc))
    else:
        headline, full = FALLBACK[0], FALLBACK[1].format(conf=f.confidence)

    slide = _slide_of(deck, n)
    prefix = f"Slide {n} (hidden slide)" if slide.hidden else f"Slide {n}"
    return Description(
        headline=headline,
        short=f"{prefix}: {headline}",
        full=full,
        fix_label=_fix_label(f),
        change_log=None if grouped else _change_log(f, label, el),
    )
