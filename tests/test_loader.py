import pytest
from pptx import Presentation

from slideproof.loader import DeckError, load_deck
from slideproof.units import inches

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def test_demo_deck_basic_model(demo_deck):
    d = load_deck(demo_deck[0])
    assert (d.slide_w, d.slide_h) == (12192000, 6858000) and len(d.slides) == 8
    agenda = next(e for e in d.slides[1].elements if e.name == "agenda-box")
    assert agenda.kind == "textbox" and agenda.frame.x == inches(10.13)
    assert agenda.id == f"s{d.slides[1].slide_id}-sh{agenda.shape_id}"


def test_picture_info_and_alt(demo_deck):
    d = load_deck(demo_deck[0])
    photo = next(e for e in d.slides[3].elements if e.name == "team-photo")
    assert photo.kind == "picture" and photo.filled
    assert (photo.image.px_w, photo.image.px_h) == (800, 600)
    assert photo.image.alt == "Team photo"


def test_title_placeholder_inherits_geometry(demo_deck):
    d = load_deck(demo_deck[0])
    title = next(e for e in d.slides[1].elements if e.kind == "title")
    assert title.frame.w > 0 and d.slides[1].title_text == "Agenda"


def test_background_is_lowest_z(demo_deck):
    s8 = load_deck(demo_deck[0]).slides[7]
    assert min(s8.elements, key=lambda e: e.z).name == "background"


def test_rotated_shape_bbox(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "r", "x": 1, "y": 1, "w": 4, "h": 2,
                              "text": "x", "rotation": 90}]))
    e = d.slides[0].elements[0]
    assert e.rotation == 90 and (e.bbox.w, e.bbox.h) == (e.frame.h, e.frame.w)


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def test_group_children_absolute_coordinates(tmp_path):
    prs = Presentation()
    g = _blank(prs).shapes.add_group_shape()
    g.shapes.add_textbox(0, 0, inches(1), inches(1)).name = "kid"
    # move the group to (2in, 1in); child space stays chOff=(0,0), chExt=ext
    xfrm = g._element.grpSpPr.find(A + "xfrm")
    xfrm.find(A + "off").set("x", str(inches(2)))
    xfrm.find(A + "off").set("y", str(inches(1)))
    xfrm.find(A + "chOff").set("x", "0")
    xfrm.find(A + "chOff").set("y", "0")
    for tag, a, b in (("ext", "cx", "cy"), ("chExt", "cx", "cy")):
        xfrm.find(A + tag).set(a, str(inches(1)))
        xfrm.find(A + tag).set(b, str(inches(1)))
    p = tmp_path / "g.pptx"
    prs.save(p)
    d = load_deck(p)
    assert len(d.slides[0].elements) == 1
    kid = d.slides[0].elements[0]
    assert kid.name == "kid" and kid.frame.x == inches(2) and kid.frame.y == inches(1)
    assert kid.group_id.startswith("s")


def test_shape_without_geometry_is_skipped(tmp_path):
    prs = Presentation()
    s = _blank(prs)
    s.shapes.add_textbox(0, 0, inches(1), inches(1)).name = "ok"
    tb = s.shapes.add_textbox(0, 0, inches(1), inches(1))
    tb.name = "nogeo"
    spPr = tb._element.spPr
    spPr.remove(spPr.find(A + "xfrm"))
    p = tmp_path / "n.pptx"
    prs.save(p)
    d = load_deck(p)
    assert "nogeo" in d.slides[0].skipped_shapes
    assert [e.name for e in d.slides[0].elements] == ["ok"]


def test_more_than_100_slides_rejected(tmp_path):
    prs = Presentation()
    for _ in range(101):
        _blank(prs)
    p = tmp_path / "big.pptx"
    prs.save(p)
    with pytest.raises(DeckError, match="more than 100 slides"):
        load_deck(p)


def test_not_a_pptx(tmp_path):
    p = tmp_path / "x.pptx"
    p.write_bytes(b"not a zip")
    with pytest.raises(DeckError, match="could not be opened"):
        load_deck(p)


def test_freeform_and_connector_are_shapes_not_unchecked(tmp_path):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_CONNECTOR
    from pptx.util import Inches
    from slideproof.describe.coverage import unchecked_sentence
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    fb = s.shapes.build_freeform(Inches(1), Inches(1))
    fb.add_line_segments([(Inches(2), Inches(1)), (Inches(2), Inches(2))])
    fb.convert_to_shape()
    s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1), Inches(3), Inches(4), Inches(3))
    p = tmp_path / "f.pptx"
    prs.save(p)
    deck = load_deck(p)
    assert [e.kind for e in deck.slides[0].elements] == ["shape", "shape"]
    assert unchecked_sentence(deck) is None


# ---- M2 Task 1: text layout fields, outline, group transforms ----
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402
from slideproof.units import Rect  # noqa: E402


def _new_blank(tmp_path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = inches(13.333), inches(7.5)
    slide = prs.slides.add_slide(next(l for l in prs.slide_layouts if l.name == "Blank"))
    return prs, slide


def _set_group_xfrm(grp, off, ext, ch_off, ch_ext):
    x = grp._element.grpSpPr.get_or_add_xfrm()
    for tag, (a, b), names in (("off", off, ("x", "y")), ("ext", ext, ("cx", "cy")),
                               ("chOff", ch_off, ("x", "y")), ("chExt", ch_ext, ("cx", "cy"))):
        el = x.find(f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag}")
        el.set(names[0], str(a)); el.set(names[1], str(b))


def test_text_fields_loaded(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "t", "x": 1, "y": 1, "w": 4, "h": 2,
                              "text": "Hello world"}]))
    e = d.slides[0].elements[0]
    assert e.paragraphs and e.paragraphs[0][0] == len("Hello world")
    assert e.anchor == "top" and e.insets == (91440, 45720, 91440, 45720)
    assert e.outlined is False


def test_paragraph_sizes_and_middle_anchor(tmp_path):
    prs, slide = _new_blank(tmp_path)
    tf = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2)).text_frame
    tf.text = "First"
    tf.paragraphs[0].runs[0].font.size = Pt(30)
    tf.add_paragraph().text = "Second line"
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tmp_path / "t.pptx"; prs.save(p)
    e = load_deck(p).slides[0].elements[0]
    assert e.paragraphs == [(5, 30.0), (11, None)]
    assert e.anchor == "middle"


def test_outlined_shape(tmp_path):
    prs, slide = _new_blank(tmp_path)
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(2), Inches(1))
    sh.fill.background()
    sh.line.color.rgb = __import__("pptx.dml.color", fromlist=["RGBColor"]).RGBColor(0, 0, 0)
    sh.line.width = Pt(2)
    p = tmp_path / "o.pptx"; prs.save(p)
    assert load_deck(p).slides[0].elements[0].outlined is True


def test_group_with_child_offset_and_scale(tmp_path):
    prs, slide = _new_blank(tmp_path)
    grp = slide.shapes.add_group_shape()
    grp.shapes.add_textbox(Inches(1), Inches(1), Inches(1), Inches(0.5)).text_frame.text = "c"
    _set_group_xfrm(grp, (inches(2), inches(1)), (inches(4), inches(2)),
                    (inches(1), inches(1)), (inches(2), inches(1)))
    p = tmp_path / "g.pptx"; prs.save(p)
    e = load_deck(p).slides[0].elements[0]
    assert e.frame == Rect(inches(2), inches(1), inches(2), inches(1))


def test_nested_group_composes(tmp_path):
    prs, slide = _new_blank(tmp_path)
    outer = slide.shapes.add_group_shape()
    inner = outer.shapes.add_group_shape()
    inner.shapes.add_textbox(Inches(0), Inches(0), Inches(1), Inches(1)).text_frame.text = "n"
    # inner: identity scale, moves child by +1in x; outer: scale x2, moves by +2in, +1in
    _set_group_xfrm(inner, (inches(1), 0), (inches(1), inches(1)), (0, 0), (inches(1), inches(1)))
    _set_group_xfrm(outer, (inches(2), inches(1)), (inches(4), inches(2)), (0, 0), (inches(2), inches(1)))
    p = tmp_path / "n.pptx"; prs.save(p)
    e = load_deck(p).slides[0].elements[0]
    # child (0,0,1,1) -> inner (1,0,1,1) -> outer x: 2 + 1*2 = 4, y: 1 + 0 = 1, size 2x2
    assert e.frame == Rect(inches(4), inches(1), inches(2), inches(2))
