import pytest

from slideproof.checks import CHECKS
from slideproof.checks.overflow import check_overflow
from slideproof.loader import load_deck
from slideproof.units import inches


def _with_spans(deck, render, per_element):
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    el = {e.name: e for e in deck.slides[0].elements}
    render.linked = {el[n].id: [RenderedSpan("t", Rect(*(inches(v) for v in b)), "A", 18, (0, 0, 0))
                                for b in boxes] for n, boxes in per_element.items()}
    return render


def _box_deck(tiny_deck):
    # text box 1..5 in across, 1..3 in down
    return load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 4, "h": 2, "text": "Lots of text"}]))


def test_overflow_flagged_when_text_runs_past_bottom(tiny_deck, make_render):
    deck = _box_deck(tiny_deck)
    # text runs 1 in below the box (box height 2 in): half its height
    render = _with_spans(deck, make_render([[]]), {"box": [(1.1, 1.1, 3.0, 0.4), (1.1, 3.6, 3.0, 0.4)]})
    (f,) = check_overflow(deck, render)
    assert f.check_id == "C3" and f.severity == "visible" and f.confidence == "likely"
    assert f.fix is None
    assert f.element_ids == (deck.slides[0].elements[0].id,)
    assert f.measurements["edge"] == "bottom"
    assert f.measurements["amount"] == pytest.approx(0.5, abs=0.01)


def test_overflow_right_edge_when_larger(tiny_deck, make_render):
    deck = _box_deck(tiny_deck)
    # 0.2 in below (10% of height), 2 in to the right (50% of width): right is the larger overflow
    render = _with_spans(deck, make_render([[]]), {"box": [(1.1, 2.8, 5.9, 0.4)]})
    (f,) = check_overflow(deck, render)
    assert f.measurements["edge"] == "right"
    assert f.measurements["amount"] == pytest.approx(0.5, abs=0.01)


def test_overflow_ignored_under_tenth_inch(tiny_deck, make_render):
    # Review Focus 1: font substitution can push text slightly past its box.
    deck = _box_deck(tiny_deck)
    render = _with_spans(deck, make_render([[]]), {"box": [(1.1, 2.7, 3.0, 0.39), (1.1, 1.1, 3.98, 0.3)]})
    assert check_overflow(deck, render) == []


def test_overflow_skipped_without_render(demo_deck):
    from slideproof.render.pipeline import RenderResult
    deck = load_deck(demo_deck[0])
    assert check_overflow(deck, None) == []
    assert check_overflow(deck, RenderResult("skipped", "LibreOffice is not installed", [])) == []


def test_overflow_registered():
    assert check_overflow in CHECKS


@pytest.mark.soffice
def test_demo_timeline_overflow(demo_deck, tmp_path):
    from slideproof.analysis import analyse
    a = analyse(demo_deck[0], tmp_path)
    assert a.render.status == "ok"
    names = {e.id: e.name for s in a.deck.slides for e in s.elements}
    c3 = [f for f in a.findings if f.check_id == "C3" and f.slide_index == 6]
    assert [(names[f.element_ids[0]], f.severity) for f in c3] == [("timeline-list", "visible")]
    assert c3[0].measurements["edge"] == "bottom"
