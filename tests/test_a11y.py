import os
import socket
import threading
import time

import pytest

from slideproof.web.app import create_app

playwright_sync = pytest.importorskip("playwright.sync_api")
axe_mod = pytest.importorskip("axe_playwright_python.sync_playwright")

NAV_TIMEOUT = 120_000


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    import uvicorn
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing-soffice.exe"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = create_app(tmp_path / "runs")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    try:
        t.start()
        end = time.time() + 20
        while not server.started and time.time() < end:
            time.sleep(0.05)
        assert server.started, "uvicorn did not start"
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        t.join(timeout=15)


@pytest.fixture
def page():
    with playwright_sync.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Edge could not be launched for Playwright: {e}")
        pg = browser.new_page()
        pg.set_default_timeout(NAV_TIMEOUT)
        yield pg
        browser.close()


def assert_no_serious(page, label):
    results = axe_mod.Axe().run(page)
    bad = [v for v in results.response["violations"]
           if v.get("impact") in {"serious", "critical"}]
    msg = "\n".join(
        f"{label}: {v['id']} ({v['impact']}): {v['help']} -> "
        f"{v['nodes'][0]['target'] if v['nodes'] else ''}" for v in bad)
    assert not bad, msg


def reach_report(page, base, deck_path):
    page.goto(base + "/")
    page.set_input_files("#file", str(deck_path))
    page.get_by_role("button", name="Check slides").click()
    page.wait_for_url("**/report", timeout=NAV_TIMEOUT)


def test_pages_have_no_serious_axe_violations(live_server, demo_deck, page):
    page.goto(live_server + "/")
    assert_no_serious(page, "index")
    page.set_input_files("#file", str(demo_deck[0]))
    page.get_by_role("button", name="Check slides").click()
    page.wait_for_url("**/report", timeout=NAV_TIMEOUT)
    assert page.evaluate("document.activeElement.id") == "top"
    assert_no_serious(page, "report")
    page.get_by_role("button", name="Create corrected copy").click()
    page.wait_for_url("**/result", timeout=NAV_TIMEOUT)
    assert_no_serious(page, "result")


def test_report_focuses_h1_on_load(live_server, demo_deck, page):
    reach_report(page, live_server, demo_deck[0])
    assert page.evaluate("document.activeElement.id") == "top"
    assert page.evaluate("document.activeElement.tagName") == "H1"


def test_report_heading_outline(live_server, demo_deck, page):
    reach_report(page, live_server, demo_deck[0])
    heads = page.evaluate(
        "[...document.querySelectorAll('h1,h2,h3')]"
        ".map(h => [h.tagName.toLowerCase(), h.textContent.trim()])")
    name = demo_deck[0].name
    assert heads[0] == ["h1", f"Report for {name}"]
    assert heads[1] == ["h2", "Visible problems (3)"]
    # Ranking is deterministic (spec 7.3): the stretched team photo on
    # slide 4 outranks the agenda box on slide 2.
    assert [h[0] for h in heads[2:5]] == ["h3", "h3", "h3"]
    assert [h[1].split(",")[0] for h in heads[2:5]] == ["Slide 4", "Slide 2", "Slide 3"]
    assert heads[-1] == ["h2", "Apply fixes"]
