from tests.groundtruth import load_expected, match
from slideproof.loader import load_deck
from slideproof.checks import run_checks
from slideproof.fixes.geometry import pull_on_slide, restore_proportions
from slideproof.units import Rect, inches

SLIDE = Rect(0, 0, 12192000, 6858000)

def test_demo_deck_c1_c4_match_ground_truth(demo_deck):
    deck = load_deck(demo_deck[0])
    found = [f for f in run_checks(deck, None) if f.check_id in {"C1", "C4"}]
    tp, fp, missed = match(found, deck, load_expected(demo_deck[1], {"C1", "C4"}))
    assert (len(fp), len(missed)) == (0, 0) and len(tp) == 2

def test_c1_agenda_box_measurements(demo_deck):
    deck = load_deck(demo_deck[0])
    f = next(f for f in run_checks(deck, None) if f.check_id == "C1")
    assert f.severity == "visible" and abs(f.measurements["edges"]["right"] - 0.20) < 0.02
    assert f.fix.kind == "F1" and f.fix.safety == "safe"

def test_c1_on_4_3_slide(tiny_deck):
    deck = load_deck(tiny_deck([{"kind": "textbox", "name": "b", "x": 8, "y": 1, "w": 4, "h": 1, "text": "hi"}],
                               slide_w=inches(10), slide_h=inches(7.5)))
    f = run_checks(deck, None)[0]
    assert f.check_id == "C1" and abs(f.measurements["outside"] - 0.5) < 0.01

def test_c1_ignores_full_bleed_background(demo_deck):
    deck = load_deck(demo_deck[0])
    assert not [f for f in run_checks(deck, None) if f.slide_index == 8 and f.check_id == "C1"]

def test_c4_logo_not_flagged_and_photo_ratio(demo_deck):
    deck = load_deck(demo_deck[0])
    c4 = [f for f in run_checks(deck, None) if f.check_id == "C4"]
    assert len(c4) == 1 and round(c4[0].measurements["ratio"], 1) == 1.6
    assert c4[0].measurements["direction"] == "wide"

def test_pull_on_slide_translates_with_margin():
    new, scaled = pull_on_slide(Rect(inches(10.13), inches(1.5), inches(4), inches(3)),
                                Rect(inches(10.13), inches(1.5), inches(4), inches(3)), SLIDE, rotated=False)
    assert not scaled and new.right == SLIDE.w - inches(0.2) and new.w == inches(4)

def test_pull_on_slide_scales_oversized():
    big = Rect(0, 0, inches(20), inches(5))
    new, scaled = pull_on_slide(big, big, SLIDE, rotated=False)
    assert scaled and new.w == SLIDE.w - 2 * inches(0.2) and abs(new.w / new.h - 4.0) < 0.01

def test_pull_on_slide_rotated_needing_scale_returns_none():
    big = Rect(0, 0, inches(20), inches(5))
    assert pull_on_slide(big, big, SLIDE, rotated=True) is None

def test_restore_proportions_keeps_centre_and_larger_side():
    r = restore_proportions(Rect(0, 0, 1600, 600), 800 / 600)
    assert r.w == 1600 and r.h == 1200 and r.center == (800, 300)
