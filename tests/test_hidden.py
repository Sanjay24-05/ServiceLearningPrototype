from io import BytesIO

import pytest
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

from slideproof.checks import CHECKS
from slideproof.checks.hidden import check_hidden
from slideproof.checks.overlap import check_overlap
from slideproof.describe import describe
from slideproof.describe.copy import GROUPED
from slideproof.loader import load_deck
from slideproof.units import inches


def _hidden_text_deck(tiny_deck, pic_w=6.0):
    return load_deck(tiny_deck([
        {"kind": "textbox", "name": "notes", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Hidden words"},
        {"kind": "picture", "name": "photo", "x": 0.5, "y": 0.5, "w": pic_w, "h": 2}]))


def _ids(deck):
    return {e.name: e.id for e in deck.slides[0].elements}


def test_text_fully_under_picture_is_hidden(tiny_deck):
    d = _hidden_text_deck(tiny_deck)
    ids = _ids(d)
    fs = check_hidden(d, None)
    assert len(fs) == 1
    f = fs[0]
    assert f.check_id == "C11" and f.severity == "visible" and f.confidence == "likely"
    assert f.element_ids == (ids["photo"], ids["notes"])
    assert f.measurements["coverage"] >= 0.95 and f.fix is None
    assert check_overlap(d, None) == []


def test_partial_cover_stays_c2(tiny_deck):
    d = load_deck(tiny_deck([
        {"kind": "textbox", "name": "notes", "x": 1, "y": 1, "w": 5, "h": 1,
         "text": "Some words that run along the line"},
        {"kind": "picture", "name": "photo", "x": 0.5, "y": 0.5, "w": 1.9, "h": 2}]))
    render = None
    assert check_hidden(d, render) == []
    c2 = check_overlap(d, render)
    assert len(c2) == 1 and 0.05 <= c2[0].measurements["coverage"] < 0.95


def test_rendered_spans_decide_the_content_box(tiny_deck, make_render):
    # The picture covers the estimated text area, but the rendered text sits lower, mostly uncovered.
    d = load_deck(tiny_deck([
        {"kind": "textbox", "name": "notes", "x": 1, "y": 1, "w": 5, "h": 3, "text": "Hidden words"},
        {"kind": "picture", "name": "photo", "x": 0.5, "y": 0.5, "w": 6, "h": 1.2}]))
    assert len(check_hidden(d, None)) == 1
    render = make_render([[("Hidden words", (inches(1.2), inches(3), inches(2), inches(0.4)))]])
    from slideproof.render.link import link_spans
    render.linked = link_spans(d, render)
    assert render.linked
    assert check_hidden(d, render) == []


def test_background_lower_exempt(demo_deck):
    d = load_deck(demo_deck[0])
    assert [f for f in check_hidden(d, None) if f.slide_index == 8] == []


def _png():
    b = BytesIO(); Image.new("RGB", (400, 300), (200, 80, 80)).save(b, "PNG"); b.seek(0); return b


def _deck(tmp_path, build):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    build(s)
    p = tmp_path / "h.pptx"; prs.save(p)
    return load_deck(p)


def _filled(s, x, y, w, h, text=None):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = RGBColor(0x33, 0x66, 0x99)
    if text:
        sh.text_frame.text = text
    return sh


def test_filled_shape_hides_picture(tmp_path):
    def build(s):
        s.shapes.add_picture(_png(), Inches(2), Inches(2), Inches(3), Inches(2))
        _filled(s, 1.5, 1.5, 4, 3)
    d = _deck(tmp_path, build)
    fs = check_hidden(d, None)
    assert [f.check_id for f in fs] == ["C11"]
    assert check_overlap(d, None) == []


def test_plain_shape_under_shape_exempt(tmp_path):
    def build(s):
        _filled(s, 2, 2, 3, 2)
        _filled(s, 1.5, 1.5, 4, 3)
    assert check_hidden(_deck(tmp_path, build), None) == []


def test_grouped_members_exempt(tmp_path):
    def build(s):
        g = s.shapes.add_group_shape()
        g.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3)).text_frame.text = "Label"
        g.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(6), Inches(3))
    assert check_hidden(_deck(tmp_path, build), None) == []


def test_label_inside_picture_exempt(tmp_path):
    # A filled caption bar inside a photo is a label, even if it covers almost all of the photo.
    def build(s):
        s.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(6), Inches(3))
        _filled(s, 1, 1, 6, 2.95, text="Caption")
    d = _deck(tmp_path, build)
    assert check_hidden(d, None) == []


def test_c2_and_c11_never_report_the_same_pair(tiny_deck):
    for w in (1.0, 1.9, 3.0, 4.0, 5.0, 5.6, 6.0):
        d = _hidden_text_deck(tiny_deck, pic_w=w)
        c11 = {f.element_ids for f in check_hidden(d, None)}
        c2 = {f.element_ids for f in check_overlap(d, None)}
        assert not (c11 & c2), w


def test_registered():
    assert check_hidden in CHECKS


def test_copy_c11(tiny_deck):
    d = _hidden_text_deck(tiny_deck)
    item = describe(check_hidden(d, None)[0], d)
    assert item.headline == 'text box "Hidden words" is hidden behind picture 1'
    assert item.full == ('Text box "Hidden words", in the top left, is almost completely covered by '
                         "picture 1, so your audience will not see it. Confidence: likely.")
    assert GROUPED["C11"] == ("{c} objects are hidden behind others",
                              "{c} objects on this slide are hidden behind others. Confidence: {conf}.")
