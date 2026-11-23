from slideproof.describe.coverage import checked_sentence
from slideproof.describe.layout_map import slide_map
from slideproof.loader import load_deck


def test_slide_map_demo_slide4(demo_deck):
    d = load_deck(demo_deck[0])
    lines = slide_map(d.slides[3], d)
    assert lines[0].startswith("The title, in the top")
    assert any(l.startswith('Picture "Team photo", in the centre') for l in lines)
    assert any(l.startswith('Picture "Garden logo", in the bottom right, small') for l in lines)
    assert len(lines) == 3


def test_slide_map_offslide_and_skipped(tiny_deck):
    d = load_deck(tiny_deck([
        {"kind": "textbox", "name": "a", "x": 1, "y": 1, "w": 4, "h": 1, "text": "On the slide"},
        {"kind": "textbox", "name": "b", "x": 20, "y": 1, "w": 2, "h": 1, "text": "Parked"}]))
    s = d.slides[0]
    s.skipped_shapes.append("weird")
    lines = slide_map(s, d)
    assert lines[0] == 'Text box "On the slide", in the top left, small'
    assert lines[1] == 'Text box "Parked", off the slide'
    assert lines[2] == "1 other object that could not be read"


def test_coverage_sentence_lists_eleven():
    s = checked_sentence()
    assert s.startswith("This version checks eleven things: ")
    assert "overlapping objects" in s and "empty or stray objects" in s
    for item in ("text that overflows its box", "small text", "low-contrast text",
                 "and content hidden behind other objects."):
        assert item in s
    assert s.endswith("Text inside charts and diagrams is not checked yet.")
    assert "11" not in s
