import re
import time

import pytest
from fastapi.testclient import TestClient

from slideproof.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing-soffice.exe"))
    return TestClient(create_app(tmp_path / "runs"), base_url="http://127.0.0.1")


def wait_done(client, run_id, cap=30):
    end = time.time() + cap
    while time.time() < end:
        s = client.get(f"/runs/{run_id}/status").json()
        if s["state"] != "working":
            return s
        time.sleep(0.1)
    raise AssertionError("run did not finish in time")


def upload(client, name, data):
    r = client.post("/check", files={"file": (name, data)},
                    follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].split("/")[2]


def full_flow(client, demo_deck, name):
    run_id = upload(client, name, demo_deck[0].read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes},
                    follow_redirects=False)
    assert r.status_code == 303
    assert wait_done(client, run_id)["next"] == f"/runs/{run_id}/result"
    return run_id, rep


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<h1>Check slide layout</h1>" in r.text and 'lang="en"' in r.text
    assert "Before you start" in r.text  # soffice missing


def test_full_flow_demo_deck(client, demo_deck):
    r = client.post("/check", files={"file": ("demo.pptx", demo_deck[0].read_bytes())},
                    follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].split("/")[2]
    assert wait_done(client, run_id)["next"] == f"/runs/{run_id}/report"
    rep = client.get(f"/runs/{run_id}/report").text
    assert "Report for demo.pptx" in rep and "Visible problems (4)" in rep
    assert len(re.findall(r'type="checkbox"[^>]*\schecked', rep)) == 3
    assert "LibreOffice is not installed" in rep
    assert "(s)" not in rep
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes},
                    follow_redirects=False)
    assert r.status_code == 303
    wait_done(client, run_id)
    res = client.get(f"/runs/{run_id}/result").text
    assert "3 fixes applied. 3 problems resolved. 0 new problems among the problems this version checks." in res
    d = client.get(f"/runs/{run_id}/download")
    assert d.status_code == 200
    assert ("filename*=utf-8''demo%20%28checked%29.pptx"
            in d.headers["content-disposition"])


def test_wrong_extension_error(client):
    r = client.post("/check", files={"file": ("old.ppt", b"x")})
    assert r.status_code == 400 and "Save as .pptx and try again." in r.text


def test_corrupt_pptx_shows_error_not_500(client):
    run_id = upload(client, "bad.pptx", b"not a zip")
    s = wait_done(client, run_id)
    assert s["state"] == "error" and "could not be opened" in s["message"]
    page = client.get(f"/runs/{run_id}/progress")
    assert page.status_code == 200
    assert 'role="alert"' in page.text and "Check another file" in page.text


def test_too_large_upload(client, monkeypatch):
    import slideproof.web.app as webapp
    monkeypatch.setattr(webapp, "MAX_BYTES", 1024)
    r = client.post("/check", files={"file": ("big.pptx", b"0" * 1025)})
    assert r.status_code == 400 and "larger than 50 MB" in r.text


def test_unicode_filename_roundtrip(client, demo_deck):
    run_id, rep = full_flow(client, demo_deck, "Café plan.pptx")
    assert "Report for Café plan.pptx" in rep
    d = client.get(f"/runs/{run_id}/download")
    assert d.status_code == 200
    assert ("filename*=utf-8''Caf%C3%A9%20plan%20%28checked%29.pptx"
            in d.headers["content-disposition"])


def test_unknown_run_404(client):
    r = client.get("/runs/nope/report")
    assert r.status_code == 404 and "Check the file again." in r.text
    assert 'href="/"' in r.text


def test_no_fixes_selected(client, demo_deck):
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    r = client.post(f"/runs/{run_id}/export", data={})
    assert r.status_code == 200
    assert "No fixes were selected, so no copy was made." in r.text


def test_unexpected_error_in_job_is_reported(client, monkeypatch):
    import slideproof.web.app as webapp

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(webapp, "analyse", boom)
    run_id = upload(client, "x.pptx", b"x")
    s = wait_done(client, run_id)
    assert s["state"] == "error" and s["message"].startswith("Something went wrong")


def test_plural_helper():
    from slideproof.web.app import plural
    assert plural(1, "visible problem") == "1 visible problem"
    assert plural(2, "slide") == "2 slides"
    assert plural(1, "fix", "fixes") == "1 fix"
    assert plural(0, "fix", "fixes") == "0 fixes"


def test_report_states_what_is_checked(client, demo_deck):
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert ("This version checks two things: objects that stick out past the "
            "slide edge, and stretched pictures. Overlap, text overflow, "
            "contrast, fonts and title position are not checked yet.") in rep
    assert rep.index("This version checks") < rep.index("<form")


def test_summary_singular_and_minor_only(client, tiny_deck):
    path = tiny_deck([dict(kind="text", name="t", x=12.9, y=1, w=1, h=1, text="")])
    run_id = upload(client, "one.pptx", path.read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert "1 slide checked. No visible problems. 1 minor." in rep
    assert "1 slides" not in rep


def test_summary_no_problems_singular(client, tiny_deck):
    path = tiny_deck([dict(kind="text", name="t", x=1, y=1, w=3, h=1, text="hi")])
    run_id = upload(client, "ok.pptx", path.read_bytes())
    wait_done(client, run_id)
    assert "1 slide checked. No problems found." in client.get(f"/runs/{run_id}/report").text


def test_unchecked_sentence(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches
    from slideproof.describe.coverage import unchecked_sentence
    from slideproof.loader import load_deck
    prs = Presentation()
    for _ in range(2):
        prs.slides.add_slide(prs.slide_layouts[6])
    prs.slides[1].shapes.add_table(2, 2, 0, 0, Inches(3), Inches(1))
    p = tmp_path / "t.pptx"
    prs.save(p)
    deck = load_deck(p)
    assert unchecked_sentence(deck) == (
        "Some objects could not be checked: 1 object on slide 2.")
    deck.slides[0].skipped_shapes.append("grp")
    assert unchecked_sentence(deck) == (
        "Some objects could not be checked: 2 objects on slides 1 and 2.")
    deck.slides[0].skipped_shapes.clear()
    deck.slides[1].elements.clear()
    assert unchecked_sentence(deck) is None


def test_bad_file_name_gives_400_page(client, monkeypatch):
    from pathlib import Path

    def boom(self, data):
        raise OSError("reserved name")
    monkeypatch.setattr(Path, "write_bytes", boom)
    r = client.post("/check", files={"file": ("CON.pptx", b"x")})
    assert r.status_code == 400
    import html
    assert "This file name can't be used. Rename the file and try again." in html.unescape(r.text)


def _fixes_of(client, run_id):
    rep = client.get(f"/runs/{run_id}/report").text
    return re.findall(r'value="(F\d:[^"]+)"', rep)


def test_no_copy_made_message(client, demo_deck, monkeypatch):
    import slideproof.web.app as webapp
    from slideproof.verify import ExportResult
    monkeypatch.setattr(webapp, "export_and_verify",
                        lambda *a, **k: ExportResult(None, [], [], 0, 0, None))
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    client.post(f"/runs/{run_id}/export", data={"fix": _fixes_of(client, run_id)},
                follow_redirects=False)
    wait_done(client, run_id)
    res = client.get(f"/runs/{run_id}/result").text
    assert "No corrected copy was made because no fix could be applied." in res


def test_double_export_starts_one_job(client, demo_deck, monkeypatch):
    import threading
    import slideproof.web.app as webapp
    from slideproof.verify import ExportResult
    calls, gate = [], threading.Event()

    def slow(*a, **k):
        calls.append(1)
        gate.wait(10)
        return ExportResult(None, [], [], 0, 0, None)
    monkeypatch.setattr(webapp, "export_and_verify", slow)
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    fixes = _fixes_of(client, run_id)
    r1 = client.post(f"/runs/{run_id}/export", data={"fix": fixes}, follow_redirects=False)
    r2 = client.post(f"/runs/{run_id}/export", data={"fix": fixes}, follow_redirects=False)
    gate.set()
    wait_done(client, run_id)
    assert r1.status_code == r2.status_code == 303
    assert r2.headers["location"] == f"/runs/{run_id}/progress"
    assert len(calls) == 1


def test_store_start_refuses_second_job_and_new_export_clears_old(tmp_path):
    import threading
    from slideproof.web.runs import RunStore
    store = RunStore(tmp_path)
    run = store.create("a.pptx")
    gate = threading.Event()
    assert store.start(run, lambda p: (gate.wait(10), "/x")[1]) is True
    assert store.start(run, lambda p: "/y") is False
    gate.set()
    _wait_state(store, run)
    run.export = object()
    assert store.start(run, lambda p: "/z", clear_export=True) is True
    assert run.export is None


def _wait_state(store, run, cap=10):
    end = time.time() + cap
    while time.time() < end:
        s = store.snapshot(run)
        if s["state"] != "working":
            return
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_clear_runs_removes_old_run_folders(tmp_path):
    from slideproof.web.runs import clear_runs
    root = tmp_path / "slideproof"
    (root / "abc" / "original").mkdir(parents=True)
    (root / "abc" / "original" / "x.pptx").write_bytes(b"x")
    (root / "stray.txt").write_text("x")
    clear_runs(root)
    assert root.is_dir() and list(root.iterdir()) == []
    clear_runs(tmp_path / "missing")  # no error


def test_untrusted_host_header_rejected(client):
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/", headers={"host": "localhost:8765"}).status_code == 200


def test_file_input_not_required(client):
    assert " required" not in client.get("/").text.split("<form")[1]


def test_submit_without_file_field_gives_400(client):
    r = client.post("/check", data={})
    assert r.status_code == 400
    assert 'role="alert"' in r.text and "Check another file" in r.text
    assert "Choose a PowerPoint file (.pptx) first." in r.text


def test_submit_with_empty_filename_gives_400(client):
    r = client.post("/check", files={"file": ("", b"")})
    assert r.status_code == 400
    assert "Choose a PowerPoint file (.pptx) first." in r.text


def test_coverage_sentence_in_summary_paragraph(client, tiny_deck):
    path = tiny_deck([dict(kind="text", name="t", x=1, y=1, w=3, h=1, text="hi")])
    run_id = upload(client, "ok.pptx", path.read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert re.search(r"<p>1 slide checked\. [^<]*\. This version checks", rep)
