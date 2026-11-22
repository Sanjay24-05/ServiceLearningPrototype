from io import BytesIO

from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt

from slideproof.checks.overlap import check_overlap
from slideproof.describe import describe
from slideproof.loader import load_deck


def _png():
    b = BytesIO(); Image.new("RGB", (400, 300), (200, 80, 80)).save(b, "PNG"); b.seek(0); return b


def _deck(tmp_path, build):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    build(s)
    p = tmp_path / "o.pptx"; prs.save(p)
    return load_deck(p)


def _long_text(s, x=0.5, y=1.0, w=7, h=4.5, n=6):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i in range(n):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = f"Line {i} with enough words to fill the box width"
        para.runs[0].font.size = Pt(24)


def test_picture_over_text_flagged(tmp_path):
    d = _deck(tmp_path, lambda s: (_long_text(s),
                                    s.shapes.add_picture(_png(), Inches(0.5), Inches(2.5), Inches(7), Inches(3))))
    fs = check_overlap(d, None)
    assert len(fs) == 1
    f = fs[0]
    assert f.check_id == "C2" and f.severity == "visible" and f.confidence == "likely"
    assert f.measurements["coverage"] >= 0.3 and f.measurements["lower_is_text"] is True
    assert f.fix is None


def test_picture_beside_short_text_not_flagged(tmp_path):
    def build(s):
        tf = s.shapes.add_textbox(Inches(0.5), Inches(1), Inches(12), Inches(5)).text_frame
        tf.text = "Short"
        s.shapes.add_picture(_png(), Inches(7), Inches(3), Inches(5), Inches(3))
    assert check_overlap(_deck(tmp_path, build), None) == []


def test_caption_inside_photo_not_flagged(tmp_path):
    def build(s):
        s.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(8), Inches(5))
        s.shapes.add_textbox(Inches(2), Inches(5), Inches(5), Inches(0.8)).text_frame.text = "Caption"
    assert check_overlap(_deck(tmp_path, build), None) == []


def test_background_below_text_not_flagged(demo_deck):
    d = load_deck(demo_deck[0])
    assert [f for f in check_overlap(d, None) if f.slide_index == 8] == []


def test_grouped_members_not_flagged(tmp_path):
    def build(s):
        g = s.shapes.add_group_shape()
        tf = g.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3)).text_frame
        tf.text = "A label that is long enough to be covered by the picture"
        g.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(6), Inches(3))
    assert check_overlap(_deck(tmp_path, build), None) == []


def test_two_overlapping_text_boxes_flagged(tmp_path):
    def build(s):
        _long_text(s, 0.5, 1, 7, 3, n=3)
        _long_text(s, 0.5, 1.4, 7, 3, n=3)
    fs = check_overlap(_deck(tmp_path, build), None)
    assert len(fs) == 1 and fs[0].measurements["lower_is_text"] is True


def test_demo_slide3_c2(demo_deck):
    d = load_deck(demo_deck[0])
    fs = [f for f in check_overlap(d, None) if f.slide_index == 3]
    assert len(fs) == 1
    assert {d.element(i).name for i in fs[0].element_ids} == {"results-chart", "results-list"}
    short = describe(fs[0], d).short
    assert short.startswith('Slide 3: picture "Bar chart of harvest results" covers ')
    assert 'text box "' in short
    assert "may not be able to read the covered text" in describe(fs[0], d).full


def test_shapes_stacked_on_plain_shape_not_flagged(tmp_path):
    # Icon artwork: a small filled shape on top of a larger filled shape without text.
    from pptx.enum.shapes import MSO_SHAPE

    def build(s):
        for sh in (s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1), Inches(1), Inches(1.6), Inches(1.6)),
                   s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.4), Inches(1.6), Inches(0.9), Inches(0.5))):
            sh.fill.solid()  # explicit fills, like template artwork
    assert check_overlap(_deck(tmp_path, build), None) == []


def test_picture_over_picture_still_flagged(tmp_path):
    def build(s):
        s.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(4), Inches(3))
        s.shapes.add_picture(_png(), Inches(3), Inches(2), Inches(4), Inches(3))
    fs = check_overlap(_deck(tmp_path, build), None)
    assert len(fs) == 1 and fs[0].measurements["lower_is_text"] is False


def test_filled_caption_band_inside_photo_not_flagged(tmp_path):
    # Review issue 9: a coloured caption band with text, inside a photo, is a deliberate label.
    from pptx.enum.shapes import MSO_SHAPE

    def build(s):
        s.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(8), Inches(5))
        band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1), Inches(5.2), Inches(8), Inches(0.8))
        band.fill.solid(); band.text_frame.text = "Volunteers at the spring planting day"
    assert check_overlap(_deck(tmp_path, build), None) == []


def test_textless_shape_hiding_photo_still_flagged(tmp_path):
    from pptx.enum.shapes import MSO_SHAPE

    def build(s):
        s.shapes.add_picture(_png(), Inches(1), Inches(1), Inches(8), Inches(5))
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2), Inches(2), Inches(4), Inches(3))
        box.fill.solid()
    assert len(check_overlap(_deck(tmp_path, build), None)) == 1
