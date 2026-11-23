import pytest

from slideproof.checks.content import content_box
from slideproof.checks.hidden import check_hidden
from slideproof.checks.offslide import check_offslide
from slideproof.checks.overlap import check_overlap
from slideproof.loader import load_deck
from slideproof.units import inches


def _with_spans(deck, render, per_element):
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    el = {e.name: e for e in deck.slides[0].elements}
    render.linked = {el[n].id: [RenderedSpan("t", Rect(*(inches(v) for v in b)), "A", 18, (0, 0, 0))
                                for b in boxes] for n, boxes in per_element.items()}
    return render


def _wide_box_deck(tiny_deck):
    # box x 11..14 on a 13.333 in slide: sticks out ~0.667 in (22%)
    return load_deck(tiny_deck([
        {"kind": "textbox", "name": "wide", "x": 11, "y": 1, "w": 3, "h": 1, "text": "Hi"}]))


def test_c1_box_sticks_out_but_text_inside_not_flagged(tiny_deck, make_render):
    deck = _wide_box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"wide": [(11.1, 1.1, 0.5, 0.3)]})
    assert check_offslide(deck, render) == []
    assert [f.check_id for f in check_offslide(deck, None)] == ["C1"]  # estimate path unchanged


# The wide box is 3 in wide and 0.667 in past the right edge: M2 measures 0.222 outside.
_BOX_OUTSIDE = 0.667 / 3


def test_c1_text_cut_still_flagged(tiny_deck, make_render):
    deck = _wide_box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"wide": [(12.9, 1.1, 1.0, 0.3)]})
    (f,) = check_offslide(deck, render)
    assert f.check_id == "C1" and f.severity == "visible"
    # Rendered spans only decide whether text is cut; the size is measured from the box (M2).
    assert f.measurements["edges"] == {"right": pytest.approx(_BOX_OUTSIDE, abs=0.001)}
    assert f.magnitude == pytest.approx(_BOX_OUTSIDE, abs=0.001)
    assert f.fix is not None and f.fix.element_id == deck.slides[0].elements[0].id


def test_c1_spans_clipped_at_slide_edge_measured_like_m2(tiny_deck, make_render):
    # LibreOffice does not draw glyphs off the page, so the spans stop at the slide edge.
    deck = _wide_box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"wide": [(11.1, 1.1, 2.233, 0.3)]})
    (f,) = check_offslide(deck, render)
    (m2,) = check_offslide(deck, None)
    assert f.severity == "visible"
    assert f.magnitude == pytest.approx(m2.magnitude)
    assert f.measurements == {"outside": pytest.approx(m2.magnitude), "edges": m2.measurements["edges"]}


@pytest.mark.parametrize("gap, flagged", [(0.1, False), (0.09, True)])
def test_c1_text_inside_crossed_edge_boundary(tiny_deck, make_render, gap, flagged):
    # A6: text at least 0.1 in inside every edge the box crosses fits on the slide.
    deck = _wide_box_deck(tiny_deck)
    right = 13.333 - gap
    render = _with_spans(deck, make_render([[]]), {"wide": [(11.1, 1.1, right - 11.1, 0.3)]})
    assert bool(check_offslide(deck, render)) == flagged


def test_c1_only_crossed_edges_count(tiny_deck, make_render):
    # Box crosses the bottom only; text near the right edge does not matter, text at the bottom does.
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "low", "x": 1, "y": 6.5, "w": 12.3, "h": 2, "text": "Hi"}]))
    inside = _with_spans(deck, make_render([[]]), {"low": [(10, 6.6, 3.3, 0.3)]})
    assert check_offslide(deck, inside) == []
    cut = _with_spans(deck, make_render([[]]), {"low": [(1.1, 6.6, 2, 0.9)]})
    (f,) = check_offslide(deck, cut)
    assert f.severity == "visible" and set(f.measurements["edges"]) == {"bottom"}
    assert f.magnitude == pytest.approx(0.5, abs=0.001)


@pytest.mark.soffice
def test_c1_text_cut_between_lines_with_render(tmp_path):
    # Reviewer's scenario 1: four 28 pt lines in a 5 x 2 in box at y = 6.5 in; two lines are
    # off the page, which LibreOffice does not draw.
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from slideproof.analysis import analyse
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(next(l for l in prs.slide_layouts if l.name == "Blank"))
    tb = s.shapes.add_textbox(Inches(1), Inches(6.5), Inches(5), Inches(2))
    tb.name = "off-bottom"
    tf = tb.text_frame
    tf.word_wrap = True
    for c in list(tf._txBody.bodyPr):
        tf._txBody.bodyPr.remove(c)
    tf.text = "Line one\nLine two\nLine three\nLine four"
    for p in tf.paragraphs:
        for r in p.runs:
            r.font.size = Pt(28)
    path = tmp_path / "cut.pptx"
    prs.save(path)
    a = analyse(path, tmp_path / "run")
    assert a.render.status == "ok"
    (f,) = [f for f in a.findings if f.check_id == "C1"]
    assert f.severity == "visible"
    assert f.magnitude == pytest.approx(0.5, abs=0.001)
    assert set(f.measurements["edges"]) == {"bottom"}


@pytest.mark.soffice
def test_demo_slide2_still_flagged_with_render(demo_deck, tmp_path):
    from slideproof.analysis import analyse
    a = analyse(demo_deck[0], tmp_path)
    assert a.render.status == "ok"
    names = {e.id: e.name for s in a.deck.slides for e in s.elements}
    c1 = [f for f in a.findings if f.check_id == "C1" and f.slide_index == 2]
    assert [names[f.element_ids[0]] for f in c1] == ["agenda-box"]


def test_judge_uses_estimate_magnitude(tiny_deck, make_render, monkeypatch):
    from slideproof import intent
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "low", "x": 1, "y": 1, "w": 6, "h": 3, "text": "Some words"},
        {"kind": "picture", "name": "up", "x": 1, "y": 1, "w": 6, "h": 0.5}]))
    if not intent.available():
        pytest.skip("intent model unavailable")
    render = _with_spans(deck, make_render([[]]), {"low": [(1.1, 1.3, 5.0, 0.3)]})
    (f,) = check_overlap(deck, render)
    low = next(e for e in deck.slides[0].elements if e.name == "low")
    up = next(e for e in deck.slides[0].elements if e.name == "up")
    rect, _ = content_box(low)
    expected = up.bbox.intersect(rect).area / rect.area
    assert f.magnitude != pytest.approx(expected, abs=0.01)  # rendered coverage differs
    seen = []
    real = intent.features_for

    def spy(check_id, ids, magnitude, d):
        seen.append(magnitude)
        return real(check_id, ids, magnitude, d)
    monkeypatch.setattr(intent, "features_for", spy)
    intent.judge([f], deck)
    assert seen == [pytest.approx(expected)]


def test_c1_slight_text_cut_is_visible(tiny_deck, make_render):
    deck = _wide_box_deck(tiny_deck)
    # span union 1.0 in wide, ~0.05 in past the right edge (13.333): ~5% outside
    render = _with_spans(deck, make_render([[]]), {"wide": [(12.333, 1.1, 1.05, 0.3)]})
    (f,) = check_offslide(deck, render)
    assert f.severity == "visible" and f.magnitude == pytest.approx(_BOX_OUTSIDE, abs=0.001)


def test_c1_text_entirely_off_slide_in_box_on_slide(tiny_deck, make_render):
    deck = _wide_box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"wide": [(13.6, 1.1, 0.4, 0.3)]})
    (f,) = check_offslide(deck, render)
    assert f.magnitude == pytest.approx(_BOX_OUTSIDE, abs=0.001) and f.severity == "visible"


def test_intent_helpers_match_raw_candidates(demo_deck):
    from slideproof.intent.features import c1_outside, c2_coverage, raw_candidates
    deck = load_deck(demo_deck[0])
    n = 0
    for c in raw_candidates(deck):
        if c.check_id == "C1":
            m = c1_outside(deck.element(c.element_ids[0]), deck.slide_rect)
        else:
            m = c2_coverage(*(deck.element(i) for i in c.element_ids))
        assert m == pytest.approx(c.magnitude)
        n += 1
    assert n > 0


def _autofit_deck(tmp_path, auto_size):
    """A text box (1-6 in across, 1-2 in down) with a picture just below it (2.05-4 in)."""
    from io import BytesIO
    from PIL import Image
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    tb.name = "words"
    tb.text_frame.word_wrap = True
    tb.text_frame.text = "A long title that wraps"
    tb.text_frame.auto_size = auto_size
    buf = BytesIO()
    Image.new("RGB", (100, 100), (128, 128, 128)).save(buf, "PNG")
    buf.seek(0)
    s.shapes.add_picture(buf, Inches(1), Inches(2.05), Inches(5), Inches(1.95)).name = "pic"
    p = tmp_path / f"autofit-{auto_size}.pptx"
    prs.save(p)
    return load_deck(p)


@pytest.mark.parametrize("auto_size, flagged", [("TEXT_TO_FIT_SHAPE", False), ("NONE", True)])
def test_shrink_autofit_text_is_kept_inside_its_box(tmp_path, make_render, auto_size, flagged):
    # LibreOffice may not shrink a "shrink text on overflow" box, so its rendered second line
    # runs into the picture below; PowerPoint shrinks the text into the box, so nothing is covered.
    from pptx.enum.text import MSO_AUTO_SIZE
    deck = _autofit_deck(tmp_path, getattr(MSO_AUTO_SIZE, auto_size))
    words = next(e for e in deck.slides[0].elements if e.name == "words")
    render = _with_spans(deck, make_render([[]]),
                         {"words": [(1.5, 1.05, 4.0, 0.6), (2.0, 1.65, 3.0, 0.6)]})
    rect, _ = content_box(words, render.linked[words.id])
    assert (rect.bottom <= words.bbox.bottom) == (not flagged)
    assert bool(check_overlap(deck, render)) == flagged
    assert check_hidden(deck, render) == []  # the picture covers part of the text, not all


def test_shrink_box_with_text_rendered_outside_falls_back_to_the_box(tmp_path, make_render):
    # The rendered text lies wholly below the shrink box: PowerPoint shrinks it into the box,
    # so the content box is the box itself, not the rendered text out there.
    from pptx.enum.text import MSO_AUTO_SIZE
    deck = _autofit_deck(tmp_path, MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE)
    words = next(e for e in deck.slides[0].elements if e.name == "words")
    render = _with_spans(deck, make_render([[]]), {"words": [(1.5, 4.5, 3.0, 0.6)]})
    rect, conf = content_box(words, render.linked[words.id])
    assert rect == words.bbox and conf == "definite"


@pytest.mark.parametrize("pic_y, judged", [(3.5, False), (1.0, True)])
def test_judge_skips_c2_without_estimate_overlap(tiny_deck, pic_y, judged):
    # Rendered text can sit where the estimate does not; with no (or under 5%) estimated
    # coverage the model has nothing it was trained on, so the finding stays in the main list.
    from slideproof import intent
    from slideproof.findings import Finding
    if not intent.available():
        pytest.skip("intent model unavailable")
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "low", "x": 1, "y": 1, "w": 6, "h": 3, "text": "Some words"},
        {"kind": "picture", "name": "up", "x": 1, "y": pic_y, "w": 6, "h": 0.5}]))
    low, up = (next(e for e in deck.slides[0].elements if e.name == n) for n in ("low", "up"))
    f = Finding("C2", 1, deck.slides[0].slide_id, (up.id, low.id), "visible", "definite", 0.9,
                {"coverage": 0.9, "lower_is_text": True})
    (out,), note = intent.judge([f], deck)
    assert note is None
    assert ("intent_p" in out.measurements) == judged


def test_judge_skips_c2_under_five_percent_estimate(tiny_deck, monkeypatch):
    from slideproof import intent
    from slideproof.findings import Finding
    if not intent.available():
        pytest.skip("intent model unavailable")
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "low", "x": 1, "y": 1, "w": 6, "h": 3, "text": "Some words"},
        {"kind": "picture", "name": "up", "x": 1, "y": 1, "w": 6, "h": 0.5}]))
    low, up = (next(e for e in deck.slides[0].elements if e.name == n) for n in ("low", "up"))
    f = Finding("C2", 1, deck.slides[0].slide_id, (up.id, low.id), "visible", "definite", 0.9, {})
    monkeypatch.setattr(intent, "c2_coverage", lambda u, l: 0.049)
    (out,), _ = intent.judge([f], deck)
    assert "intent_p" not in out.measurements
    monkeypatch.setattr(intent, "c2_coverage", lambda u, l: 0.05)
    (out,), _ = intent.judge([f], deck)
    assert "intent_p" in out.measurements
