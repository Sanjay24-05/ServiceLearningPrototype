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


@pytest.mark.soffice
@pytest.mark.parametrize("template", ["Blue_Curve", "Focus", "Freshes", "Grey_Elegant"])
def test_template_decks_have_no_findings(tmp_path, template):
    src = TEMPLATES / f"{template}.otp"
    if not src.exists():
        pytest.skip(f"LibreOffice template {template} not installed")
    shutil.copy(src, tmp_path)
    subprocess.run([str(find_soffice()), "--headless", "--norestore",
                    f"-env:UserInstallation={(tmp_path / 'lo').as_uri()}",
                    "--convert-to", "pptx", "--outdir", str(tmp_path), str(tmp_path / src.name)],
                   check=True, capture_output=True, timeout=120)
    # Templates' sample slides keep their placeholders empty. Those are reported as minor,
    # removable "empty text box"/"empty title" notes (spec C10, plan Review Focus 2); nothing else
    # may fire — in particular no visible finding from decorative artwork (Review Focus 1).
    d = load_deck(tmp_path / f"{template}.pptx")
    others = [f for f in run_checks(d, None)
              if not (f.check_id == "C10" and f.measurements["kind"] == "empty"
                      and f.severity == "minor")]
    assert others == []
