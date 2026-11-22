import re
import time

from tests.conftest import upload, wait_done


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
    assert "Report for demo.pptx" in rep and "Visible problems (5)" in rep
    assert len(re.findall(r'type="checkbox"[^>]*\schecked', rep)) == 4
    assert "LibreOffice is not installed" in rep
    assert "(s)" not in rep
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes},
                    follow_redirects=False)
    assert r.status_code == 303
    wait_done(client, run_id)
    res = client.get(f"/runs/{run_id}/result").text
    assert "4 fixes applied. 4 problems resolved. 0 new problems among the problems this version checks." in res
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
    assert ("This version checks seven things: objects that stick out past the slide edge, "
            "stretched pictures, overlapping objects, low-resolution pictures, titles out of line "
            "with the rest, stray fonts, and empty or stray objects. Text overflow, contrast and "
            "text size are not checked yet.") in rep
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


def test_report_has_layout_details(client, demo_deck):
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert "<summary>Layout of slide 4</summary>" in rep
    assert re.search(r"<summary>Layout of slide 4</summary>\s*<ol>\s*<li>The title, in the top", rep)


def _logo_run(client, tmp_path):
    from tests.test_intent_pipeline import _logo_deck
    p = _logo_deck(tmp_path / "logo.pptx")
    run_id = upload(client, "logo.pptx", p.read_bytes())
    wait_done(client, run_id)
    return run_id, client.get(f"/runs/{run_id}/report").text


def test_report_shows_probably_intentional_section(client, tmp_path):
    run_id, rep = _logo_run(client, tmp_path)
    assert "<h2>Probably intentional (6)</h2>" in rep
    assert ("<p>Slide Proof's model thinks these look like deliberate design. "
            "Check them if you are unsure.</p>") in rep
    assert re.search(r"Probably intentional \(\d+% sure\): the same object appears in the same "
                     r"place on 5 other slides and it runs along the edge of the slide like a "
                     r"design element\.", rep)
    assert "Visible problems" not in rep and "Minor polish" not in rep
    assert 'name="fix"' in rep
    assert not re.search(r'type="checkbox"[^>]*\schecked', rep)
    assert rep.index("<h2>Probably intentional") < rep.index("<h2>Apply fixes")
    assert "A small on-device model sorts findings that look like deliberate design into" in rep


def test_summary_counts_intentional(client, tmp_path):
    run_id, rep = _logo_run(client, tmp_path)
    assert "6 slides checked. No visible problems. 0 minor, 6 probably intentional. " in rep


def test_summary_omits_clause_when_none(client, demo_deck):
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert " probably intentional." not in rep
    assert "Probably intentional (" not in rep


def test_unticked_intentional_fix_still_applies_when_ticked(client, tmp_path):
    run_id, rep = _logo_run(client, tmp_path)
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    assert fixes
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes[:1]}, follow_redirects=False)
    assert r.status_code == 303
    assert wait_done(client, run_id)["next"] == f"/runs/{run_id}/result"
    res = client.get(f"/runs/{run_id}/result").text
    assert "1 fix applied" in res


def test_about_shows_model_accuracy(client):
    import json
    from slideproof import intent
    m = json.loads((intent.MODEL_DIR / "metrics.json").read_text())
    html = client.get("/about").text
    assert '<h2>What "Probably intentional" means</h2>' in html
    assert "<h2>How accurate the model is</h2>" in html
    assert f"kept {round(m['mistake_recall'] * 100)}% of planted mistakes" in html
    assert f"recognised {round(m['deliberate_recall'] * 100)}% of deliberate designs" in html
    assert "All training data is synthetic" in html
    assert "Nothing is hidden: it is still listed and counted" in html
    assert html.index("What it checks") < html.index("How accurate")
    assert html.index("How accurate") < html.index("How fixes work")


def test_about_and_report_without_model(client, tmp_path, monkeypatch):
    from slideproof import intent
    monkeypatch.setattr(intent, "MODEL_DIR", tmp_path)
    intent._cache.clear()
    try:
        html = client.get("/about").text
        assert "How accurate the model is" not in html
        assert "Probably intentional" not in html
        assert "A small on-device model" not in html
        assert "How fixes work" in html
    finally:
        intent._cache.clear()
