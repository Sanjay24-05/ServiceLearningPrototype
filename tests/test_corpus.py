"""Answer-key and realistic-deck regression for the checks implemented so far (M2)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from slideproof.checks import run_checks
from slideproof.loader import load_deck
from slideproof.render.soffice import find_soffice
from tests.groundtruth import load_expected, match

IMPLEMENTED = {"C1", "C2", "C4", "C5", "C8", "C9", "C10"}
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


def test_demo_deck_matches_ground_truth(demo_deck):
    deck = load_deck(demo_deck[0])
    found = [f for f in run_checks(deck, None) if f.check_id in IMPLEMENTED]
    tp, fp, missed = match(found, deck, load_expected(demo_deck[1], IMPLEMENTED))
    assert fp == [] and missed == []


@pytest.mark.parametrize("name", ["clean_student_deck.pptx", "long_40_slides.pptx",
                                  "linked_and_background.pptx"])
def test_clean_corpus_has_no_findings(corpus_decks, name):
    assert _summary(corpus_decks / name) == set()


def test_constructs_and_lecture_expected(corpus_decks):
    expected = json.loads((corpus_decks / "expected.json").read_text())
    for name in ("constructs_deck.pptx", "lecture_4x3.pptx"):
        assert _summary(corpus_decks / name) == {tuple(x) for x in expected[name]}, name


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


@pytest.mark.soffice
@pytest.mark.parametrize("template", TEMPLATE_NAMES or ["none-installed"])
def test_template_decks_have_no_findings(template_decks, template):
    # Templates' sample slides keep their placeholders empty. Those are reported as minor notes
    # (empty placeholder, or "this slide has no title"; spec C10, plan Review Focus 2). Nothing
    # else may fire — in particular no visible finding from decorative artwork or title layouts.
    d = load_deck(template_decks / f"{template}.pptx")
    def allowed(f):
        # C1/C4 (M1 checks) are out of this guard's scope: two templates have real or deliberate
        # cases (Growing Liberty's photo is 6% squashed; Yellow Idea runs a half-donut off the
        # edge on purpose). See docs/testing/2026-11-22-m2-audit.md.
        if f.check_id in ("C1", "C4"):
            return True
        placeholder_note = (f.measurements.get("kind") in ("empty", "no_title")
                            or "grouped" in f.measurements)
        return f.check_id == "C10" and f.severity == "minor" and placeholder_note

    others = [(f.check_id, f.slide_index, f.severity, d.element(f.element_ids[0]).name)
              for f in run_checks(d, None) if not allowed(f)]
    assert others == []
