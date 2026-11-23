import re

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from slideproof.web.app import create_app
from slideproof.web.compare import GAP, alt_text, compose
from tests.conftest import upload, wait_done


def test_compose_side_by_side(tmp_path):
    a, b, out = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "out.png"
    Image.new("RGB", (40, 30), (255, 0, 0)).save(a)
    Image.new("RGB", (50, 30), (0, 0, 255)).save(b)
    compose(a, b, out)
    im = Image.open(out).convert("RGB")
    assert GAP == 24
    assert im.size == (40 + 24 + 50, 30)
    assert im.getpixel((5, 5)) == (255, 0, 0)
    assert im.getpixel((40 + 12, 15)) == (255, 255, 255)
    assert im.getpixel((40 + 24 + 5, 5)) == (0, 0, 255)
    # Each half is outlined so white slides stand apart from the gap.
    assert im.getpixel((0, 0)) != (255, 0, 0)
    assert im.getpixel((40 + 24, 0)) != (0, 0, 255)


def test_compose_scales_to_same_height(tmp_path):
    a, b, out = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "out.png"
    Image.new("RGB", (40, 20), (255, 0, 0)).save(a)
    Image.new("RGB", (80, 40), (0, 0, 255)).save(b)
    compose(a, b, out)
    im = Image.open(out)
    # Both halves scaled to the taller height (40): 80 + 24 + 80.
    assert im.size == (80 + 24 + 80, 40)


def test_compose_flattens_transparency_onto_white(tmp_path):
    a, b, out = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "out.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(a)
    Image.new("RGB", (10, 10), (0, 0, 0)).save(b)
    compose(a, b, out)
    assert Image.open(out).convert("RGB").getpixel((2, 2)) == (255, 255, 255)


def test_alt_text_strips_prefix_and_joins():
    assert alt_text(4, ["Slide 4: the team photo restored to its natural "
                        "shape; it is now narrower and still centred."]) == (
        "Slide 4 before and after: the team photo restored to its natural "
        "shape; it is now narrower and still centred.")
    assert alt_text(2, ["Slide 2: a moved back onto the slide.",
                        "Slide 2: an b was removed."]) == (
        "Slide 2 before and after: a moved back onto the slide; "
        "an b was removed.")


@pytest.mark.soffice
def test_result_shows_compare_with_render(tmp_path, demo_deck):
    client = TestClient(create_app(tmp_path / "runs"),
                        base_url="http://127.0.0.1")
    run_id = upload(client, "demo.pptx", demo_deck[0].read_bytes())
    wait_done(client, run_id, cap=600)
    rep = client.get(f"/runs/{run_id}/report").text
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    client.post(f"/runs/{run_id}/export", data={"fix": fixes},
                follow_redirects=False)
    assert wait_done(client, run_id, cap=600)["next"] == f"/runs/{run_id}/result"
    res = client.get(f"/runs/{run_id}/result").text
    assert "<details><summary>Show the changed slides</summary>" in res
    imgs = re.findall(r'<img src="([^"]+)" alt="([^"]+)"', res)
    assert imgs, res
    alts = [a for _, a in imgs]
    assert any(a.startswith("Slide 4 before and after: ") for a in alts)
    assert all("Slide 4: " not in a for a in alts)
    src = next(s for s, a in imgs if a.startswith("Slide 4 "))
    assert src == f"/runs/{run_id}/compare/4.png"
    r = client.get(src)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    # Unchanged slides, junk and traversal attempts are 404.
    for bad in ("1", "0", "-1", "4a", "..%2Fx", "%2E%2E", "4.0"):
        assert client.get(f"/runs/{run_id}/compare/{bad}.png").status_code == 404
