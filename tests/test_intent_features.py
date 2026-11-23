from io import BytesIO

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

from slideproof.checks.offslide import check_offslide
from slideproof.intent.features import FEATURES, features_for, raw_candidates
from slideproof.loader import load_deck
from slideproof.units import inches


def _png():
    buf = BytesIO()
    Image.new("RGB", (100, 100), (0x80, 0x80, 0x80)).save(buf, "PNG")
    buf.seek(0)
    return buf


def _prs(n_slides=1):
    prs = Presentation()
    prs.slide_width, prs.slide_height = inches(13.333), inches(7.5)
    blank = next(l for l in prs.slide_layouts if l.name == "Blank")
    return prs, [prs.slides.add_slide(blank) for _ in range(n_slides)]


def test_feature_order_is_stable():
    assert FEATURES[:3] == ["is_c1", "is_c2", "magnitude"] and len(FEATURES) == 21


def test_bleed_banner_is_a_raw_c1_candidate(tiny_deck):
    path = tiny_deck([{"kind": "picture", "name": "banner", "x": 0, "y": -0.5,
                       "w": 13.333, "h": 2}])
    deck = load_deck(path)
    assert check_offslide(deck) == []           # deliberate bleed: no finding
    cands = [c for c in raw_candidates(deck) if c.check_id == "C1"]
    assert len(cands) == 1
    assert abs(cands[0].magnitude - 0.25) < 0.01
    v = features_for("C1", cands[0].element_ids, cands[0].magnitude, deck)
    f = dict(zip(FEATURES, v))
    assert f["is_c1"] == 1 and f["kind_picture"] == 1 and f["edges_touched"] >= 3


def test_repeats_counts_same_object_on_other_slides(tmp_path):
    prs, slides = _prs(4)
    for s in slides:
        s.shapes.add_picture(_png(), inches(12), inches(-0.3), inches(1), inches(1))
    # slide 4's logo shifted 1 in: no longer the same spot
    slides[3].shapes[0].left = inches(11)
    p = tmp_path / "r.pptx"
    prs.save(p)
    deck = load_deck(p)
    c = [c for c in raw_candidates(deck) if c.slide_index == 1][0]
    f = dict(zip(FEATURES, features_for("C1", c.element_ids, c.magnitude, deck)))
    assert f["repeats"] == 2 and f["same_layout_repeats"] == 2
    c0 = [c for c in raw_candidates(deck) if c.slide_index == 2][0]
    f0 = dict(zip(FEATURES, features_for("C1", c0.element_ids, c0.magnitude, deck)))
    assert f0["repeats"] == 2
    # all four at one spot -> 3
    slides[3].shapes[0].left = inches(12)
    prs.save(p)
    deck = load_deck(p)
    c = [c for c in raw_candidates(deck) if c.slide_index == 1][0]
    assert dict(zip(FEATURES, features_for("C1", c.element_ids, c.magnitude, deck)))["repeats"] == 3


def test_c2_candidate_ignores_exemptions(tmp_path):
    prs, (s,) = _prs()
    s.shapes.add_picture(_png(), inches(1), inches(1), inches(6), inches(4))
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, inches(1), inches(4), inches(6), inches(1))
    band.fill.solid()
    band.fill.fore_color.rgb = RGBColor(0, 0, 0)
    band.text_frame.text = "Caption"
    p = tmp_path / "c.pptx"
    prs.save(p)
    deck = load_deck(p)
    c2 = [c for c in raw_candidates(deck) if c.check_id == "C2"]
    assert len(c2) == 1
    upper, lower = c2[0].element_ids
    assert deck.element(upper).kind == "shape" and deck.element(lower).kind == "picture"
    assert abs(c2[0].magnitude - 6 * 1 / (6 * 4)) < 0.01
    f = dict(zip(FEATURES, features_for("C2", c2[0].element_ids, c2[0].magnitude, deck)))
    assert f["is_c2"] == 1 and f["upper_inside_lower"] == 1 and f["lower_is_text"] == 0


def test_features_for_finding_matches_candidate(demo_deck):
    deck = load_deck(demo_deck[0])
    finding = next(f for f in check_offslide(deck)
                   if f.slide_index == 2 and f.check_id == "C1")
    cand = next(c for c in raw_candidates(deck)
                if c.check_id == "C1" and c.element_ids == finding.element_ids)
    a = features_for(finding.check_id, finding.element_ids, finding.magnitude, deck)
    b = features_for(cand.check_id, cand.element_ids, cand.magnitude, deck)
    assert a == b and len(a) == len(FEATURES)
