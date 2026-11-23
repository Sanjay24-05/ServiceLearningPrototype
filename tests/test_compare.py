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
    assert r.headers["cache-control"] == "no-store"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    # Unchanged slides, junk and traversal attempts are 404.
    for bad in ("1", "0", "-1", "4a", "..%2Fx", "%2E%2E", "4.0"):
        assert client.get(f"/runs/{run_id}/compare/{bad}.png").status_code == 404


def _fake_render(tmp_path, tag, missing=()):
    from types import SimpleNamespace
    slides = []
    for n in range(1, 4):
        png = tmp_path / f"{tag}-{n}.png"
        if n not in missing:
            Image.new("RGB", (40, 30), (n * 60, 0, 0)).save(png)
        slides.append(SimpleNamespace(png_path=png))
    return SimpleNamespace(status="ok", slides=slides)


def test_build_drops_only_the_slide_without_a_png(tmp_path):
    # A hidden slide may have no PNG: leave that slide out, keep the others.
    from types import SimpleNamespace
    from slideproof.web.compare import build, image_path
    run_dir = tmp_path / "run"
    original = SimpleNamespace(render=_fake_render(tmp_path, "before"))
    export = SimpleNamespace(final=SimpleNamespace(render=_fake_render(tmp_path, "after", missing=(3,))))
    logs = {2: ["Slide 2: a moved back onto the slide."], 3: ["Slide 3: b moved back."]}
    got = build(run_dir, original, export, logs)
    assert [n for n, _ in got] == [2]
    assert image_path(run_dir, 2).is_file() and not image_path(run_dir, 3).exists()


def test_build_absent_when_no_slide_has_both_pngs(tmp_path):
    from types import SimpleNamespace
    from slideproof.web.compare import build
    original = SimpleNamespace(render=_fake_render(tmp_path, "before", missing=(2,)))
    export = SimpleNamespace(final=SimpleNamespace(render=_fake_render(tmp_path, "after", missing=(3,))))
    logs = {2: ["Slide 2: a."], 3: ["Slide 3: b."]}
    assert build(tmp_path / "run", original, export, logs) == []


def test_compare_image_is_not_cached(tmp_path, monkeypatch):
    # A later export of the same run rewrites the image at the same URL.
    from types import SimpleNamespace
    from slideproof.web import app as app_mod
    from slideproof.web.compare import image_path
    stores = []

    class Store(app_mod.RunStore):
        def __init__(self, root):
            super().__init__(root)
            stores.append(self)
    monkeypatch.setattr(app_mod, "RunStore", Store)
    client = TestClient(create_app(tmp_path / "runs"), base_url="http://127.0.0.1")
    run = stores[0].create("x.pptx")
    run.export = SimpleNamespace()
    run.compare = [(2, "Slide 2 before and after: x.")]
    Image.new("RGB", (10, 10)).save(image_path(run.dir, 2))
    r = client.get(f"/runs/{run.id}/compare/2.png")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
