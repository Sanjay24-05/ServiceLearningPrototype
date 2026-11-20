from pathlib import Path

import fitz
import pytest

from slideproof.render import pipeline
from slideproof.render import render_deck
from slideproof.render.pdf import RenderedSlide, read_pdf
from slideproof.render.soffice import RenderError, find_soffice
from slideproof.units import Rect


def test_find_soffice_respects_missing_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "nope.exe"))
    assert find_soffice() is None


def test_render_skipped_without_libreoffice(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "nope.exe"))
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "skipped" and r.reason == "LibreOffice is not installed"
    assert r.slides == [None] * 8


@pytest.mark.soffice
def test_render_demo_deck_spans_and_pngs(tmp_path, demo_deck):
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "ok" and len(r.slides) == 8
    assert all(s.png_path.exists() for s in r.slides)
    agenda = [sp for sp in r.slides[1].spans if sp.text.strip()]
    assert agenda and all(sp.size_pt > 0 for sp in agenda)
    grey = [sp for sp in r.slides[6].spans if sp.rgb == (0xBB, 0xBB, 0xBB)]
    assert grey


def test_read_pdf_parses_synthetic_pdf(tmp_path):
    pdf = tmp_path / "s.pdf"
    doc = fitz.open()
    page = doc.new_page(width=960, height=540)
    page.insert_text((72, 144), "Hello", fontsize=24, color=(0xBB / 255,) * 3)
    doc.save(pdf)
    doc.close()
    png_dir = tmp_path / "png"
    slides = read_pdf(pdf, png_dir, 12192000, 6858000)
    assert len(slides) == 1
    assert slides[0].png_path.exists()
    hello = [s for s in slides[0].spans if s.text == "Hello"]
    assert hello
    sp = hello[0]
    assert sp.size_pt == 24
    assert sp.rgb == (0xBB, 0xBB, 0xBB)
    assert abs(sp.bbox.x - 72 * 12700) <= 12700


def _fake_slides(n, tmp_path):
    return [RenderedSlide(i, tmp_path / f"{i}.png", []) for i in range(n)]


def _fake_env(monkeypatch, tmp_path, pages):
    monkeypatch.setattr(pipeline, "find_soffice", lambda: Path("dummy"))
    monkeypatch.setattr(pipeline, "convert_to_pdf",
                        lambda *a, **k: tmp_path / "x.pdf")
    monkeypatch.setattr(pipeline, "read_pdf",
                        lambda *a, **k: _fake_slides(pages, tmp_path))
    monkeypatch.setattr(pipeline, "slide_size", lambda p: (12192000, 6858000))


def test_render_failed_when_conversion_errors(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setattr(pipeline, "find_soffice", lambda: Path("dummy"))

    def boom(*a, **k):
        raise RenderError("bad")
    monkeypatch.setattr(pipeline, "convert_to_pdf", boom)
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "failed"
    assert r.reason == "LibreOffice could not render this file"
    assert r.slides == [None] * 8


def test_render_failed_on_timeout(monkeypatch, tmp_path, demo_deck):
    import subprocess
    monkeypatch.setattr(pipeline, "find_soffice", lambda: Path("dummy"))

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("soffice", 1)
    monkeypatch.setattr(pipeline, "convert_to_pdf", slow)
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "failed" and r.reason == "LibreOffice took too long"


def test_render_page_mapping_with_hidden_slides(monkeypatch, tmp_path, demo_deck):
    _fake_env(monkeypatch, tmp_path, 7)
    hidden = [False, False, True] + [False] * 5
    r = render_deck(demo_deck[0], tmp_path, hidden=hidden)
    assert r.status == "ok"
    assert r.slides[2] is None
    got = [s.page_index for s in r.slides if s is not None]
    assert got == list(range(7))


def test_render_page_count_mismatch(monkeypatch, tmp_path, demo_deck):
    _fake_env(monkeypatch, tmp_path, 5)
    hidden = [False, False, True] + [False] * 5
    r = render_deck(demo_deck[0], tmp_path, hidden=hidden)
    assert r.status == "failed"
    assert r.reason == "page count did not match slide count"
    assert r.slides == [None] * 8


def test_convert_error_includes_log_tail(monkeypatch, tmp_path):
    from slideproof.render import soffice as so

    class FakePopen:
        returncode = 3

        def __init__(self, cmd, stdout=None, **kw):
            stdout.write(b"boom: bad filter")
            stdout.flush()

        def wait(self, timeout=None):
            return 3

    monkeypatch.setattr(so.subprocess, "Popen", FakePopen)
    with pytest.raises(RenderError, match="boom: bad filter"):
        so.convert_to_pdf(Path("soffice"), tmp_path / "a.pptx",
                          tmp_path / "out", tmp_path / "prof")
