"""C5: picture shown at too few pixels per inch (spec §7.1 C5)."""
from __future__ import annotations

from slideproof.findings import Finding
from slideproof.units import EMU_PER_INCH

_VISIBLE_DPI = 72
_MINOR_DPI = 110


def effective_dpi(e) -> float | None:
    img = e.image
    if img is None or img.vector or e.frame.w <= 0 or e.frame.h <= 0:
        return None
    cl, ct, cr, cb = img.crop
    return min(img.px_w * (1 - cl - cr) / (e.frame.w / EMU_PER_INCH),
               img.px_h * (1 - ct - cb) / (e.frame.h / EMU_PER_INCH))


def check_resolution(deck, render=None) -> list[Finding]:
    out: list[Finding] = []
    for s in deck.slides:
        for e in s.elements:
            if e.kind != "picture":
                continue
            dpi = effective_dpi(e)
            if dpi is None or dpi >= _MINOR_DPI:
                continue
            severity = "visible" if dpi < _VISIBLE_DPI else "minor"
            out.append(Finding("C5", s.index, s.slide_id, (e.id,), severity, "definite",
                               max(0.0, 1 - dpi / _MINOR_DPI), {"dpi": round(dpi)}))
    return out
