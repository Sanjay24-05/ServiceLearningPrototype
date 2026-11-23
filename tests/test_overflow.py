import pytest
from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn

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


def _set_body(path, auto_size=MSO_AUTO_SIZE.NONE, wrap=True, rotation=0):
    prs = Presentation(str(path))
    for sh in prs.slides[0].shapes:
        sh.text_frame.auto_size = auto_size
        sh.text_frame.word_wrap = wrap
        sh.rotation = rotation
    prs.save(path)
    return path


def _box_deck(tiny_deck, **body):
    # text box 1..5 in across, 1..3 in down, autofit off and wrapping on unless given
    return load_deck(_set_body(tiny_deck([
        {"kind": "textbox", "name": "box", "x": 1, "y": 1, "w": 4, "h": 2, "text": "Lots of text"}]),
        **body))


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


# ---- review fixes: autofit, wrap, rotation, boundaries, wording ----

def _emu_spans(deck, render, name, boxes):
    from slideproof.render.pdf import RenderedSpan
    from slideproof.units import Rect
    el = next(e for e in deck.slides[0].elements if e.name == name)
    render.linked = {el.id: [RenderedSpan("t", Rect(*b), "A", 18, (0, 0, 0)) for b in boxes]}
    return render


def _bottom_past(deck, render, emu):
    f = deck.slides[0].elements[0].frame
    return _emu_spans(deck, render, "box", [(f.x + 10, f.y + 10, f.w // 2, f.h - 10 + emu)])


def test_explicit_shape_autofit_skipped(tiny_deck, make_render):
    deck = _box_deck(tiny_deck, auto_size=MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT)
    assert deck.slides[0].elements[0].autofit == "grow"
    assert check_overflow(deck, _bottom_past(deck, make_render([[]]), inches(1))) == []


def test_no_autofit_still_flagged(tiny_deck, make_render):
    deck = _box_deck(tiny_deck)
    assert deck.slides[0].elements[0].autofit == "none"
    assert [f.check_id for f in check_overflow(deck, _bottom_past(deck, make_render([[]]), inches(1)))] == ["C3"]


def test_inherited_shrink_autofit_from_layout_skipped(tmp_path, make_render):
    prs = Presentation()
    layout = prs.slide_layouts[1]  # Title and Content
    lph = next(ph for ph in layout.placeholders if ph.placeholder_format.idx == 1)
    body_pr = lph._element.find(".//" + qn("a:bodyPr"))
    for child in list(body_pr):
        body_pr.remove(child)
    body_pr.append(body_pr.makeelement(qn("a:normAutofit"), {}))
    s = prs.slides.add_slide(layout)
    s.placeholders[1].text = "Lots of body text"
    s.placeholders[1].name = "box"
    path = tmp_path / "inherit.pptx"
    prs.save(path)
    deck = load_deck(path)
    el = next(e for e in deck.slides[0].elements if e.name == "box")
    assert el.autofit == "shrink"
    f = el.frame
    render = _emu_spans(deck, make_render([[]]), "box", [(f.x + 10, f.y + 10, f.w // 2, f.h + inches(1))])
    assert check_overflow(deck, render) == []


def test_unwrapped_text_ignores_right_overflow_but_checks_bottom(tiny_deck, make_render):
    deck = _box_deck(tiny_deck, wrap=False)
    assert deck.slides[0].elements[0].wrap is False
    render = _with_spans(deck, make_render([[]]), {"box": [(1.1, 1.1, 6.0, 0.4)]})
    assert check_overflow(deck, render) == []  # 2.1 in past the right: fine when unwrapped
    render = _with_spans(deck, make_render([[]]), {"box": [(1.1, 2.8, 6.0, 0.7)]})
    (f,) = check_overflow(deck, render)
    assert f.measurements["edge"] == "bottom"


def test_rotated_box_skipped(tiny_deck, make_render):
    deck = _box_deck(tiny_deck, rotation=90)
    assert check_overflow(deck, _bottom_past(deck, make_render([[]]), inches(1))) == []


def test_tolerance_boundary(tiny_deck, make_render):
    deck = _box_deck(tiny_deck)
    assert check_overflow(deck, _bottom_past(deck, make_render([[]]), 91440)) == []
    assert len(check_overflow(deck, _bottom_past(deck, make_render([[]]), 91441))) == 1


def test_overflow_skipped_when_render_failed(tiny_deck, make_render):
    deck = _box_deck(tiny_deck)
    render = _bottom_past(deck, make_render([[]]), inches(1))
    render.status = "failed"
    assert check_overflow(deck, render) == []


def test_copy_c3_whole_box(tiny_deck):
    from slideproof.describe import describe
    from slideproof.findings import Finding
    deck = _box_deck(tiny_deck)
    el = deck.slides[0].elements[0]
    d = describe(Finding("C3", 1, el.slide_id, (el.id,), "visible", "likely", 1.0,
                         {"edge": "bottom", "amount": 1.4}), deck)
    assert ("runs past the bottom of its box by more than the box's whole height, so it may "
            "spill onto other content or be cut off. Confidence: likely.") in d.full
    d = describe(Finding("C3", 1, el.slide_id, (el.id,), "visible", "likely", 1.0,
                         {"edge": "right", "amount": 1.0}), deck)
    assert "by more than the box's whole width, so it may" in d.full


@pytest.mark.soffice
def test_real_render_autofit_boxes_not_flagged(demo_deck, tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    from slideproof.analysis import analyse
    a = analyse(demo_deck[0], tmp_path / "demo")
    names = {e.id: e.name for s in a.deck.slides for e in s.elements}
    assert [(f.slide_index, names[f.element_ids[0]]) for f in a.findings if f.check_id == "C3"] == \
        [(6, "timeline-list")]
    out = tmp_path / "corpus"
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / "tools" / "make_test_decks.py"), str(out)],
                   check=True, capture_output=True)
    b = analyse(out / "constructs_deck.pptx", tmp_path / "constructs")
    assert b.render.status == "ok"
    assert [f for f in b.findings if f.check_id == "C3"] == []
