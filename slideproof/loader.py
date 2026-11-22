"""Load a .pptx into a DeckModel with absolute-coordinate geometry."""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.text import MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn
from pptx.shapes.group import GroupShape

from slideproof.model import DeckModel, Element, ImageInfo, RunStyle, SlideModel
from slideproof.units import Rect, rotated_aabb

MAX_SLIDES = 100
_TITLES = (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
_FILLED = (MSO_FILL.SOLID, MSO_FILL.GRADIENT, MSO_FILL.PATTERNED, MSO_FILL.PICTURE)


class DeckError(Exception):
    """Raised with a user-facing message when a deck cannot be loaded."""


def load_deck(path: Path) -> DeckModel:
    path = Path(path)
    try:
        prs = Presentation(str(path))
    except Exception as exc:
        raise DeckError("This file could not be opened as a PowerPoint presentation.") from exc
    slides = list(prs.slides)
    if len(slides) > MAX_SLIDES:
        raise DeckError(
            f"This presentation has more than {MAX_SLIDES} slides; the limit is {MAX_SLIDES}.")
    deck = DeckModel(path=path, slide_w=int(prs.slide_width), slide_h=int(prs.slide_height),
                     theme_fonts=_theme_fonts(prs))
    for i, slide in enumerate(slides, start=1):
        deck.slides.append(_load_slide(slide, i))
    return deck


def _theme_fonts(prs) -> set[str]:
    """Latin typefaces of the first master's theme (heading and body fonts)."""
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    try:
        theme = prs.slide_masters[0].part.part_related_by(RT.THEME)
        root = etree.fromstring(theme.blob)
    except Exception:
        return set()
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    return {el.get("typeface") for el in root.iterfind(".//a:fontScheme/*/a:latin", ns)
            if el.get("typeface")}


def _load_slide(slide, index: int) -> SlideModel:
    sm = SlideModel(index=index, slide_id=slide.slide_id,
                    hidden=slide._element.get("show") in ("0", "false"), title_text=None)
    _walk(slide.shapes, [], None, sm, [0])
    return sm


def _group_xfrm(group):
    x = group._element.find(qn("p:grpSpPr")).find(qn("a:xfrm"))
    if x is None:
        return None
    off, ext = x.find(qn("a:off")), x.find(qn("a:ext"))
    choff, chext = x.find(qn("a:chOff")), x.find(qn("a:chExt"))
    if off is None or ext is None:
        return None
    ox, oy = int(off.get("x")), int(off.get("y"))
    ew, eh = int(ext.get("cx")), int(ext.get("cy"))
    cx, cy = (int(choff.get("x")), int(choff.get("y"))) if choff is not None else (ox, oy)
    cw, ch = (int(chext.get("cx")), int(chext.get("cy"))) if chext is not None else (ew, eh)
    return ox, oy, ew, eh, cx, cy, cw, ch


def _apply(t, x, y, w, h):
    ox, oy, ew, eh, cx, cy, cw, ch = t
    sx = ew / cw if cw else 1.0
    sy = eh / ch if ch else 1.0
    return (round(ox + (x - cx) * sx), round(oy + (y - cy) * sy), round(w * sx), round(h * sy))


def _walk(shapes, transforms, group_id, sm: SlideModel, counter) -> None:
    """transforms: ancestor group transforms, outermost first."""
    for shape in shapes:
        if isinstance(shape, GroupShape):
            t = _group_xfrm(shape)
            if t is None:
                sm.skipped_shapes.append(shape.name)
                continue
            _walk(shape.shapes, transforms + [t], f"s{sm.slide_id}-sh{shape.shape_id}", sm, counter)
            continue
        try:
            vals = (shape.left, shape.top, shape.width, shape.height)
        except Exception:
            vals = (None,)
        if any(v is None for v in vals):
            sm.skipped_shapes.append(shape.name)
            continue
        x, y, w, h = (int(v) for v in vals)
        for t in reversed(transforms):  # innermost first
            x, y, w, h = _apply(t, x, y, w, h)
        frame = Rect(x, y, w, h)
        try:
            rotation = float(getattr(shape, "rotation", 0.0))
        except Exception:
            rotation = 0.0
        kind, ph_type = _kind(shape)
        image = None
        if kind == "picture":
            try:
                image = _image_info(shape)
            except Exception:  # linked or unreadable image
                kind = "other"
        eid = f"s{sm.slide_id}-sh{shape.shape_id}"
        fixable = shape.shape_id not in sm_ids(sm)
        if not fixable:
            eid = f"{eid}-z{counter[0]}"
        text = None
        runs: list[RunStyle] = []
        paragraphs: list[tuple[int, float | None]] = []
        anchor, insets = "top", _DEFAULT_INSETS
        if getattr(shape, "has_text_frame", False):
            tf = shape.text_frame
            text = tf.text
            runs = [_run_style(r) for p in tf.paragraphs for r in p.runs]
            paragraphs = [(len(p.text), _para_size(p)) for p in tf.paragraphs]
            anchor, insets = _text_layout(tf)
        if kind == "title" and sm.title_text is None:
            sm.title_text = text
        sm.elements.append(Element(
            id=eid, slide_index=sm.index, slide_id=sm.slide_id,
            shape_id=shape.shape_id, name=shape.name, kind=kind, frame=frame,
            bbox=rotated_aabb(frame, rotation), z=counter[0], rotation=rotation,
            filled=kind == "picture" or _is_filled(shape), text=text, runs=runs,
            image=image, placeholder_type=ph_type, group_id=group_id,
            fixable=fixable, outlined=_is_outlined(shape), paragraphs=paragraphs,
            anchor=anchor, insets=insets))
        counter[0] += 1


def sm_ids(sm: SlideModel) -> set[int]:
    return {e.shape_id for e in sm.elements}


def _kind(shape):
    try:
        return _kind_inner(shape)
    except Exception:  # unrecognised shape type, linked picture, ...
        return "other", None


def _kind_inner(shape):
    if shape.is_placeholder:
        pt = shape.placeholder_format.type
        name = pt.name if pt is not None else None
        if pt in _TITLES:
            return "title", name
        if shape._element.tag == qn("p:pic"):
            return "picture", name
        if getattr(shape, "has_table", False):
            return "table", name
        if getattr(shape, "has_chart", False):
            return "chart", name
        return "body", name
    st = shape.shape_type  # may raise: caller treats the shape as "other"
    if st == MSO_SHAPE_TYPE.PICTURE:
        return "picture", None
    if st == MSO_SHAPE_TYPE.TEXT_BOX:
        return "textbox", None
    if st in (MSO_SHAPE_TYPE.AUTO_SHAPE, MSO_SHAPE_TYPE.FREEFORM, MSO_SHAPE_TYPE.LINE):
        return "shape", None
    if st == MSO_SHAPE_TYPE.TABLE:
        return "table", None
    if st == MSO_SHAPE_TYPE.CHART:
        return "chart", None
    return "other", None


_DEFAULT_INSETS = (91440, 45720, 91440, 45720)
_ANCHORS = {MSO_ANCHOR.MIDDLE: "middle", MSO_ANCHOR.BOTTOM: "bottom"}


def _para_size(paragraph) -> float | None:
    for r in paragraph.runs:
        try:
            if r.font.size is not None:
                return float(r.font.size.pt)
        except Exception:
            pass
    return None


def _text_layout(tf) -> tuple[str, tuple[int, int, int, int]]:
    try:
        anchor = _ANCHORS.get(tf.vertical_anchor, "top")
    except Exception:
        anchor = "top"
    try:
        insets = tuple(int(v) if v is not None else d for v, d in zip(
            (tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom), _DEFAULT_INSETS))
    except Exception:
        insets = _DEFAULT_INSETS
    return anchor, insets


def _is_outlined(shape) -> bool:
    try:
        line = shape.line
        return line.fill.type in _FILLED and (line.width or 0) > 0
    except Exception:
        return False


def _is_filled(shape) -> bool:
    try:
        return shape.fill.type in _FILLED
    except Exception:
        return False


def _run_style(run) -> RunStyle:
    f = run.font
    rgb = None
    try:
        if f.color.type == MSO_COLOR_TYPE.RGB:
            c = f.color.rgb
            rgb = (c[0], c[1], c[2])
    except Exception:
        rgb = None
    return RunStyle(font=f.name, size_pt=f.size.pt if f.size is not None else None,
                    bold=f.bold, rgb=rgb)


def _image_info(shape) -> ImageInfo:
    img = shape.image
    descr = shape._element.xpath(".//p:cNvPr")[0].get("descr")
    return ImageInfo(px_w=int(img.size[0]), px_h=int(img.size[1]),
                     crop=(shape.crop_left, shape.crop_top, shape.crop_right, shape.crop_bottom),
                     alt=descr or None, filename=img.filename)
