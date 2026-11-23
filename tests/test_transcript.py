"""Golden screen-reader transcripts for each page.

The goldens are generated with LibreOffice deliberately disabled (the
live_server fixture points SOFFICE_PATH at a missing file) so they are stable
across machines. They therefore contain the "LibreOffice was not found" line
on the index page and the "text overflow, contrast and text size checks were
skipped" note on the report page.

Set UPDATE_TRANSCRIPTS=1 to rewrite the golden files.
"""
import difflib
import os
from pathlib import Path

from test_a11y import NAV_TIMEOUT, live_server, page, reach_report  # noqa: F401
from transcript import transcript

GOLDEN = Path(__file__).parent / "transcripts"


def check(name, page):
    actual = "\n".join(transcript(page)) + "\n"
    path = GOLDEN / f"{name}.txt"
    if os.environ.get("UPDATE_TRANSCRIPTS") == "1":
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="\n")
        return
    expected = path.read_text(encoding="utf-8")
    diff = "\n".join(difflib.unified_diff(
        expected.splitlines(), actual.splitlines(),
        f"golden/{name}.txt", "actual", lineterm=""))
    assert actual == expected, f"{name} transcript changed:\n{diff}"


def test_index_transcript(live_server, page):  # noqa: F811
    page.goto(live_server + "/")
    check("index", page)


def test_about_transcript(live_server, page):  # noqa: F811
    page.goto(live_server + "/about")
    check("about", page)


def test_report_transcript(live_server, demo_deck, page):  # noqa: F811
    reach_report(page, live_server, demo_deck[0])
    check("report", page)


def test_result_transcript(live_server, demo_deck, page):  # noqa: F811
    reach_report(page, live_server, demo_deck[0])
    page.get_by_role("button", name="Create corrected copy").click()
    page.wait_for_url("**/result", timeout=NAV_TIMEOUT)
    check("result", page)
