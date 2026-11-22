import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from slideproof import intent
from slideproof.checks import run_checks
from slideproof.loader import load_deck
from slideproof.prioritise import prioritise

ROOT = Path(__file__).resolve().parents[1]
NOTE = 'The "probably intentional" judgement is unavailable in this setup.'


def _judged(deck_path):
    deck = load_deck(deck_path)
    findings = run_checks(deck, None)
    return deck, findings, intent.judge(findings, deck)


def _intentional(findings, threshold):
    return [f for f in findings if f.measurements.get("intent_p", 0.0) >= threshold]


def test_demo_deck_nothing_moves(demo_deck):
    deck, before, (after, note) = _judged(demo_deck[0])
    assert note is None
    assert len(after) == len(before)
    assert _intentional(after, intent.threshold()) == []
    assert prioritise(after, len(deck.slides), intent.threshold()).intentional == []
    assert any("intent_p" in f.measurements for f in after)


def test_constructs_deck_nothing_moves(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_test_decks.py"), str(tmp_path)],
                   check=True, capture_output=True)
    t = intent.threshold()
    for name in ("constructs_deck.pptx", "lecture_4x3.pptx"):
        deck, _, (after, note) = _judged(tmp_path / name)
        assert note is None
        assert prioritise(after, len(deck.slides), t).intentional == [], name


def _logo_deck(path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = next(l for l in prs.slide_layouts if l.name == "Blank")
    for _ in range(6):
        s = prs.slides.add_slide(blank)
        buf = BytesIO()
        Image.new("RGB", (100, 100), (0x30, 0x60, 0x90)).save(buf, "PNG")
        buf.seek(0)
        s.shapes.add_picture(buf, Inches(-0.15), Inches(-0.15), Inches(0.9), Inches(0.9)).name = "logo"
    prs.save(path)
    return path


def test_deliberate_pattern_moves(tmp_path):
    deck, findings, (after, note) = _judged(_logo_deck(tmp_path / "logo.pptx"))
    t = intent.threshold()
    c1 = [f for f in after if f.check_id == "C1"]
    assert c1, "the spilling logo should raise C1"
    r = prioritise(after, len(deck.slides), t)
    assert {f.check_id for f in r.intentional} == {"C1"}
    assert r.intentional and not [f for f in r.visible + r.minor if f.check_id == "C1"]
    reasons = r.intentional[0].measurements["intent_reasons"]
    assert "repeats" in reasons and len(reasons) <= 2


def test_text_over_text_is_not_judged(tmp_path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = next(l for l in prs.slide_layouts if l.name == "Blank")
    s = prs.slides.add_slide(blank)
    for y in (1.0, 1.3):
        s.shapes.add_textbox(Inches(1), Inches(y), Inches(6), Inches(1)).text_frame.text = "Some words here"
    p = tmp_path / "tt.pptx"
    prs.save(p)
    deck, before, (after, _) = _judged(p)
    c2 = [f for f in after if f.check_id == "C2"]
    assert c2 and all("intent_p" not in f.measurements for f in c2)


def test_missing_model_is_a_noop(monkeypatch, demo_deck, tmp_path):
    monkeypatch.setattr(intent, "MODEL_DIR", tmp_path)
    intent._cache.clear()
    try:
        deck = load_deck(demo_deck[0])
        before = run_checks(deck, None)
        after, note = intent.judge(before, deck)
        assert note == NOTE
        assert after == before and all("intent_p" not in f.measurements for f in after)
    finally:
        intent._cache.clear()


def test_version_mismatch_is_a_noop(monkeypatch, demo_deck, tmp_path):
    meta = json.loads((intent.MODEL_DIR / "features.json").read_text())
    meta["sklearn"] = "0.0.1"
    (tmp_path / "features.json").write_text(json.dumps(meta))
    (tmp_path / "model.joblib").write_bytes((intent.MODEL_DIR / "model.joblib").read_bytes())
    monkeypatch.setattr(intent, "MODEL_DIR", tmp_path)
    intent._cache.clear()
    try:
        deck = load_deck(demo_deck[0])
        _, note = intent.judge(run_checks(deck, None), deck)
        assert note == NOTE
    finally:
        intent._cache.clear()


def test_grouping_never_mixes_tiers(make_finding):
    fs = [make_finding("C1", 1, f"e{i}", "visible", 0.5) for i in range(6)]
    for f in fs[:3]:
        f.measurements = {"intent_p": 0.95}
    r = prioritise(fs, 1, 0.8)
    assert len(r.intentional) == 3 and len(r.visible) == 3
    assert all(f.measurements.get("grouped") is None for f in r.intentional + r.visible)
    # and a tier that is itself large still groups, only with its own members
    fs = [make_finding("C1", 1, f"e{i}", "visible", 0.5) for i in range(12)]
    for f in fs[:6]:
        f.measurements = {"intent_p": 0.95}
    r = prioritise(fs, 1, 0.8)
    assert [f.measurements["grouped"] for f in r.intentional] == [6]
    assert [f.measurements["grouped"] for f in r.visible] == [6]
    assert set(r.intentional[0].element_ids) == {f"e{i}" for i in range(6)}


def test_harmless_warning_during_load_does_not_disable_model(monkeypatch):
    import joblib
    import warnings
    real = joblib.load

    def noisy(*a, **k):
        warnings.warn("harmless", DeprecationWarning)
        return real(*a, **k)

    monkeypatch.setattr(joblib, "load", noisy)
    intent._cache.clear()
    try:
        assert intent._load() is not None
    finally:
        intent._cache.clear()


def test_version_warning_during_load_disables_model(monkeypatch):
    import joblib
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    real = joblib.load

    def noisy(*a, **k):
        warnings.warn(InconsistentVersionWarning(
            estimator_name="x", current_sklearn_version="1", original_sklearn_version="0"))
        return real(*a, **k)

    monkeypatch.setattr(joblib, "load", noisy)
    intent._cache.clear()
    try:
        assert intent._load() is None
    finally:
        intent._cache.clear()


def test_judged_findings_carry_repeat_count(tmp_path):
    _, _, (after, _) = _judged(_logo_deck(tmp_path / "logo.pptx"))
    c1 = [f for f in after if f.check_id == "C1"]
    assert all(f.measurements["intent_repeats"] == 5 for f in c1)


# ---------------------------------------------------------------- final review fixes
def _dup_deck(path, build, n=5):
    """n Title Only slides with a title and a text box; build(slide) adds the same mistake to each."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    lay = next(l for l in prs.slide_layouts if l.name == "Title Only")
    for i in range(n):
        s = prs.slides.add_slide(lay)
        s.shapes.title.text = f"Topic {i + 1}"
        s.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(6), Inches(4)).text_frame.text = "Point one"
        build(s)
    prs.save(path)
    return path


def _png():
    buf = BytesIO()
    Image.new("RGB", (120, 120), (40, 90, 160)).save(buf, "PNG")
    buf.seek(0)
    return buf


def _moved_mistakes(path):
    deck, _, (after, note) = _judged(path)
    assert note is None
    r = prioritise(after, len(deck.slides), intent.threshold())
    return [f for f in r.intentional if any(deck.element(e).name == "MISTAKE" for e in f.element_ids)], r


def test_duplicated_text_box_off_slide_never_moves(tmp_path):
    def build(s):
        t = s.shapes.add_textbox(Inches(10.5), Inches(3), Inches(3.8), Inches(1))
        t.text_frame.text = "Source: survey 2026"
        t.name = "MISTAKE"
    moved, r = _moved_mistakes(_dup_deck(tmp_path / "tb.pptx", build))
    assert r.intentional == []


def test_duplicated_dragged_title_never_moves(tmp_path):
    def build(s):
        s.shapes.title.left = Inches(9)
        s.shapes.title.name = "MISTAKE"
    moved, r = _moved_mistakes(_dup_deck(tmp_path / "title.pptx", build))
    assert r.intentional == []


def test_text_c1_is_not_judged(tmp_path):
    def build(s):
        from pptx.enum.shapes import MSO_SHAPE
        sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(6.9), Inches(13.333), Inches(1.0))
        sh.text_frame.text = "Group 4 - Environmental Studies"
        sh.name = "MISTAKE"
    deck, _, (after, _) = _judged(_dup_deck(tmp_path / "band.pptx", build, n=1))
    c1 = [f for f in after if f.check_id == "C1"]
    assert c1 and all("intent_p" not in f.measurements for f in c1)


def test_duplicated_picture_half_off_right_edge_stays(tmp_path):
    def build(s):
        s.shapes.add_picture(_png(), Inches(12.6), Inches(3.0), Inches(1.4), Inches(1.4)).name = "MISTAKE"
    moved, _ = _moved_mistakes(_dup_deck(tmp_path / "pic.pptx", build))
    assert moved == [], [round(f.measurements["intent_p"], 3) for f in moved]


def test_prediction_failure_is_a_noop(monkeypatch, tmp_path):
    model, _ = intent._load()

    def boom(*a, **k):
        raise ValueError("broken model")

    monkeypatch.setattr(model, "predict_proba", boom)
    deck = load_deck(_logo_deck(tmp_path / "logo.pptx"))
    before = run_checks(deck, None)
    after, note = intent.judge(before, deck)
    assert note == NOTE
    assert after == before and all("intent_p" not in f.measurements for f in after)


def test_behind_reason_rules():
    from slideproof.intent.features import FEATURES

    def vec(**kv):
        v = dict.fromkeys(FEATURES, 0.0)
        v.update(has_text=1.0, **kv)
        return [v[k] for k in FEATURES]
    assert "behind" in intent._reasons(vec(is_c1=1.0, z_rank=0.0, elements_on_slide=4.0))
    assert "behind" not in intent._reasons(vec(is_c1=1.0, z_rank=0.0, elements_on_slide=1.0))
    assert "behind" not in intent._reasons(vec(is_c2=1.0, z_rank=0.0, elements_on_slide=4.0))


def test_trainer_held_out_uses_shipped_judgeable(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("train_intent_model", ROOT / "tools" / "train_intent_model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["train_intent_model"] = mod
    spec.loader.exec_module(mod)

    class Always:
        def predict_proba(self, X):
            import numpy as np
            return np.array([[0.0, 1.0]] * len(X))

    def build(s):
        t = s.shapes.add_textbox(Inches(10.5), Inches(3), Inches(3.8), Inches(1))
        t.text_frame.text = "Source: survey 2026"
    deck = load_deck(_dup_deck(tmp_path / "tb.pptx", build, n=1))
    assert any(f.check_id == "C1" for f in run_checks(deck, None))
    assert mod._judge(deck, Always(), 0.8, [])["judged"] == 0


def test_app_start_loads_model(tmp_path, monkeypatch):
    from slideproof.web.app import create_app
    intent._cache.clear()
    create_app(tmp_path / "runs")
    assert intent._cache.get("dir") == intent.MODEL_DIR
