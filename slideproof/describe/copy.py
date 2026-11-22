"""Exact wording for each check: (headline, full) builders and grouped variants (spec §8.1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from slideproof.describe.names import element_label
from slideproof.describe.spatial import coverage_phrase, grid_location, portion_phrase


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


@dataclass
class Ctx:
    deck: object
    slide: object
    el: object       # first element of the finding
    label: str       # lower-case label of el
    loc: str         # grid location of el

    def other(self, element_id: str) -> tuple[str, str]:
        e = self.deck.element(element_id)
        return element_label(e, self.slide), grid_location(e.bbox, self.deck.slide_rect)


def _c1(f, c: Ctx):
    edges = f.measurements["edges"]
    names = list(edges)
    edge_txt = " and ".join(names)
    word = "edges" if len(names) > 1 else "edge"
    worst = max(names, key=lambda k: edges[k])
    dim = "width" if worst in ("left", "right") else "height"
    return (f"{c.label} sticks out past the {edge_txt} {word}",
            f"{cap(c.label)}, {c.loc}, sticks out past the {edge_txt} {word} of the slide "
            f"by {portion_phrase(edges[worst])} of its {dim}. "
            f"Part of it will be cut off when presented. Confidence: definite.")


def _c2(f, c: Ctx):
    lower, lower_loc = c.other(f.element_ids[1])
    cov = coverage_phrase(f.measurements["coverage"])
    tail = ("Your audience may not be able to read the covered text."
            if f.measurements["lower_is_text"]
            else "Your audience may not be able to see the covered part.")
    return (f"{c.label} covers {cov} {lower}",
            f"{cap(c.label)}, {c.loc}, sits on top of {cov} {lower}, {lower_loc}. "
            f"{tail} Confidence: {f.confidence}.")


def _c4(f, c: Ctx):
    ratio = f.measurements["ratio"]
    wide = f.measurements["direction"] == "wide"
    r = ratio if wide else 1 / ratio
    return (f"{c.label} is stretched {'wider' if wide else 'taller'} than its natural shape",
            f"{cap(c.label)}, {c.loc}, is shown {r:.1f} times as "
            f"{'wide' if wide else 'tall'} as its natural shape, so it looks distorted. "
            f"Confidence: definite.")


def _c5(f, c: Ctx):
    dpi = f.measurements["dpi"]
    return (f"{c.label} is low resolution",
            f"{cap(c.label)}, {c.loc}, has about {dpi} pixels per inch at its current size, "
            f"so it will look blurry or blocky when projected. "
            f"Use a larger or sharper version of the image. Confidence: definite.")


def _c10(f, c: Ctx):
    kind = f.measurements["kind"]
    if kind == "empty":
        if f.severity == "visible":
            full = (f"{cap(c.label)}, {c.loc}, has no text but has a fill or outline, "
                    f"so it shows as a blank shape. Confidence: definite.")
        else:
            full = (f"{cap(c.label)}, {c.loc}, is invisible when presenting but gets in the way "
                    f"when you edit the slide. Confidence: definite.")
        return f"{c.label} was left on the slide", full
    if kind == "offslide_title":
        return ("the title is placed off the slide",
                "The title is placed outside the slide, so it is not shown when presenting, but "
                "screen readers still read it. If you did this on purpose, you can ignore this. "
                "Confidence: definite.")
    if kind == "tiny":
        return (f"{c.label} is too small to see",
                f"{cap(c.label)}, {c.loc}, is almost zero in size, so it cannot be seen. "
                f"It is probably left over from editing. Confidence: definite.")
    return (f"{c.label} is completely off the slide",
            f"{cap(c.label)} is entirely outside the slide, so it will not be shown "
            f"when presenting. Confidence: definite.")


def _c8(f, c: Ctx):
    dx, dy = f.measurements["dx"], f.measurements["dy"]
    others = f.measurements["others"]
    if abs(dy) >= abs(dx):
        direction = "lower" if dy > 0 else "higher"
        share = abs(dy) / c.deck.slide_h
    else:
        direction = "further right" if dx > 0 else "further left"
        share = abs(dx) / c.deck.slide_w
    amount = "slightly" if share < 0.03 else "noticeably" if share < 0.10 else "much"
    return (f"the title sits {amount} {direction} than on the other {others} slides",
            f"The title on this slide sits {amount} {direction} than on the other {others} slides, "
            f"so it will seem to jump when the slides change. Confidence: definite.")


def _c9(f, c: Ctx):
    font, main = f.measurements["font"], f.measurements["main_font"]
    return (f"{c.label} uses {font}, a font used almost nowhere else",
            f"{cap(c.label)}, {c.loc}, is set in {font}. The rest of the presentation mainly uses "
            f"{main}, so this text will look out of place. Confidence: definite.")


COPY: dict[str, Callable] = {"C1": _c1, "C2": _c2, "C4": _c4, "C5": _c5, "C8": _c8, "C9": _c9,
                             "C10": _c10}

# (headline, full) for findings grouped by the prioritiser; {c} = count, {conf} = confidence.
GROUPED: dict[str, tuple[str, str]] = {
    "C1": ("{c} objects stick out past the slide edges",
           "{c} objects on this slide stick out past the slide edges. Confidence: definite."),
    "C2": ("{c} objects overlap each other",
           "{c} objects on this slide overlap each other. Confidence: {conf}."),
    "C4": ("{c} pictures are stretched out of shape",
           "{c} pictures on this slide are stretched out of shape. Confidence: definite."),
    "C5": ("{c} pictures are low resolution",
           "{c} pictures on this slide are low resolution. Confidence: definite."),
    "C8": ("{c} titles sit out of line with the rest",
           "{c} titles on this slide sit out of line with the rest. Confidence: definite."),
    "C9": ("{c} text boxes use a font used almost nowhere else",
           "{c} text boxes on this slide use a font that the rest of the presentation hardly uses, "
           "so they will look out of place. Confidence: definite."),
    "C10": ("{c} empty or stray objects",
            "{c} empty or stray objects are on this slide. Confidence: definite."),
}

FALLBACK = ("a layout problem was found",
            "A layout problem was found on this slide. Confidence: {conf}.")
