import random

import pytest
from PIL import Image, ImageDraw

from slideproof.checks import CHECKS
from slideproof.checks.content import FURNITURE_PLACEHOLDERS
from slideproof.checks.contrast import check_contrast, contrast_ratio
from slideproof.describe.copy import GROUPED
from slideproof.loader import load_deck
from slideproof.units import inches

PX_PER_IN = 96  # synthetic slide PNGs: 13.333 x 7.5 in at 96 px per inch


def _px(v):
    return round(v * PX_PER_IN)


def _slide_png(path, background, text_rgb, text_box, photo=None):
    """A slide PNG: flat background, optional noisy photo rectangle, text strokes in text_box (inches)."""
    img = Image.new("RGB", (_px(13.333), _px(7.5)), background)
    d = ImageDraw.Draw(img)
    if photo is not None:
        (x, y, w, h), base = photo
        rnd = random.Random(7)
        for py in range(_px(y), _px(y + h)):
            for px in range(_px(x), _px(x + w)):
                img.putpixel((px, py), tuple(max(0, min(255, c + rnd.randint(-25, 25))) for c in base))
    x, y, w, h = text_box
    # horizontal strokes like letters: about a third of the box is text colour
    for i in range(_px(x), _px(x + w), 6):
        d.rectangle([i, _px(y) + 4, i + 2, _px(y + h) - 4], fill=text_rgb)
    img.save(path)
    return path


def _render(make_render, png, deck, per_element):
    """per_element: name -> list of (bbox inches, rgb, size, bold)."""
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    render = make_render([[]])
    render.slides[0].png_path = png
    el = {e.name: e for e in deck.slides[0].elements}
    render.linked = {el[n].id: [RenderedSpan("t", Rect(*(inches(v) for v in b)), "A", size, rgb, bold)
                                for b, rgb, size, bold in spans]
                     for n, spans in per_element.items()}
    return render


def test_contrast_ratio_math():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)
    assert contrast_ratio((0x77, 0x77, 0x77), (255, 255, 255)) == pytest.approx(4.48, abs=0.01)


def test_grey_on_white_flagged(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "grey", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"grey": [((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.check_id == "C7" and f.severity == "visible" and f.confidence == "definite"
    assert f.fix is None and f.element_ids == (deck.slides[0].elements[0].id,)
    assert f.measurements == {"ratio": 1.9, "need": 4.5}


def test_one_finding_per_element_for_worst_span(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "grey", "x": 1, "y": 1, "w": 5, "h": 2, "text": "Grey"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"grey": [
        ((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False),
        ((1.1, 1.1, 3, 0.5), (0x99,) * 3, 12.0, False),
        ((1.1, 1.1, 3, 0.5), (0, 0, 0), 12.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.measurements["ratio"] == 1.9


def test_white_on_dark_photo_not_flagged(tiny_deck, make_render, tmp_path):
    # Review Focus 2: a noisy dark photo behind white text is fine.
    deck = load_deck(tiny_deck([
        {"kind": "picture", "name": "photo", "x": 1, "y": 1, "w": 6, "h": 3},
        {"kind": "textbox", "name": "caption", "x": 1.5, "y": 2, "w": 5, "h": 1, "text": "Caption"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (255, 255, 255), (1.6, 2.1, 3, 0.5),
                     photo=((1, 1, 6, 3), (40, 50, 45)))
    render = _render(make_render, png, deck, {"caption": [((1.6, 2.1, 3, 0.5), (255, 255, 255), 18.0, False)]})
    assert check_contrast(deck, render) == []


def test_text_on_bright_photo_is_likely(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "picture", "name": "photo", "x": 1, "y": 1, "w": 6, "h": 3},
        {"kind": "textbox", "name": "caption", "x": 1.5, "y": 2, "w": 5, "h": 1, "text": "Caption"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (255, 255, 255), (1.6, 2.1, 3, 0.5),
                     photo=((1, 1, 6, 3), (0xFF, 0xF5, 0x9D)))
    render = _render(make_render, png, deck, {"caption": [((1.6, 2.1, 3, 0.5), (255, 255, 255), 28.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.confidence == "likely" and f.measurements["need"] == 3


def test_large_bold_needs_only_3(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Mid grey"}]))
    grey = (0x88, 0x88, 0x88)  # about 3.5:1 on white
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), grey, (1.1, 1.1, 3, 0.5))
    span = (1.1, 1.1, 3, 0.5)
    assert check_contrast(deck, _render(make_render, png, deck, {"box": [(span, grey, 14.0, True)]})) == []
    assert check_contrast(deck, _render(make_render, png, deck, {"box": [(span, grey, 18.0, False)]})) == []
    (f,) = check_contrast(deck, _render(make_render, png, deck, {"box": [(span, grey, 14.0, False)]}))
    assert f.measurements == {"ratio": 3.5, "need": 4.5}
    (f,) = check_contrast(deck, _render(make_render, png, deck, {"box": [(span, grey, 13.0, True)]}))
    assert f.measurements["need"] == 4.5


def test_span_with_too_few_background_pixels_skipped(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}]))
    png = tmp_path / "s.png"
    Image.new("RGB", (_px(13.333), _px(7.5)), (0xBB, 0xBB, 0xBB)).save(png)
    render = _render(make_render, png, deck, {"box": [((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False)]})
    assert check_contrast(deck, render) == []


def test_png_loaded_once_per_slide(tiny_deck, make_render, tmp_path, monkeypatch):
    import slideproof.checks.contrast as mod
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "a", "x": 1, "y": 1, "w": 5, "h": 1, "text": "A"},
        {"kind": "textbox", "name": "b", "x": 1, "y": 3, "w": 5, "h": 1, "text": "B"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (1.1, 1.1, 3, 0.5))
    span = ((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False)
    render = _render(make_render, png, deck, {"a": [span, span], "b": [span]})
    opened = []
    real_open = mod.Image.open
    monkeypatch.setattr(mod.Image, "open", lambda p, *a, **k: opened.append(p) or real_open(p, *a, **k))
    assert len(check_contrast(deck, render)) == 2
    assert len(opened) == 1


def test_contrast_skipped_without_render(demo_deck):
    deck = load_deck(demo_deck[0])
    assert check_contrast(deck, None) == []


def test_contrast_registered():
    assert check_contrast in CHECKS


def test_contrast_copy(tiny_deck):
    from slideproof.describe import describe
    from slideproof.findings import Finding
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 0.5, "y": 0.5, "w": 4, "h": 2, "text": "Milestones"}]))
    el = deck.slides[0].elements[0]
    d = describe(Finding("C7", 1, el.slide_id, (el.id,), "visible", "definite", 0.5,
                         {"ratio": 1.9, "need": 3}), deck)
    assert d.headline == 'text box "Milestones" has low contrast'
    assert d.full == ('Text box "Milestones", in the top left, has text that is too close in colour to its '
                      "background (contrast 1.9:1, at least 3:1 is needed), so it will be hard to read, "
                      "especially on a projector. Confidence: definite.")
    d = describe(Finding("C7", 1, el.slide_id, (el.id,), "visible", "likely", 0.5,
                         {"ratio": 4.0, "need": 4.5}), deck)
    assert "(contrast 4.0:1, at least 4.5:1 is needed)" in d.full and d.full.endswith("Confidence: likely.")
    assert GROUPED["C7"] == ("{c} text boxes have low contrast",
                             "{c} text boxes on this slide have low contrast. Confidence: {conf}.")


@pytest.mark.soffice
def test_demo_slide7_two_contrast_findings(demo_deck, tmp_path):
    from slideproof.analysis import analyse
    path = demo_deck[0]
    result = analyse(path, tmp_path / "run")
    assert result.render.status == "ok"
    deck = result.deck
    names = {e.id: e.name for s in deck.slides for e in s.elements}
    got = {names[f.element_ids[0]]: f for f in result.findings if f.check_id == "C7"}
    assert set(got) == {"grey-text", "photo-caption"}
    assert got["grey-text"].confidence == "definite" and got["grey-text"].slide_index == deck.slides[6].index
    assert got["photo-caption"].confidence == "likely" and got["photo-caption"].slide_index == deck.slides[6].index
    for f in got.values():
        assert f.severity == "visible" and f.measurements["need"] == 3


def test_very_faint_text_flagged_from_ring(tiny_deck, make_render, tmp_path):
    # #E0E0E0 is within 60 RGB of white, so no pixel in the box counts as background:
    # the ring just outside the box measures it instead.
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "faint", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Faint"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xE0, 0xE0, 0xE0), (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"faint": [((1.1, 1.1, 3, 0.5), (0xE0,) * 3, 12.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.measurements == {"ratio": 1.3, "need": 4.5} and f.confidence == "definite"


def test_ratio_never_rounds_up_to_need(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}]))
    grey = (0x77, 0x77, 0x77)  # 4.48:1 on white
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), grey, (1.1, 1.1, 3, 0.5))
    (f,) = check_contrast(deck, _render(make_render, png, deck, {"box": [((1.1, 1.1, 3, 0.5), grey, 12.0, False)]}))
    assert f.measurements == {"ratio": 4.4, "need": 4.5}


def test_span_off_the_png_ignored(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB,) * 3, (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"box": [((20, 10, 3, 0.5), (0xBB,) * 3, 12.0, False)]})
    assert check_contrast(deck, render) == []


def test_contrast_skipped_when_render_failed(tiny_deck, make_render, tmp_path):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}]))
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB,) * 3, (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"box": [((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False)]})
    render.status = "failed"
    assert check_contrast(deck, render) == []


@pytest.mark.parametrize("far,ratio", [(20, None), (19, 3.5)])
def test_far_pixel_boundary(tiny_deck, make_render, tmp_path, far, ratio):
    # 10 x 7.5 in slide at 96 px per inch, so the span box maps to whole pixels 96..192 x 96..144.
    # Inside the box: span colour plus `far` black pixels. Outside (the ring): white.
    # 20 far pixels -> black background (5.9:1, fine); 19 -> falls back to the white ring (3.5:1, flagged).
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 5, "h": 1, "text": "Grey"}],
        slide_w=inches(10)))
    grey = (0x88, 0x88, 0x88)
    img = Image.new("RGB", (960, 720), (255, 255, 255))
    ImageDraw.Draw(img).rectangle([96, 96, 191, 143], fill=grey)
    for i in range(far):
        img.putpixel((100 + i, 100), (0, 0, 0))
    png = tmp_path / "s.png"
    img.save(png)
    render = _render(make_render, png, deck, {"box": [((1, 1, 1, 0.5), grey, 12.0, False)]})
    got = [f.measurements["ratio"] for f in check_contrast(deck, render)]
    assert got == ([] if ratio is None else [ratio])


def _placeholder_deck(tmp_path, ph_type):
    """A "Title and Content" slide whose ph_type placeholder (cloned from the layout) has text."""
    from pptx import Presentation
    from pptx.enum.shapes import PP_PLACEHOLDER
    prs = Presentation()
    prs.slide_width = inches(13.333)  # the PNG frame used here
    layout = prs.slide_layouts[1]
    s = prs.slides.add_slide(layout)
    want = getattr(PP_PLACEHOLDER, ph_type)
    ph = next((p for p in s.placeholders if p.placeholder_format.type == want), None)
    if ph is None:
        lp = next(p for p in layout.placeholders if p.placeholder_format.type == want)
        s.shapes.clone_placeholder(lp)
        ph = next(p for p in s.placeholders if p.placeholder_format.type == want)
    ph.text_frame.text = "7"
    ph.name = "target"
    p = tmp_path / f"ph-{ph_type}.pptx"
    prs.save(p)
    return load_deck(p)


@pytest.mark.parametrize("ph_type, severity", [("SLIDE_NUMBER", "minor"), ("FOOTER", "minor"),
                                               ("DATE", "minor"), ("OBJECT", "visible")])
def test_slide_furniture_low_contrast_is_minor(tmp_path, make_render, ph_type, severity):
    # Footer, date and slide number come with the template; real failures, but not the author's.
    # OBJECT is the layout's content placeholder, loaded as a body placeholder.
    deck = _placeholder_deck(tmp_path, ph_type)
    target = next(e for e in deck.slides[0].elements if e.name == "target")
    x, y = target.bbox.x / 914400 + 0.05, target.bbox.y / 914400 + 0.05
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (x, y, 0.6, 0.25))
    render = _render(make_render, png, deck, {"target": [((x, y, 0.6, 0.25), (0xBB,) * 3, 12.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.check_id == "C7" and f.severity == severity and f.confidence == "definite"
    if ph_type == "OBJECT":
        assert target.kind == "body" and target.placeholder_type not in FURNITURE_PLACEHOLDERS


def test_minor_low_contrast_reads_well_and_goes_in_the_minor_list(tmp_path, make_render):
    from slideproof.describe import describe
    from slideproof.prioritise import prioritise
    deck = _placeholder_deck(tmp_path, "SLIDE_NUMBER")
    target = next(e for e in deck.slides[0].elements if e.name == "target")
    x, y = target.bbox.x / 914400 + 0.05, target.bbox.y / 914400 + 0.05
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (x, y, 0.6, 0.25))
    render = _render(make_render, png, deck, {"target": [((x, y, 0.6, 0.25), (0xBB,) * 3, 12.0, False)]})
    (f,) = check_contrast(deck, render)
    item = describe(f, deck)
    assert item.headline.endswith("has low contrast")
    assert "visible" not in item.full and item.full.endswith("Confidence: definite.")
    assert "visible" not in " ".join(GROUPED["C7"])
    report = prioritise([f], 1, 1.0)
    assert report.visible == [] and [g.check_id for g in report.minor] == ["C7"]


def _patch_deck(tmp_path, patch_x):
    """A text box (1-8 in across, 5-6 in down) with a filled rectangle above it from patch_x."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(5), Inches(7), Inches(1))
    tb.name = "half"
    tb.text_frame.text = "Another line of visible text"
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(patch_x), Inches(4.8), Inches(5), Inches(1.5))
    r.fill.solid()
    r.fill.fore_color.rgb = RGBColor(0x10, 0x10, 0x30)
    p = tmp_path / "patch.pptx"
    prs.save(p)
    return load_deck(p)


@pytest.mark.parametrize("patch_x, flagged", [(3.5, False), (8.5, True)])
def test_span_covered_by_opaque_element_above_is_skipped(tmp_path, make_render, patch_x, flagged):
    # The second span sits on navy in the picture; with the rectangle over it, it cannot be seen,
    # so its contrast does not matter (C2 reports the cover). With the rectangle elsewhere, it counts.
    deck = _patch_deck(tmp_path, patch_x)
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0, 0, 0), (1.1, 5.1, 2, 0.4),
                     photo=((3.5, 4.8, 5, 1.5), (0x10, 0x10, 0x30)))
    img = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(img)
    for i in range(_px(4.0), _px(6.0), 6):
        d.rectangle([i, _px(5.1) + 4, i + 2, _px(5.5) - 4], fill=(0, 0, 0))
    img.save(png)
    render = _render(make_render, png, deck, {"half": [
        ((1.1, 5.1, 2, 0.4), (0, 0, 0), 24.0, False),
        ((4.0, 5.1, 2, 0.4), (0, 0, 0), 24.0, False)]})
    assert bool(check_contrast(deck, render)) == flagged


_PIC_BG = ('<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
           'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:bgPr>'
           '<a:blipFill><a:stretch><a:fillRect/></a:stretch></a:blipFill><a:effectLst/></p:bgPr></p:bg>')
_SOLID_BG = ('<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:bgPr>'
             '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>')


def _set_bg(part_element, xml):
    from lxml import etree
    from pptx.oxml.ns import qn
    csld = part_element.find(qn("p:cSld"))
    old = csld.find(qn("p:bg"))
    if old is not None:
        csld.remove(old)
    csld.insert(0, etree.fromstring(xml))


@pytest.mark.parametrize("backgrounds, conf", [
    ({}, "definite"),
    ({"slide": _PIC_BG}, "likely"),
    ({"layout": _PIC_BG}, "likely"),
    ({"master": _PIC_BG}, "likely"),
    ({"slide": _SOLID_BG, "layout": _PIC_BG}, "definite"),  # the slide's own background wins
])
def test_picture_background_makes_contrast_likely(tmp_path, make_render, backgrounds, conf):
    from pptx import Presentation
    prs = Presentation()
    prs.slide_width, prs.slide_height = inches(13.333), inches(7.5)
    layout = prs.slide_layouts[6]
    s = prs.slides.add_slide(layout)
    tb = s.shapes.add_textbox(inches(1), inches(1), inches(5), inches(1))
    tb.name = "grey"
    tb.text_frame.text = "Grey"
    parts = {"slide": s._element, "layout": layout._element, "master": prs.slide_master._element}
    for where, xml in backgrounds.items():
        _set_bg(parts[where], xml)
    p = tmp_path / "bg.pptx"
    prs.save(p)
    deck = load_deck(p)
    png = _slide_png(tmp_path / "s.png", (255, 255, 255), (0xBB, 0xBB, 0xBB), (1.1, 1.1, 3, 0.5))
    render = _render(make_render, png, deck, {"grey": [((1.1, 1.1, 3, 0.5), (0xBB,) * 3, 12.0, False)]})
    (f,) = check_contrast(deck, render)
    assert f.confidence == conf
