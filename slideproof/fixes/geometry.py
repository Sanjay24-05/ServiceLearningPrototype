"""Pure geometry used to compute fix frames."""
from __future__ import annotations

from slideproof.units import Rect, inches


def pull_on_slide(frame: Rect, bbox: Rect, slide: Rect, rotated: bool,
                  margin: int = inches(0.2)) -> tuple[Rect, bool] | None:
    inner = Rect(slide.x + margin, slide.y + margin, slide.w - 2 * margin, slide.h - 2 * margin)
    scaled = False
    if bbox.w > inner.w or bbox.h > inner.h:
        if rotated:
            return None
        s = min(inner.w / bbox.w, inner.h / bbox.h)
        cx, cy = frame.center
        w, h = round(frame.w * s), round(frame.h * s)
        frame = Rect(round(cx - w / 2), round(cy - h / 2), w, h)
        bx, by = bbox.center
        bw, bh = round(bbox.w * s), round(bbox.h * s)
        bbox = Rect(round(bx - bw / 2), round(by - bh / 2), bw, bh)
        scaled = True
    dx = max(inner.x - bbox.x, 0) or min(inner.right - bbox.right, 0)
    dy = max(inner.y - bbox.y, 0) or min(inner.bottom - bbox.bottom, 0)
    return frame.translate(dx, dy), scaled


def restore_proportions(frame: Rect, native_aspect: float) -> Rect:
    cx, cy = frame.center
    if frame.w >= frame.h:
        w, h = frame.w, round(frame.w / native_aspect)
    else:
        w, h = round(frame.h * native_aspect), frame.h
    return Rect(round(cx - w / 2), round(cy - h / 2), w, h)
