"""Effective text formatting for a shape, following PowerPoint's inheritance chain.

slide shape → its own list style → layout placeholder → master placeholder → master text styles
(titleStyle for titles, bodyStyle for other placeholders, otherStyle for plain text boxes).
Values: font size per paragraph (with shrink-on-overflow applied), horizontal alignment,
vertical anchor and insets.
"""
from __future__ import annotations

from dataclasses import dataclass

from pptx.oxml.ns import qn

DEFAULT_INSETS = (91440, 45720, 91440, 45720)
_TITLE_TYPES = ("TITLE", "CENTER_TITLE")
_ANCHORS = {"t": "top", "ctr": "middle", "b": "bottom"}
_ALIGN = {"l": "left", "ctr": "center", "r": "right", "just": "left", "dist": "left"}
_INSET_ATTRS = ("lIns", "tIns", "rIns", "bIns")


@dataclass
class TextStyle:
    paragraphs: list[tuple[int, float | None]]
    align: str
    anchor: str
    insets: tuple[int, int, int, int]
    autofit: str | None = None  # "none" | "shrink" | "grow"; None when nothing in the chain says
    wrap: bool = True           # False when the text does not wrap (bodyPr wrap="none")


def _chain(shape) -> list:
    """The shape's txBody/bodyPr owners from most to least specific: slide, layout, master."""
    out = [shape]
    try:
        base = shape._base_placeholder if shape.is_placeholder else None
        while base is not None:
            out.append(base)
            base = getattr(base, "_base_placeholder", None)
    except Exception:
        pass
    return out


def _master_style(shape, ph_type: str | None):
    try:
        master = shape.part.slide_layout.slide_master._element
    except Exception:
        return None
    styles = master.find(qn("p:txStyles"))
    if styles is None:
        return None
    if ph_type is None:
        return styles.find(qn("p:otherStyle"))
    return styles.find(qn("p:titleStyle") if ph_type in _TITLE_TYPES else qn("p:bodyStyle"))


def _lvl(list_style, level: int):
    if list_style is None:
        return None
    return list_style.find(qn(f"a:lvl{level + 1}pPr"))


def _lists(chain, master_style):
    """List-style elements to consult, most specific first."""
    lists = []
    for sh in chain:
        try:
            tb = sh._element.find(qn("p:txBody"))
        except Exception:
            tb = None
        if tb is not None:
            lists.append(tb.find(qn("a:lstStyle")))
    lists.append(master_style)
    return [x for x in lists if x is not None]


def _first(values):
    return next((v for v in values if v is not None), None)


def _para_size(paragraph, lists) -> float | None:
    for r in paragraph.runs:
        try:
            if r.font.size is not None:
                return float(r.font.size.pt)
        except Exception:
            pass
    ppr = paragraph._p.find(qn("a:pPr"))
    candidates = []
    if ppr is not None:
        d = ppr.find(qn("a:defRPr"))
        candidates.append(d.get("sz") if d is not None else None)
    for ls in lists:
        lvl = _lvl(ls, paragraph.level)
        d = lvl.find(qn("a:defRPr")) if lvl is not None else None
        candidates.append(d.get("sz") if d is not None else None)
    sz = _first(candidates)
    return int(sz) / 100 if sz is not None else None


def _para_align(paragraph, lists) -> str | None:
    ppr = paragraph._p.find(qn("a:pPr"))
    values = [ppr.get("algn") if ppr is not None else None]
    values += [(_lvl(ls, paragraph.level).get("algn") if _lvl(ls, paragraph.level) is not None else None)
               for ls in lists]
    return _first(values)


def _body_prs(chain):
    out = []
    for sh in chain:
        try:
            tb = sh._element.find(qn("p:txBody"))
            if tb is not None and tb.find(qn("a:bodyPr")) is not None:
                out.append(tb.find(qn("a:bodyPr")))
        except Exception:
            pass
    return out


_AUTOFIT = {"a:noAutofit": "none", "a:normAutofit": "shrink", "a:spAutoFit": "grow"}


def _autofit(body_prs) -> str | None:
    """The first autofit setting along the slide -> layout -> master chain."""
    for bp in body_prs:
        for tag, value in _AUTOFIT.items():
            if bp.find(qn(tag)) is not None:
                return value
    return None


def _font_scale(body_prs) -> float:
    for bp in body_prs[:1]:  # shrink-on-overflow is stored on the slide's own shape
        fit = bp.find(qn("a:normAutofit"))
        if fit is not None and fit.get("fontScale"):
            return int(fit.get("fontScale")) / 100000
    return 1.0


def resolve(shape, ph_type: str | None) -> TextStyle:
    tf = shape.text_frame
    chain = _chain(shape)
    lists = _lists(chain, _master_style(shape, ph_type))
    bps = _body_prs(chain)
    scale = _font_scale(bps)
    paragraphs = []
    aligns = []
    for p in tf.paragraphs:
        size = _para_size(p, lists)
        paragraphs.append((len(p.text), round(size * scale, 2) if size is not None else None))
        aligns.append(_para_align(p, lists))
    anchor = _ANCHORS.get(_first(bp.get("anchor") for bp in bps), "top")
    insets = tuple(int(_first(bp.get(a) for bp in bps) or d)
                   for a, d in zip(_INSET_ATTRS, DEFAULT_INSETS))
    align = _ALIGN.get(_first(aligns) or "l", "left")
    wrap = _first(bp.get("wrap") for bp in bps) != "none"
    return TextStyle(paragraphs, align, anchor, insets, _autofit(bps), wrap)
