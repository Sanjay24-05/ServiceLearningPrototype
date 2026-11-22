"""Plain-language statements about what this version of the tool does and does not check."""
from __future__ import annotations

CHECKS_RUN = ("objects that stick out past the slide edge", "stretched pictures",
              "overlapping objects", "low-resolution pictures", "titles out of line with the rest",
              "stray fonts", "empty or stray objects")
NOT_CHECKED_YET = ("text overflow", "contrast", "text size")

_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
_OPAQUE_KINDS = ("chart", "table", "other")


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """'1 problem' / '2 problems' (never a literal '(s)')."""
    return f"{n} {singular if n == 1 else (plural_form or singular + 's')}"


def _join(items, comma: bool = False) -> str:
    """'a and b', 'a, b and c'; with comma=True 'a, and b' / 'a, b, and c'."""
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + (", and " if comma else " and ") + items[-1]


def checked_sentence() -> str:
    n = len(CHECKS_RUN)
    lead = f"This version checks {_NUMBER_WORDS.get(n, str(n))} thing{'' if n == 1 else 's'}: "
    return (f"{lead}{_join(CHECKS_RUN, comma=True)}. "
            f"{_join(x.capitalize() if i == 0 else x for i, x in enumerate(NOT_CHECKED_YET))} "
            f"{'is' if len(NOT_CHECKED_YET) == 1 else 'are'} not checked yet.")


def unchecked_sentence(deck) -> str | None:
    """Mention objects that were skipped or are opaque (charts, tables, other)."""
    count = 0
    slides: list[int] = []
    for s in deck.slides:
        n = len(s.skipped_shapes) + sum(1 for e in s.elements if e.kind in _OPAQUE_KINDS)
        if n:
            count += n
            slides.append(s.index)
    if not count:
        return None
    word = "slide" if len(slides) == 1 else "slides"
    return (f"Some objects could not be checked: {plural(count, 'object')} "
            f"on {word} {_join(str(i) for i in slides)}.")
