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
