import pytest

from slideproof.checks.content import content_box
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


def test_c1_text_cut_still_flagged(tiny_deck, make_render):
    deck = _wide_box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"wide": [(12.9, 1.1, 1.0, 0.3)]})
    (f,) = check_offslide(deck, render)
    assert f.check_id == "C1" and f.severity == "visible"
    # edges describe the text: about 0.567 of its 1.0 in width past the right edge
    assert f.measurements["edges"]["right"] == pytest.approx(0.567, abs=0.05)
    assert f.fix is not None and f.fix.element_id == deck.slides[0].elements[0].id


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
