"""Unusual constructs must not break a deck, and fixes must not collide."""
from io import BytesIO

import pytest
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn
from pptx.util import Inches

from slideproof.analysis import analyse
from slideproof.checks import run_checks
from slideproof.describe import describe
from slideproof.loader import load_deck

REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


@pytest.fixture(autouse=True)
def _no_soffice(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))


def png(px=(100, 100)):
    b = BytesIO()
    Image.new("RGB", px, (9, 9, 9)).save(b, "PNG")
    b.seek(0)
    return b


def blank():
    prs = Presentation()
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def add_offslide_box(slide, text="agenda one two"):
    tb = slide.shapes.add_textbox(Inches(9), Inches(1), Inches(3), Inches(1))
    tb.text_frame.text = text
    return tb


def run(tmp_path, prs, name="d"):
    p = tmp_path / f"{name}.pptx"
    prs.save(p)
    return analyse(p, tmp_path / ("r_" + name))


def has_c1(a):
    return any(f.check_id == "C1" for f in a.findings)


def test_linked_picture_loads_as_other(tmp_path):
    prs, s = blank()
    pic = s.shapes.add_picture(png(), 0, 0, Inches(2), Inches(2))
    blip = pic._element.find(".//" + qn("a:blip"))
    del blip.attrib[qn("r:embed")]
    blip.set(qn("r:link"), s.part.relate_to("file:///C:/x.png", REL_IMAGE, is_external=True))
    add_offslide_box(s)
    a = run(tmp_path, prs)
    el = next(e for e in a.deck.slides[0].elements if e.name == pic.name)
    assert el.kind == "other" and el.image is None
    assert has_c1(a)


def test_shape_without_geometry_loads(tmp_path):
    prs, s = blank()
    sh = s.shapes.add_shape(1, 0, 0, Inches(1), Inches(1))
    sh._element.spPr.remove(sh._element.spPr.find(qn("a:prstGeom")))
    add_offslide_box(s)
    a = run(tmp_path, prs)
    assert any(e.name == sh.name and e.kind == "other" for e in a.deck.slides[0].elements)
    assert has_c1(a)


def test_unidentifiable_image_blob_loads(tmp_path):
    prs, s = blank()
    pic = s.shapes.add_picture(png(), 0, 0, Inches(2), Inches(2))
    pic.part.related_part(pic._element.blip_rId)._blob = b"\x00garbage" * 10
    add_offslide_box(s)
    a = run(tmp_path, prs)
    el = next(e for e in a.deck.slides[0].elements if e.name == pic.name)
    assert el.kind == "other" and el.image is None
    assert has_c1(a)


def test_hidden_slide_show_false(tmp_path):
    prs, s = blank()
    s._element.set("show", "false")
    p = tmp_path / "h.pptx"
    prs.save(p)
    assert load_deck(p).slides[0].hidden is True


def test_duplicate_shape_ids_get_unique_finding_ids_and_no_fix(tmp_path):
    prs, s = blank()
    t1 = add_offslide_box(s, "one two")
    t2 = s.shapes.add_textbox(Inches(9), Inches(4), Inches(3), Inches(1))
    t2.text_frame.text = "three four"
    t2._element.nvSpPr.cNvPr.set("id", str(t1.shape_id))
    a = run(tmp_path, prs)
    c1 = [f for f in a.findings if f.check_id == "C1"]
    assert len(c1) == 2 and len({f.id for f in c1}) == 2
    assert all(f.id.replace("-", "").isalnum() for f in c1)
    first, second = sorted(c1, key=lambda f: f.element_ids[0].count("-z"))
    assert first.fix is not None and second.fix is None
    assert "-z" in second.element_ids[0]


def test_stretched_and_offslide_picture_gets_only_f2(tiny_deck):
    path = tiny_deck([dict(kind="picture", name="p", x=11, y=1, w=6, h=2, px=(100, 100))])
    deck = load_deck(path)
    fs = run_checks(deck, None)
    c1 = next(f for f in fs if f.check_id == "C1")
    c4 = next(f for f in fs if f.check_id == "C4")
    assert c1.fix is None
    assert c4.fix is not None and c4.fix.kind == "F2"
    fixed = c4.fix.params["frame"]
    assert fixed[0] + fixed[2] <= deck.slide_w  # pulled on-slide by F2 itself


def test_empty_offslide_textbox_is_minor_and_labelled(tiny_deck):
    path = tiny_deck([dict(kind="text", name="t", x=12, y=1, w=3, h=1, text="  ")])
    deck = load_deck(path)
    # Empty boxes belong to C10 (M2): one minor finding, no C1.
    fs = run_checks(deck, None)
    assert [x.check_id for x in fs] == ["C10"]
    f = fs[0]
    assert f.severity == "minor"  # empty unfilled box is invisible: always minor
    assert "empty text box" in describe(f, deck).headline
    assert '""' not in describe(f, deck).headline


def test_empty_textbox_slightly_offslide_is_minor_only(tiny_deck):
    # Not full-width or full-height, so it is no deliberate bleed (spec 7.2).
    path = tiny_deck([dict(kind="text", name="t", x=10, y=1, w=3.6, h=1, text="")])
    fs = run_checks(load_deck(path), None)
    assert [f.severity for f in fs] == ["minor"]


def test_empty_full_width_strip_bleeding_off_not_flagged(tiny_deck):
    path = tiny_deck([dict(kind="text", name="t", x=-0.5, y=1, w=13.5, h=1, text="")])
    # No C1 (deliberate bleed / empty box); C10 still reports the empty box as minor.
    assert [(f.check_id, f.severity) for f in run_checks(load_deck(path), None)] == [("C10", "minor")]


def test_table_and_chart_frames_load(tmp_path):
    prs, s = blank()
    s.shapes.add_table(2, 2, 0, 0, Inches(3), Inches(1))
    cd = CategoryChartData()
    cd.categories = ["a", "b"]
    cd.add_series("s", (1, 2))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(12), 0, Inches(3), Inches(2), cd)
    a = run(tmp_path, prs)
    assert {e.kind for e in a.deck.slides[0].elements} == {"table", "chart"}
