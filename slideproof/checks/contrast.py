"""C7: rendered text too close in colour to what is behind it (spec §7.1, WCAG 2 contrast)."""
from __future__ import annotations

from math import ceil, floor

import numpy as np
from PIL import Image

from slideproof.findings import Finding

_BG_DISTANCE = 60     # RGB distance from the text colour for a pixel to count as background
_MIN_BG_PIXELS = 20   # fewer background pixels than this: no reliable measurement, skip the span


def _channel(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _luminance(rgb) -> float:
    r, g, b = (_channel(int(c)) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    """WCAG contrast ratio between two RGB colours, 1.0 to 21.0."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _need(span) -> float:
    large = span.size_pt >= 18 or (span.size_pt >= 14 and span.bold)
    return 3 if large else 4.5


def _background(pixels: np.ndarray, sx: float, sy: float, span):
    """Median colour of the pixels in the span's box that are clearly not the text colour."""
    h, w = pixels.shape[:2]
    b = span.bbox
    x0, y0 = max(0, floor(b.x * sx)), max(0, floor(b.y * sy))
    x1, y1 = min(w, ceil(b.right * sx)), min(h, ceil(b.bottom * sy))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = pixels[y0:y1, x0:x1].reshape(-1, 3)
    dist = np.sqrt(((crop - np.asarray(span.rgb, dtype=np.float32)) ** 2).sum(axis=1))
    bg = crop[dist > _BG_DISTANCE]
    if len(bg) < _MIN_BG_PIXELS:
        return None
    return tuple(np.median(bg, axis=0))


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
            out.append(Finding("C7", s.index, s.slide_id, (e.id,), "visible", conf,
                               min(1.0, (need - ratio) / need),
                               {"ratio": round(ratio, 1), "need": need}))
    return out
