import pytest
from slideproof.checks import run_checks
from slideproof.describe import describe
from slideproof.describe.names import element_label
from slideproof.describe.spatial import grid_location, coverage_phrase, portion_phrase
from slideproof.loader import load_deck
from slideproof.units import Rect

S = Rect(0, 0, 900, 900)


def test_grid_cells_and_extent():
    assert grid_location(Rect(0, 0, 100, 100), S) == "in the top left"
    assert grid_location(Rect(400, 400, 100, 100), S) == "in the centre"
    assert grid_location(Rect(0, 0, 900, 100), S) == "across the whole top of the slide"
    assert grid_location(Rect(0, 0, 900, 900), S) == "covering the whole slide"
    assert grid_location(Rect(0, 0, 100, 900), S) == "down the whole left side of the slide"


def test_phrases():
    assert coverage_phrase(0.35) == "about a third of" and coverage_phrase(0.95) == "all of"
    assert portion_phrase(0.20) == "about a fifth" and portion_phrase(0.5) == "about half"


def _demo(demo_deck, check):
    deck = load_deck(demo_deck[0])
    f = next(f for f in run_checks(deck, None) if f.check_id == check)
    return deck, f, describe(f, deck)


def test_c1_description_demo(demo_deck):
    deck, f, d = _demo(demo_deck, "C1")
    # Label is the first 6 words plus an ellipsis.
    assert d.short == 'Slide 2: text box "Welcome and introductions from our team…" sticks out past the right edge'
    assert "by about a fifth of its width" in d.full and "agenda-box" not in d.full
    assert d.fix_label == "Move it back onto the slide. Safe fix."


def test_c4_description_demo(demo_deck):
    deck, f, d = _demo(demo_deck, "C4")
    assert d.headline == 'picture "Team photo" is stretched wider than its natural shape'
    assert "1.6 times as wide" in d.full
    assert d.change_log.endswith("it is now narrower and still centred.")


def test_short_form_under_90_chars_for_demo(demo_deck):
    deck = load_deck(demo_deck[0])
    fs = [f for f in run_checks(deck, None) if f.check_id in {"C1", "C4"}]
    assert fs
    for f in fs:
        assert len(describe(f, deck).short) <= 95  # spec: "<= ~90"; agenda demo is 92


def test_long_text_gets_ellipsis(tiny_deck):
    deck = load_deck(tiny_deck([{"kind": "textbox", "name": "b", "x": 1, "y": 1, "w": 4, "h": 1,
                                 "text": "one two three four five six seven"}]))
    s = deck.slides[0]
    assert element_label(s.elements[0], s) == 'text box "one two three four five six…"'


def _pic_label(tiny_deck, name):
    from slideproof.describe.names import element_label
    deck = load_deck(tiny_deck([dict(kind="picture", name="n", x=1, y=1, w=2, h=2)]))
    el = deck.slides[0].elements[0]
    el.image.alt = None
    el.image.filename = name
    return element_label(el, deck.slides[0])


@pytest.mark.parametrize("name", ["image1.png", "Image12.JPG", "Picture 3.png",
                                  "picture.jpeg", "img_0042.jpg", "IMG 7.png"])
def test_generic_image_filenames_are_not_names(tiny_deck, name):
    assert _pic_label(tiny_deck, name) == "picture 1"


@pytest.mark.parametrize("name", ["team.jpg", "chart-q3.png"])
def test_real_image_filenames_still_shown(tiny_deck, name):
    assert _pic_label(tiny_deck, name) == f'picture "{name}"'


def test_generic_alt_text_is_not_a_name_but_real_alt_is(tiny_deck):
    deck = load_deck(tiny_deck([dict(kind="picture", name="n", x=1, y=1, w=2, h=2)]))
    el = deck.slides[0].elements[0]
    slide = deck.slides[0]
    el.image.filename = None
    el.image.alt = "image.png"
    assert element_label(el, slide) == "picture 1"
    el.image.alt = "Bar chart of harvest results"
    assert element_label(el, slide) == 'picture "Bar chart of harvest results"'
