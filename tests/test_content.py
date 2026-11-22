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


# ---- review issue 2: inherited size / alignment / autofit ----
from io import BytesIO  # noqa: E402

from PIL import Image  # noqa: E402

from slideproof.checks.overlap import check_overlap  # noqa: E402


def _png(w=400, h=400):
    b = BytesIO(); Image.new("RGB", (w, h), (200, 60, 60)).save(b, "PNG"); b.seek(0); return b


def test_title_inherits_size_and_centre_alignment(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1]); s.shapes.title.text = "Week 1 results"
    p = tmp_path / "t.pptx"; prs.save(p)
    title = next(e for e in load_deck(p).slides[0].elements if e.kind == "title")
    assert title.paragraphs == [(len("Week 1 results"), 44.0)]
    assert title.align == "center"


def test_body_inherits_size(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1]); s.shapes.title.text = "T"
    s.placeholders[1].text = "One\nTwo"
    p = tmp_path / "b.pptx"; prs.save(p)
    body = next(e for e in load_deck(p).slides[0].elements if e.kind == "body")
    assert [size for _, size in body.paragraphs] == [32.0, 32.0]


def test_autofit_font_scale_applies(tmp_path):
    from pptx.oxml.ns import qn
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    tb.text_frame.text = "Shrunk"; tb.text_frame.paragraphs[0].runs[0].font.size = Pt(40)
    body_pr = tb.text_frame._txBody.find(qn("a:bodyPr"))
    for child in list(body_pr):
        body_pr.remove(child)
    fit = body_pr.makeelement(qn("a:normAutofit"), {"fontScale": "50000"})
    body_pr.append(fit)
    p = tmp_path / "a.pptx"; prs.save(p)
    assert load_deck(p).slides[0].elements[0].paragraphs == [(6, 20.0)]


def test_centred_title_and_corner_logo_no_overlap(tmp_path):
    prs = Presentation()
    for i in range(3):
        s = prs.slides.add_slide(prs.slide_layouts[1]); s.shapes.title.text = f"Week {i} results"
        s.placeholders[1].text = "Point one\nPoint two"
        s.shapes.add_picture(_png(), Inches(0.15), Inches(0.15), Inches(0.9), Inches(0.9))
    p = tmp_path / "k.pptx"; prs.save(p)
    assert check_overlap(load_deck(p), None) == []


def test_picture_over_inherited_size_bullets_found(tmp_path):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1]); s.shapes.title.text = "Results"
    s.placeholders[1].text = "\n".join(f"Bullet {i}: a line of reasonably long text here" for i in range(6))
    s.shapes.add_picture(_png(1600, 1200), Inches(4.5), Inches(4.0), Inches(4.5), Inches(2.6))
    p = tmp_path / "h.pptx"; prs.save(p)
    fs = check_overlap(load_deck(p), None)
    assert len(fs) == 1 and fs[0].measurements["lower_is_text"] is True
