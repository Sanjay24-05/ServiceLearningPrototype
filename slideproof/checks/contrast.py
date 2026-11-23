"""C7: rendered text too close in colour to what is behind it (spec §7.1, WCAG 2 contrast)."""
from __future__ import annotations

from math import ceil, floor

import numpy as np
from PIL import Image

from slideproof.checks.content import FURNITURE_PLACEHOLDERS
from slideproof.findings import Finding

_BG_DISTANCE = 60     # RGB distance from the text colour for a pixel to count as background
_MIN_BG_PIXELS = 20   # fewer background pixels than this: measure the ring outside the box instead
_RING_PX = 3          # width of that ring in pixels
_SAME_COLOUR = 10     # ring this close to the text colour: no measurable difference, skip the span


def _channel(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _luminance(rgb) -> float:
    r, g, b = (_channel(round(float(c))) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    """WCAG contrast ratio between two RGB colours, 1.0 to 21.0."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _need(span) -> float:
    large = span.size_pt >= 18 or (span.size_pt >= 14 and span.bold)
    return 3 if large else 4.5


def _distances(pixels: np.ndarray, rgb) -> np.ndarray:
    return np.sqrt(((pixels - np.asarray(rgb, dtype=np.float32)) ** 2).sum(axis=-1))


def _background(pixels: np.ndarray, sx: float, sy: float, span):
    """Colour behind the span: the median of the pixels in its box that are clearly not the
    text colour; for very faint text (too few such pixels) the median of a thin ring just
    outside the box, which glyphs rarely touch. None when nothing measurable is there."""
    h, w = pixels.shape[:2]
    b = span.bbox
    x0, y0 = max(0, floor(b.x * sx)), max(0, floor(b.y * sy))
    x1, y1 = min(w, ceil(b.right * sx)), min(h, ceil(b.bottom * sy))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = pixels[y0:y1, x0:x1].reshape(-1, 3)
    bg = crop[_distances(crop, span.rgb) > _BG_DISTANCE]
    if len(bg) >= _MIN_BG_PIXELS:
        return tuple(np.median(bg, axis=0))
    rx0, ry0 = max(0, x0 - _RING_PX), max(0, y0 - _RING_PX)
    rx1, ry1 = min(w, x1 + _RING_PX), min(h, y1 + _RING_PX)
    outer = pixels[ry0:ry1, rx0:rx1]
    mask = np.ones(outer.shape[:2], dtype=bool)
    mask[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = False
    ring = outer[mask]
    if len(ring) == 0:
        return None
    median = np.median(ring, axis=0)
    if _distances(median, span.rgb) <= _SAME_COLOUR:
        return None
    return tuple(median)


def _over_picture(slide, el, span) -> bool:
    return any(p.kind == "picture" and p.z < el.z and p.bbox.intersect(span.bbox) is not None
               for p in slide.elements)


def check_contrast(deck, render=None) -> list[Finding]:
    if render is None or render.status != "ok":
        return []
    out: list[Finding] = []
    for s, rendered in zip(deck.slides, render.slides):
        if rendered is None:
            continue
        elements = [(e, render.linked.get(e.id)) for e in s.elements]
        elements = [(e, spans) for e, spans in elements if spans]
        if not elements:
            continue
        with Image.open(rendered.png_path) as img:  # once per slide
            pixels = np.asarray(img.convert("RGB"), dtype=np.float32)
        sx, sy = pixels.shape[1] / deck.slide_w, pixels.shape[0] / deck.slide_h
        for e, spans in elements:
            worst = None  # (ratio / need, ratio, need, span)
            for span in spans:
                bg = _background(pixels, sx, sy, span)
                if bg is None:
                    continue
                ratio, need = contrast_ratio(span.rgb, bg), _need(span)
                if ratio < need and (worst is None or ratio / need < worst[0]):
                    worst = (ratio / need, ratio, need, span)
            if worst is None:
                continue
            _, ratio, need, span = worst
            conf = "likely" if _over_picture(s, e, span) else "definite"
            # Footer, date and slide number: real failures, but template furniture the author
            # rarely chose, so they go in the minor list rather than crowd the visible one.
            severity = "minor" if e.placeholder_type in FURNITURE_PLACEHOLDERS else "visible"
            out.append(Finding("C7", s.index, s.slide_id, (e.id,), severity, conf,
                               min(1.0, (need - ratio) / need),
                               {"ratio": floor(ratio * 10) / 10, "need": need}))
    return out
