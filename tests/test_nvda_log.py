import subprocess
import sys
from pathlib import Path

from tools.nvda_log import spoken
from tools.record_demo import MAX_CAPTION, captions, read_saved, seconds_for

ROOT = Path(__file__).resolve().parents[1]


def test_spoken_reads_both_quote_styles_and_drops_the_language():
    log = ("IO - speech.speech.speak (10:00:00.000)\n"
           "Speaking ['en_US', 'main landmark', \"It isn't covered\", 'button']\n"
           "IO - inputCore (10:00:01.000)\n"
           "Speaking ['en_US']\n")
    assert spoken(log) == ["main landmark | It isn't covered | button"]


def test_captions_drop_the_window_title_and_loading_noise():
    assert captions(["Slide Proof - Profile 1 - Microsoft\u200b Edge | window", "Loading page",
                     "main landmark", "heading | level 1"]) == ["heading, level 1"]
    assert captions([]) == [""]


def test_long_captions_are_split_not_cut():
    pieces = captions(["word " * 400 + "6 probably intentional."])
    assert len(pieces) > 1 and all(len(p) <= MAX_CAPTION for p in pieces)
    assert " ".join(pieces).split() == ["word"] * 400 + ["6", "probably", "intentional."]


def test_saved_words_are_read_back_by_step():
    assert read_saved("### One\na | b\nc\n\n### Two\n\n### Three\nd\n") == [["a | b", "c"], [], ["d"]]


def test_frames_stay_up_long_enough_to_read():
    assert seconds_for("short") == 4
    assert seconds_for("word " * 40) == 14


def test_missing_log_is_one_clear_line(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "record_demo.py"),
                        str(tmp_path / "no.log"), str(tmp_path / "out.webm")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 2
    assert r.stdout.strip() == (f"NVDA log not found: {tmp_path / 'no.log'}. Start NVDA with "
                                "logging first (see tools/nvda_pass.py).")
    assert "Traceback" not in r.stderr


def test_a_silent_nvda_saves_nothing(tmp_path, capsys):
    from tools import record_demo

    class Page:
        def __getattr__(self, name):
            return lambda *a, **k: None

    class Playwright:
        chromium = type("C", (), {"launch": staticmethod(
            lambda **k: type("B", (), {"new_page": staticmethod(lambda **k: Page())})())})()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import playwright.sync_api as api
    import pytest
    log, out = tmp_path / "nvda.log", tmp_path / "out.webm"
    log.write_text("")
    out.with_suffix(".txt").write_text("keep me")
    mp = pytest.MonkeyPatch()
    mp.setattr(api, "sync_playwright", Playwright)
    mp.setattr(record_demo.time, "sleep", lambda s: None)
    try:
        with pytest.raises(SystemExit) as e:
            record_demo._record("http://x", log, out, None)
    finally:
        mp.undo()
    assert e.value.code == 2 and record_demo.NO_SPEECH in capsys.readouterr().out
    assert not out.exists() and out.with_suffix(".txt").read_text() == "keep me"


def test_replay_needs_all_saved_steps(tmp_path):
    saved = tmp_path / "words.txt"
    for text in (None, "### One\na\n"):
        if text:
            saved.write_text(text)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "record_demo.py"), "--replay",
                            str(saved), str(tmp_path / "o.webm")], capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 2 and "expected the 12 saved steps" in r.stdout
        assert "Traceback" not in r.stderr


def test_only_the_browser_title_is_dropped():
    line = "Slide 2 | Microsoft logo sticks out"
    assert captions([line]) == ["Slide 2, Microsoft logo sticks out"]
