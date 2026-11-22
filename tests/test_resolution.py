from slideproof.checks.resolution import check_resolution
from slideproof.describe import describe
from slideproof.loader import load_deck


def test_demo_logo_low_resolution(demo_deck):
    d = load_deck(demo_deck[0])
    fs = check_resolution(d, None)
    assert [d.element(f.element_ids[0]).name for f in fs] == ["logo"]
    f = fs[0]
    assert f.severity == "visible" and f.confidence == "definite" and f.fix is None
    assert f.measurements["dpi"] == 50
    assert describe(f, d).headline == 'picture "Garden logo" is low resolution'
    assert "has about 50 pixels per inch" in describe(f, d).full


def test_minor_band(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 8.5, "h": 6.375,
                              "px": (800, 600)}]))
    fs = check_resolution(d, None)
    assert [f.severity for f in fs] == ["minor"] and fs[0].measurements["dpi"] == 94


def test_sharp_picture_not_flagged(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 4, "h": 3,
                              "px": (800, 600)}]))
    assert check_resolution(d, None) == []
