"""C4: picture displayed with a different aspect ratio than its pixels."""
from __future__ import annotations

from slideproof.findings import Finding, Fix
from slideproof.fixes.geometry import pull_on_slide, restore_proportions
from slideproof.units import Rect, rotated_aabb


def distortion_of(e) -> tuple[float, float] | None:
    """Return (native_aspect, displayed/native ratio) for a picture, else None."""
    if e.kind != "picture" or e.image is None or e.frame.h <= 0:
        return None
    im = e.image
    cl, ct, cr, cb = im.crop
    w_px, h_px = im.px_w * (1 - cl - cr), im.px_h * (1 - ct - cb)
    if w_px <= 0 or h_px <= 0:
        return None
    native = w_px / h_px
    return native, (e.frame.w / e.frame.h) / native


def f2_fix(e, slide: Rect) -> Fix | None:
    """The F2 fix C4 offers for this element, or None."""
    d = distortion_of(e)
    if d is None or abs(d[1] - 1) <= 0.05 or e.group_id is not None or not e.fixable:
        return None
    rotated = e.rotation % 360 != 0
    frame = restore_proportions(e.frame, d[0])
    bbox = rotated_aabb(frame, e.rotation)
    final = (frame, False) if slide.contains(bbox) else pull_on_slide(frame, bbox, slide, rotated)
    if not final:
        return None
    return Fix("F2", "safe", e.id, {"frame": final[0].as_list(), "scaled": final[1]})


def check_distortion(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            d = distortion_of(e)
            if d is None:
                continue
            ratio = d[1]
            dev = abs(ratio - 1)
            if dev <= 0.05:
                continue
            out.append(Finding("C4", s.index, s.slide_id, (e.id,),
                               "visible" if dev > 0.15 else "minor", "definite", min(dev, 1.0),
                               {"ratio": ratio, "direction": "wide" if ratio > 1 else "tall"},
                               f2_fix(e, slide)))
    return out
