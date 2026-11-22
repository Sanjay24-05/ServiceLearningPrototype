"""Spoken labels for elements."""
from __future__ import annotations

import re

_GENERIC_IMAGE_NAME = re.compile(
    r"^(image\d*\.\w+|picture\s*\d*(\.\w+)?|img[_ ]?\d+\.\w+)$", re.IGNORECASE)


def first_words(text: str, n: int = 6) -> str:
    words = text.split()
    out = " ".join(words[:n])
    return out + "…" if len(words) > n else out


def _has_text(el) -> bool:
    return bool(el.text and el.text.strip())


def element_label(el, slide) -> str:
    kind = el.kind
    if kind == "title":
        return "the title"
    if kind in ("body", "textbox"):
        if not _has_text(el):
            return "empty text box"
        return f'text box "{first_words(el.text or "")}"'
    if kind == "picture":
        alt = (el.image.alt or "").strip() if el.image else ""
        fname = (el.image.filename or "").strip() if el.image else ""
        # Tools often fill alt text with the file name; both count as no name.
        if _GENERIC_IMAGE_NAME.match(alt):
            alt = ""
        if _GENERIC_IMAGE_NAME.match(fname):
            fname = ""
        name = alt or fname
        if name:
            return f'picture "{name}"'
        pics = [e for e in slide.elements if e.kind == "picture"]
        return f"picture {pics.index(el) + 1}"
    if kind == "shape":
        if _has_text(el):
            return f'shape "{first_words(el.text)}"'
        shapes = [e for e in slide.elements if e.kind == "shape" and not _has_text(e)]
        return f"shape {shapes.index(el) + 1}"
    if kind == "table":
        return "table"
    if kind == "chart":
        return "chart"
    return "object"
