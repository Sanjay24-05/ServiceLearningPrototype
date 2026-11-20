import hashlib

import pytest
from pptx import Presentation

from slideproof.checks import run_checks
from slideproof.fixes import apply_fixes
from slideproof.fixes.writer import set_frame
from slideproof.loader import load_deck
from slideproof.units import Rect


def _elem(deck, name):
    return next(e for s in deck.slides for e in s.elements if e.name == name)


def test_apply_f1_f2_to_copy(demo_deck, tmp_path):
    src = demo_deck[0]
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    fixes = [f.fix for f in run_checks(load_deck(src), None) if f.fix]
    assert {f.kind for f in fixes} == {"F1", "F2"}
    out = tmp_path / "sub" / "demo (checked).pptx"
    applied = apply_fixes(src, out, fixes)
    assert [f.kind for f in applied] == ["F2", "F1"]
    reloaded = load_deck(out)
    f1 = next(f for f in fixes if f.kind == "F1")
    assert _elem(reloaded, "agenda-box").frame == Rect.from_list(f1.params["frame"])
    photo = _elem(reloaded, "team-photo").frame
    assert abs(photo.w / photo.h - 800 / 600) / (800 / 600) < 0.01
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before


def test_apply_refuses_to_overwrite_original(demo_deck):
    with pytest.raises(ValueError):
        apply_fixes(demo_deck[0], demo_deck[0], [])


def test_set_frame_on_inherited_placeholder(demo_deck, tmp_path):
    deck = load_deck(demo_deck[0])
    slide = deck.slides[1]
    title = next(e for e in slide.elements if e.name == "slide-title")
    new = Rect(1000000, 500000, 5000000, 800000)
    out = tmp_path / "t.pptx"
    prs = Presentation(str(demo_deck[0]))
    set_frame(prs, title.slide_id, title.shape_id, new)
    prs.save(str(out))
    assert _elem(load_deck(out), "slide-title").frame == new
    with pytest.raises(KeyError):
        set_frame(prs, title.slide_id, 99999, new)
