import fitz
import pytest

from slideproof.loader import load_deck
from slideproof.render.link import link_spans
from slideproof.render.pdf import read_pdf
from slideproof.units import inches


def _two_boxes(tiny_deck, t1="Alpha", t2="Beta"):
    return load_deck(tiny_deck([
        {"kind": "textbox", "name": "a", "x": 1, "y": 1, "w": 3, "h": 1, "text": t1},
        {"kind": "textbox", "name": "b", "x": 6, "y": 4, "w": 3, "h": 1, "text": t2}]))


def test_bold_flag_read(tmp_path):
    pdf = tmp_path / "b.pdf"
    doc = fitz.open()
    page = doc.new_page(width=720, height=540)
    page.insert_text((50, 100), "Bold words", fontname="hebo", fontsize=20)
    page.insert_text((50, 200), "Plain words", fontname="helv", fontsize=20)
    doc.save(pdf); doc.close()
    spans = read_pdf(pdf, tmp_path / "png", inches(10), inches(7.5))[0].spans
    by = {s.text: s.bold for s in spans}
    assert by["Bold words"] is True and by["Plain words"] is False


def test_links_span_to_containing_text_box(tiny_deck, make_render):
    deck = _two_boxes(tiny_deck)
    render = make_render([[("Alpha", (inches(1.1), inches(1.1), inches(1), inches(0.3))),
                           ("Beta", (inches(6.1), inches(4.1), inches(1), inches(0.3)))]])
    linked = link_spans(deck, render)
    a, b = deck.slides[0].elements
    assert [s.text for s in linked[a.id]] == ["Alpha"]
    assert [s.text for s in linked[b.id]] == ["Beta"]


def test_repeated_text_prefers_containing_box(tiny_deck, make_render):
    deck = _two_boxes(tiny_deck, "Totals", "Totals")
    render = make_render([[("Totals", (inches(6.1), inches(4.1), inches(1), inches(0.3)))]])
    linked = link_spans(deck, render)
    a, b = deck.slides[0].elements
    assert a.id not in linked and len(linked[b.id]) == 1


def test_unmatched_span_ignored(tiny_deck, make_render):
    deck = _two_boxes(tiny_deck)
    render = make_render([[("Gamma", (inches(1), inches(1), inches(1), inches(0.3)))]])
    assert link_spans(deck, render) == {}


def test_hidden_slide_gets_nothing(tiny_deck, make_render):
    deck = _two_boxes(tiny_deck)
    assert link_spans(deck, make_render([None])) == {}


def test_rendered_content_box_is_span_union(tiny_deck, make_render):
    from slideproof.checks.content import content_box
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    el = _two_boxes(tiny_deck).slides[0].elements[0]
    s1 = RenderedSpan("Al", Rect(1000, 2000, 500, 300), "A", 18, (0, 0, 0))
    s2 = RenderedSpan("pha", Rect(1600, 2100, 700, 400), "A", 18, (0, 0, 0))
    rect, conf = content_box(el, [s1, s2])
    pad = 45720
    assert conf == "definite"
    assert (rect.x, rect.y, rect.right, rect.bottom) == (1000 - pad, 2000 - pad, 2300 + pad, 2500 + pad)


@pytest.mark.soffice
def test_demo_deck_agenda_spans_link(demo_deck, tmp_path):
    from slideproof.analysis import analyse
    a = analyse(demo_deck[0], tmp_path)
    ag = next(e for s in a.deck.slides for e in s.elements if e.name == "agenda-box")
    assert len(a.render.linked.get(ag.id, [])) >= 4
