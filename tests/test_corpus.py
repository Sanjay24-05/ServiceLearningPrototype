"""Answer-key and realistic-deck regression: the estimate-only checks (M2) everywhere, and
every check with real LibreOffice rendering (M3, soffice-marked)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from slideproof.analysis import analyse
from slideproof.checks import run_checks
from slideproof.loader import load_deck
from slideproof.render.soffice import find_soffice
from tests.groundtruth import load_expected, match

IMPLEMENTED = {"C1", "C2", "C4", "C5", "C8", "C9", "C10"}
# With LibreOffice the rendered checks run too (C11 runs either way, but the demo has none).
IMPLEMENTED_RENDERED = IMPLEMENTED | {"C3", "C6", "C7", "C11"}
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(r"C:\Program Files\LibreOffice\share\template\common\presnt")


@pytest.fixture(scope="session")
def corpus_decks(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_test_decks.py"), str(out)],
                   check=True, capture_output=True)
    return out


def _summary(deck_path):
    d = load_deck(deck_path)
    return {(f.check_id, f.slide_index, d.element(f.element_ids[0]).name) for f in run_checks(d, None)}


def _rendered(deck_path, run_dir):
    a = analyse(deck_path, run_dir)
    assert a.render.status == "ok", a.render.reason
    return a


def _rendered_summary(deck_path, run_dir):
    a = _rendered(deck_path, run_dir)
    return {(f.check_id, f.slide_index, a.deck.element(f.element_ids[0]).name) for f in a.findings}


def test_demo_deck_matches_ground_truth(demo_deck):
    deck = load_deck(demo_deck[0])
    found = [f for f in run_checks(deck, None) if f.check_id in IMPLEMENTED]
    tp, fp, missed = match(found, deck, load_expected(demo_deck[1], IMPLEMENTED))
    assert fp == [] and missed == []


@pytest.mark.soffice
def test_demo_deck_matches_ground_truth_with_rendering(demo_deck, tmp_path):
    a = _rendered(demo_deck[0], tmp_path)
    found = [f for f in a.findings if f.check_id in IMPLEMENTED_RENDERED]
    tp, fp, missed = match(found, a.deck, load_expected(demo_deck[1], IMPLEMENTED_RENDERED))
    assert fp == [] and missed == []
    (c3,) = [f for f in a.findings if f.check_id == "C3"]
    assert (c3.slide_index, c3.severity, c3.confidence) == (6, "visible", "likely")


CLEAN = ["clean_student_deck.pptx", "long_40_slides.pptx", "linked_and_background.pptx"]


@pytest.mark.parametrize("name", CLEAN)
def test_clean_corpus_has_no_findings(corpus_decks, name):
    assert _summary(corpus_decks / name) == set()


@pytest.mark.soffice
@pytest.mark.parametrize("name", CLEAN)
def test_clean_corpus_has_no_findings_with_rendering(corpus_decks, tmp_path, name):
    assert _rendered_summary(corpus_decks / name, tmp_path) == set()


def test_constructs_and_lecture_expected(corpus_decks):
    expected = json.loads((corpus_decks / "expected.json").read_text())
    for name in ("constructs_deck.pptx", "lecture_4x3.pptx"):
        assert _summary(corpus_decks / name) == {tuple(x) for x in expected[name]}, name


# Rendered findings on top of expected.json. constructs_deck slide 2 has three python-pptx default
# rounded rectangles: white 18 pt text on the default theme's mid-blue gradient measures 2.6:1
# where 3:1 is needed, a real (borderline) WCAG failure, kept on purpose.
RENDERED_EXTRA = {"constructs_deck.pptx": {("C7", 2, f"Rounded Rectangle {n}") for n in (3, 4, 5)},
                  "lecture_4x3.pptx": set()}


@pytest.mark.soffice
def test_constructs_and_lecture_expected_with_rendering(corpus_decks, tmp_path):
    # Also guards that a "shrink text on overflow" title LibreOffice did not shrink is not
    # reported as covered by the picture under it (constructs_deck slides 4 and 5).
    expected = json.loads((corpus_decks / "expected.json").read_text())
    for name in ("constructs_deck.pptx", "lecture_4x3.pptx"):
        got = _rendered_summary(corpus_decks / name, tmp_path / name)
        assert got == {tuple(x) for x in expected[name]} | RENDERED_EXTRA[name], name


TEMPLATE_NAMES = sorted(t.stem for t in TEMPLATES.glob("*.otp")) if TEMPLATES.exists() else []


@pytest.fixture(scope="session")
def template_decks(tmp_path_factory):
    """Every installed LibreOffice presentation template, converted to .pptx in one soffice call."""
    soffice = find_soffice()
    if soffice is None or not TEMPLATE_NAMES:
        pytest.skip("LibreOffice or its templates are not installed")
    out = tmp_path_factory.mktemp("templates")
    for name in TEMPLATE_NAMES:
        shutil.copy(TEMPLATES / f"{name}.otp", out)
    subprocess.run([str(soffice), "--headless", "--norestore",
                    f"-env:UserInstallation={(out / 'lo').as_uri()}",
                    "--convert-to", "pptx", "--outdir", str(out),
                    *[str(out / f"{n}.otp") for n in TEMPLATE_NAMES]],
                   check=True, capture_output=True, timeout=600)
    return out


# Visible low contrast the templates really have, measured with rendering and checked by eye
# against the rendered slides and the template XML (Task 6 report). C7 measures these correctly;
# they are design choices (decorative step numbers), not false alarms, so they are listed here
# rather than exempted in the check. (slide, text)
# Slide numbers with low contrast (Blue_Curve, Focus, Lights, Midnightblue, Sunset) are minor:
# C7 reports footer, date and slide-number placeholders as minor, which this guard allows.
KNOWN_LOW_CONTRAST = {
    "Candy": {(2, "2"), (6, "2"), (10, "3")},       # white on #60C4E4 2.0:1; purple on amber 2.9:1
    "Growing_Liberty": {(2, "01"), (2, "02"), (2, "03"), (2, "04"),   # #62CF51 on white, 1.9:1
                        (4, "1"), (4, "2"), (4, "3"), (4, "4")},      # white on #41AEEB, 2.4:1
}


@pytest.mark.soffice
@pytest.mark.parametrize("template", TEMPLATE_NAMES or ["none-installed"])
def test_template_decks_have_no_findings(template_decks, template, tmp_path):
    # Templates' sample slides keep their placeholders empty. Those are reported as minor notes
    # (empty placeholder, or "this slide has no title"; spec C10, plan Review Focus 2). Nothing
    # else may fire — in particular no visible finding from decorative artwork or title layouts.
    a = _rendered(template_decks / f"{template}.pptx", tmp_path)
    d = a.deck
    def allowed(f):
        # C1/C4 (M1 checks) are out of this guard's scope: two templates have real or deliberate
        # cases (Growing Liberty's photo is 6% squashed; Yellow Idea runs a half-donut off the
        # edge on purpose). See docs/testing/2026-11-22-m2-audit.md.
        if f.check_id in ("C1", "C4"):
            return True
        placeholder_note = (f.measurements.get("kind") in ("empty", "no_title")
                            or "grouped" in f.measurements)
        # Small template text (captions, sample labels) may be a minor note; never visible.
        if f.check_id == "C6" and f.severity == "minor":
            return True
        # Low contrast on footer, date or slide number is minor (template furniture).
        if f.check_id == "C7" and f.severity == "minor":
            return True
        return f.check_id == "C10" and f.severity == "minor" and placeholder_note

    others = [(f.check_id, f.slide_index, f.severity, d.element(f.element_ids[0]).name)
              for f in a.findings if not allowed(f)
              and not (f.check_id == "C7" and f.severity == "visible")]
    assert others == []
    low_contrast = {(f.slide_index, d.element(f.element_ids[0]).text.strip())
                    for f in a.findings if f.check_id == "C7" and f.severity == "visible"}
    assert low_contrast == KNOWN_LOW_CONTRAST.get(template, set())
