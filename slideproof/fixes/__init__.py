"""Apply fixes to a copy of a deck."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from pptx import Presentation

from slideproof.findings import Fix
from slideproof.fixes.writer import delete_shape, set_frame
from slideproof.units import Rect

FIX_ORDER = ["F4", "F5", "F3", "F2", "F1", "F7", "F6"]
_SUPPORTED = ("F1", "F2", "F3", "F4")
_ID = re.compile(r"^s(\d+)-sh(\d+)$")


def apply_fixes(src: Path, dst: Path, fixes: list[Fix]) -> list[Fix]:
    src, dst = Path(src), Path(dst)
    if src.resolve() == dst.resolve():
        raise ValueError("refusing to overwrite the original deck")
    for f in fixes:
        if f.kind not in _SUPPORTED:
            raise NotImplementedError(f.kind)
    ordered = sorted(fixes, key=lambda f: FIX_ORDER.index(f.kind))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    prs = Presentation(str(dst))
    for f in ordered:
        m = _ID.match(f.element_id)
        if not m:
            raise ValueError(f"bad element id: {f.element_id}")
        slide_id, shape_id = int(m.group(1)), int(m.group(2))
        if f.kind == "F4":
            delete_shape(prs, slide_id, shape_id)
        else:
            set_frame(prs, slide_id, shape_id, Rect.from_list(f.params["frame"]))
    prs.save(str(dst))
    return ordered
