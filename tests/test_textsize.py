from dataclasses import replace

import pytest

from slideproof.checks import CHECKS
from slideproof.checks.textsize import check_textsize
from slideproof.describe import describe
from slideproof.findings import Finding
from slideproof.loader import load_deck
from slideproof.units import inches


def _with_sizes(deck, render, per_element):
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    el = {e.name: e for e in deck.slides[0].elements}
    render.linked = {el[n].id: [RenderedSpan("t", Rect(inches(1), inches(1), inches(1), inches(0.3)),
                                             "A", size, (0, 0, 0)) for size in sizes]
                     for n, sizes in per_element.items()}
    return render


def _three_boxes(tiny_deck):
    return load_deck(tiny_deck([
        {"kind": "textbox", "name": "tiny", "x": 1, "y": 1, "w": 4, "h": 1, "text": "Tiny"},
        {"kind": "textbox", "name": "smallish", "x": 1, "y": 3, "w": 4, "h": 1, "text": "Smallish"},
        {"kind": "textbox", "name": "fine", "x": 1, "y": 5, "w": 4, "h": 1, "text": "Fine"}]))


def test_small_text_visible_and_minor_bands(tiny_deck, make_render):
    deck = _three_boxes(tiny_deck)
    render = _with_sizes(deck, make_render([[]]),
                         {"tiny": [24, 10.4], "smallish": [16, 20], "fine": [18, 28]})
    names = {e.id: e.name for e in deck.slides[0].elements}
    got = {names[f.element_ids[0]]: f for f in check_textsize(deck, render)}
    assert set(got) == {"tiny", "smallish"}
    assert got["tiny"].severity == "visible" and got["tiny"].measurements == {"size": 10}
    assert got["smallish"].severity == "minor" and got["smallish"].measurements == {"size": 16}
    for f in got.values():
        assert f.check_id == "C6" and f.confidence == "definite" and f.fix is None


def test_minor_band_only_for_body_text(tiny_deck, make_render):
    deck = _three_boxes(tiny_deck)
    s = deck.slides[0]
    s.elements[0] = replace(s.elements[0], kind="title")
    render = _with_sizes(deck, make_render([[]]), {"tiny": [16]})
    assert check_textsize(deck, render) == []
    render = _with_sizes(deck, make_render([[]]), {"tiny": [11]})
    assert [f.severity for f in check_textsize(deck, render)] == ["visible"]


@pytest.mark.parametrize("ph", ["FOOTER", "DATE", "SLIDE_NUMBER"])
def test_footer_placeholders_exempt(tiny_deck, make_render, ph):
    # Review Focus 3: footers, dates and slide numbers are small on purpose.
    deck = _three_boxes(tiny_deck)
    s = deck.slides[0]
    s.elements[0] = replace(s.elements[0], placeholder_type=ph)
    render = _with_sizes(deck, make_render([[]]), {"tiny": [8]})
    assert check_textsize(deck, render) == []


def test_textsize_skipped_without_render(demo_deck):
    deck = load_deck(demo_deck[0])
    assert check_textsize(deck, None) == []


def test_textsize_registered():
    assert check_textsize in CHECKS


@pytest.mark.soffice
def test_demo_small_text(tiny_deck, tmp_path):
    from pptx import Presentation
    from pptx.util import Pt
    from slideproof.analysis import analyse
    path = tiny_deck([
        {"kind": "textbox", "name": "note", "x": 1, "y": 1, "w": 6, "h": 1, "text": "Read the small print"},
        {"kind": "textbox", "name": "big", "x": 1, "y": 3, "w": 6, "h": 1, "text": "Large heading text"}])
    prs = Presentation(str(path))
    for sh in prs.slides[0].shapes:
        sh.text_frame.paragraphs[0].runs[0].font.size = Pt(10 if sh.name == "note" else 32)
    prs.save(path)
    a = analyse(path, tmp_path)
    assert a.render.status == "ok"
    names = {e.id: e.name for s in a.deck.slides for e in s.elements}
    c6 = [f for f in a.findings if f.check_id == "C6"]
    assert [(names[f.element_ids[0]], f.severity, f.measurements["size"]) for f in c6] == \
        [("note", "visible", 10)]


def _finding(deck, check_id, severity, confidence, measurements):
    el = deck.slides[0].elements[0]
    return Finding(check_id, 1, el.slide_id, (el.id,), severity, confidence, 0.5, measurements)


def test_copy_c3_c6(tiny_deck):
    deck = load_deck(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 0.5, "y": 0.5, "w": 4, "h": 2, "text": "Milestones"}]))
    d = describe(_finding(deck, "C3", "visible", "likely", {"edge": "bottom", "amount": 0.5}), deck)
    assert d.headline == 'text box "Milestones" has more text than fits in its box'
    assert d.full == ('Text box "Milestones", in the top left, has more text than fits: it runs past the '
                      "bottom of its box by about half of the box's height, so it may spill onto "
                      "other content or be cut off. Confidence: likely.")
    d = describe(_finding(deck, "C3", "visible", "likely", {"edge": "right", "amount": 0.2}), deck)
    assert "past the right of its box by about a fifth of the box's width," in d.full

    d = describe(_finding(deck, "C6", "visible", "definite", {"size": 10}), deck)
    assert d.headline == 'text box "Milestones" has small text'
    assert d.full == ('Text box "Milestones", in the top left, has text as small as 10 point, which is hard '
                      "to read when projected. Use at least 18 point for body text. "
                      "Confidence: definite.")
    d = describe(_finding(deck, "C6", "minor", "definite", {"size": 16}), deck)
    assert d.full == ('Text box "Milestones", in the top left, has text as small as 16 point, which may be '
                      "hard to read when projected. Use at least 18 point for body text. "
                      "Confidence: definite.")


def test_grouped_copy_c3_c6():
    from slideproof.describe.copy import GROUPED
    assert GROUPED["C3"] == ("{c} text boxes have more text than fits",
                             "{c} text boxes on this slide have more text than fits. "
                             "Confidence: likely.")
    assert GROUPED["C6"] == ("{c} text boxes have small text",
                             "{c} text boxes on this slide have small text. Confidence: definite.")
