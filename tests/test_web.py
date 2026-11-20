import re
import time

import pytest
from fastapi.testclient import TestClient

from slideproof.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing-soffice.exe"))
    return TestClient(create_app(tmp_path / "runs"))


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
    assert "Report for demo.pptx" in rep and "Visible problems (2)" in rep
    assert len(re.findall(r'type="checkbox"[^>]*\schecked', rep)) == 2
    assert "LibreOffice is not installed" in rep
    assert "(s)" not in rep
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes},
                    follow_redirects=False)
    assert r.status_code == 303
    wait_done(client, run_id)
    res = client.get(f"/runs/{run_id}/result").text
    assert "2 fixes applied. 2 problems resolved. 0 new problems." in res
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


def test_too_large_upload(client):
    r = client.post("/check", files={"file": ("big.pptx", b"0" * (50 * 1024 * 1024 + 1))})
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
