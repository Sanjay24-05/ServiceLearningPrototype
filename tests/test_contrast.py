import random

import pytest
from PIL import Image, ImageDraw

from slideproof.checks import CHECKS
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
