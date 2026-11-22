from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.util import Inches

from slideproof.checks import run_checks
from slideproof.checks.stray import check_stray
from slideproof.describe import describe
from slideproof.loader import load_deck


def _deck(tmp_path, build, layout=6):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[layout])
    build(s)
    p = tmp_path / "s.pptx"; prs.save(p)
    return load_deck(p)


def test_stray_box_c10_with_f4(demo_deck):
    d = load_deck(demo_deck[0])
    fs = [f for f in run_checks(d, None) if "stray-box" in {d.element(i).name for i in f.element_ids}]
    assert [(f.check_id, f.severity) for f in fs] == [("C10", "minor")]
    assert fs[0].fix.kind == "F4" and fs[0].fix.safety == "safe"
    desc = describe(fs[0], d)
    assert desc.headline == "empty text box was left on the slide"
    assert desc.fix_label == "Remove the empty text box. Safe fix."
    assert desc.change_log == "Slide 8: an empty text box was removed."


def test_empty_placeholder_is_minor(tmp_path):
    # Title and Content layout: title filled, body placeholder left empty (Review Focus 2)
    d = _deck(tmp_path, lambda s: setattr(s.shapes.title, "text", "Hello"), layout=1)
    fs = check_stray(d, None)
    assert [(f.severity, f.fix.kind) for f in fs] == [("minor", "F4")]


def test_filled_empty_box_visible_no_fix(tmp_path):
    def build(s):
        tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
        tb.fill.solid()
    fs = check_stray(_deck(tmp_path, build), None)
    assert [(f.severity, f.fix) for f in fs] == [("visible", None)]


def test_offslide_element(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "far", "x": 20, "y": 1, "w": 2, "h": 1,
                              "text": "parked note"}]))
    fs = run_checks(d, None)
    assert [(f.check_id, f.severity, f.measurements["kind"]) for f in fs] == [("C10", "minor", "offslide")]
    assert describe(fs[0], d).headline.endswith("is completely off the slide")


def test_tiny_shape(tmp_path):
    d = _deck(tmp_path, lambda s: s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2), Inches(2),
                                                     Inches(0.02), Inches(0.02)))
    fs = check_stray(d, None)
    assert [(f.severity, f.measurements["kind"], f.fix) for f in fs] == [("minor", "tiny", None)]


def test_line_not_tiny(tmp_path):
    d = _deck(tmp_path, lambda s: s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(1), Inches(3),
                                                         Inches(4), Inches(3)))
    assert check_stray(d, None) == []


def test_c1_leaves_empty_boxes_to_c10(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "t", "x": 12, "y": 1, "w": 3, "h": 1,
                              "text": "  "}]))
    assert [f.check_id for f in run_checks(d, None)] == ["C10"]


def test_empty_title_placeholder_label(tmp_path):
    # Title Only layout with the title left empty.
    prs = Presentation()
    prs.slides.add_slide(next(l for l in prs.slide_layouts if l.name == "Title Only"))
    p = tmp_path / "t.pptx"; prs.save(p)
    d = load_deck(p)
    f = check_stray(d, None)[0]
    # Review issue 7: never offer to delete a title; screen readers navigate by slide titles.
    assert f.fix is None and f.measurements["kind"] == "no_title"
    assert describe(f, d).headline == "this slide has no title"
    assert "Screen readers" in describe(f, d).full


def test_empty_placeholder_with_fill_is_still_minor(tmp_path):
    # Empty placeholders are not shown in a slideshow, whatever their fill.
    def build(s):
        s.shapes.title.text = "Hello"
        body = s.placeholders[1]
        body.fill.solid()
    d = _deck(tmp_path, build, layout=1)
    assert [(f.severity, f.fix.kind) for f in check_stray(d, None)] == [("minor", "F4")]


def test_empty_picture_placeholder_labelled_by_type(tmp_path):
    # Review issue 7: an empty picture placeholder is not a "text box".
    prs = Presentation()
    s = prs.slides.add_slide(next(l for l in prs.slide_layouts if l.name == "Picture with Caption"))
    s.shapes.title.text = "Our garden"
    s.placeholders[2].text = "A caption"
    p = tmp_path / "pic.pptx"; prs.save(p)
    d = load_deck(p)
    fs = check_stray(d, None)
    assert len(fs) == 1
    desc = describe(fs[0], d)
    assert desc.headline == "empty picture placeholder was left on the slide"
    assert desc.fix_label == "Remove the empty picture placeholder. Safe fix."
    assert desc.change_log == "Slide 1: an empty picture placeholder was removed."


def test_animated_empty_box_gets_no_fix(tmp_path):
    # Review issue 8: deleting an animated shape would leave a dangling animation target.
    from lxml import etree

    def build(s):
        s.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1))
    ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    timing = etree.fromstring(
        f'<p:timing xmlns:p="{ns}"><p:tnLst><p:par><p:cTn id="1"><p:childTnLst><p:par><p:cTn id="2">'
        f'<p:childTnLst><p:set><p:cBhvr><p:cTn id="3"/><p:tgtEl><p:spTgt spid="{tb.shape_id}"/>'
        f'</p:tgtEl></p:cBhvr></p:set></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>'
        f'</p:tnLst></p:timing>')
    s._element.append(timing)
    p = tmp_path / "anim.pptx"; prs.save(p)
    d = load_deck(p)
    assert d.slides[0].elements[0].animated is True
    fs = check_stray(d, None)
    assert [(f.measurements["kind"], f.fix) for f in fs] == [("empty", None)]
