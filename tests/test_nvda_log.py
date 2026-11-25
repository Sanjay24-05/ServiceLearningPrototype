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
