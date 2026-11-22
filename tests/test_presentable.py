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
