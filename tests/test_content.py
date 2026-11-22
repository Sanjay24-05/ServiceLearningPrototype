from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

from slideproof.checks.content import content_box
from slideproof.loader import load_deck
from slideproof.units import inches


def _el(path, i=0):
    return load_deck(path).slides[0].elements[i]


def test_picture_content_is_bbox(tiny_deck):
    e = _el(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 3, "h": 2}]))
    assert content_box(e) == (e.bbox, "definite")


def test_short_text_content_is_small(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tf = s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3)).text_frame
    tf.text = "Hi"; tf.paragraphs[0].runs[0].font.size = Pt(24)
    p = tmp_path / "s.pptx"; prs.save(p)
    rect, conf = content_box(_el(p))
    assert conf == "likely"
    assert rect.h < inches(0.6) and rect.w < inches(1)


def test_long_text_wraps(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tf = s.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(5)).text_frame
    tf.word_wrap = True
    tf.text = "x" * 120; tf.paragraphs[0].runs[0].font.size = Pt(20)
    p = tmp_path / "l.pptx"; prs.save(p)
    rect, _ = content_box(_el(p))
    assert rect.h >= int(4 * 20 * 1.2 * 12700)


def test_middle_anchor_centres(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tf = s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(4)).text_frame
    tf.text = "Centre me"; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tmp_path / "m.pptx"; prs.save(p)
    e = _el(p)
    rect, _ = content_box(e)
    assert abs(rect.center[1] - e.frame.center[1]) <= 0.01 * e.frame.h


def test_empty_text_has_no_content(tiny_deck):
    assert content_box(_el(tiny_deck([{"kind": "textbox", "name": "e", "x": 1, "y": 1,
                                        "w": 3, "h": 2}]))) is None


def test_unfilled_shape_without_text_has_no_content(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(1), Inches(2), Inches(2))
    sh.fill.background()
    p = tmp_path / "u.pptx"; prs.save(p)
    assert content_box(_el(p)) is None
