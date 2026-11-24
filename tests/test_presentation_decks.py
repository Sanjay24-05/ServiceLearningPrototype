"""The two decks used in the faculty presentation behave as the demo script says."""
import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Pt

from slideproof.analysis import analyse
from tools.make_logo_deck import build_logo_deck
from tools.make_talk_deck import build_talk_deck

TITLES = ["Slide Proof", "It sounds fine. It isn't.", "Who it is for",
          "Mistake or on purpose?", "What we measured", "What comes next"]


@pytest.mark.parametrize("rendering", [False, pytest.param(True, marks=pytest.mark.soffice)])
def test_logo_deck_moves_logos_and_keeps_the_photo(tmp_path, monkeypatch, rendering):
    if not rendering:
        monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing-soffice.exe"))
    a = analyse(build_logo_deck(tmp_path / "logo.pptx"), tmp_path / "run")
    assert a.render.status == ("ok" if rendering else "skipped")
    assert sorted(f.slide_index for f in a.report.intentional) == [1, 2, 3, 4, 5, 6]
    assert [(f.check_id, f.slide_index) for f in a.report.visible] == [("C1", 4)]
    assert a.report.minor == []


def test_talk_deck_text_pictures_and_notes(tmp_path):
    prs = Presentation(str(build_talk_deck(tmp_path / "talk.pptx")))
    assert [s.shapes.title.text for s in prs.slides] == TITLES
    for s in prs.slides:
        assert s.notes_slide.notes_text_frame.text.strip()
        for sh in s.shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                assert sh._element.nvPicPr.cNvPr.get("descr")
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        assert r.font.size is not None and r.font.size >= Pt(24), r.text


def test_talk_deck_states_the_limits(tmp_path):
    prs = Presentation(str(build_talk_deck(tmp_path / "talk.pptx")))
    text = " ".join(sh.text_frame.text for sh in prs.slides[4].shapes if sh.has_text_frame)
    for needed in ("97.6%", "94.3%", "120 synthetic decks", "mildly optimistic",
                   "Untested on real-world decks", "No blind user has tested it yet."):
        assert needed in text


@pytest.mark.soffice
def test_talk_deck_passes_slide_proof(tmp_path):
    a = analyse(build_talk_deck(tmp_path / "talk.pptx"), tmp_path / "run")
    assert a.render.status == "ok"
    assert a.report.visible == [] and a.report.minor == []
