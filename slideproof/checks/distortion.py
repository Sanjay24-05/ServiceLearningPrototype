"""C4: picture displayed with a different aspect ratio than its pixels."""
from __future__ import annotations

from slideproof.findings import Finding, Fix
from slideproof.fixes.geometry import pull_on_slide, restore_proportions
from slideproof.units import rotated_aabb


def check_distortion(deck, render=None) -> list[Finding]:
    slide = deck.slide_rect
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            if e.kind != "picture" or e.image is None or e.frame.h <= 0:
                continue
            im = e.image
            cl, ct, cr, cb = im.crop
            w_px, h_px = im.px_w * (1 - cl - cr), im.px_h * (1 - ct - cb)
            if w_px <= 0 or h_px <= 0:
                continue
            native = w_px / h_px
            ratio = (e.frame.w / e.frame.h) / native
            dev = abs(ratio - 1)
            if dev <= 0.05:
                continue
            fix = None
            if e.group_id is None:
                rotated = e.rotation % 360 != 0
                frame = restore_proportions(e.frame, native)
                bbox = rotated_aabb(frame, e.rotation)
                if slide.contains(bbox):
                    final = (frame, False)
                else:
                    final = pull_on_slide(frame, bbox, slide, rotated)
                if final:
                    fix = Fix("F2", "safe", e.id, {"frame": final[0].as_list(), "scaled": final[1]})
            out.append(Finding("C4", s.index, s.slide_id, (e.id,),
                               "visible" if dev > 0.15 else "minor", "definite", min(dev, 1.0),
                               {"ratio": ratio, "direction": "wide" if ratio > 1 else "tall"}, fix))
    return out
