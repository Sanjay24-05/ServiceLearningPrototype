from tests.conftest import upload

LINK = '<link rel="stylesheet" href="/static/style.css">'
FOOTER = '<footer><p><a href="/about">How Slide Proof works</a></p></footer>'


def test_pages_link_stylesheet_and_footer(client, demo_deck):
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    for html in (client.get("/").text,
                 client.get("/runs/nope/report").text,
                 client.get(f"/runs/{run_id}/progress").text):
        assert LINK in html
        assert FOOTER in html
        assert html.index("</main>") < html.index(FOOTER)


def test_stylesheet_served(client):
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "prefers-color-scheme: dark" in r.text and ":focus-visible" in r.text


def test_demo_button_runs_demo(client):
    from tests.conftest import wait_done
    r = client.post("/demo", follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].split("/")[2]
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert "Report for demo_deck.pptx" in rep and "Visible problems (5)" in rep


def test_demo_button_twice_gives_two_runs(client):
    from tests.conftest import wait_done
    a = client.post("/demo", follow_redirects=False).headers["location"]
    b = client.post("/demo", follow_redirects=False).headers["location"]
    assert a != b
    for loc in (a, b):
        wait_done(client, loc.split("/")[2])
        assert "Report for demo_deck.pptx" in client.get(
            loc.replace("progress", "report")).text


def test_demo_build_failure_shows_error(client, monkeypatch):
    import slideproof.web.app as app_mod
    monkeypatch.setattr(app_mod, "build_demo_deck",
                        lambda d: (_ for _ in ()).throw(OSError("disk")))
    r = client.post("/demo")
    assert r.status_code == 400
    assert "The demo presentation could not be created." in r.text


def test_index_has_demo_button(client):
    assert '<button>Try the demo presentation</button>' in client.get("/").text
