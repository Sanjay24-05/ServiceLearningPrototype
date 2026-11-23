import sys
import time
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slideproof.units import inches  # noqa: E402
from slideproof.demo_deck import build_demo_deck  # noqa: E402
from slideproof.web.app import create_app  # noqa: E402


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


@pytest.fixture(scope="session")
def demo_deck(tmp_path_factory):
    return build_demo_deck(tmp_path_factory.mktemp("demo"))


@pytest.fixture
def tiny_deck(tmp_path):
    def make(shapes, slide_w=inches(13.333), slide_h=inches(7.5)):
        prs = Presentation()
        prs.slide_width, prs.slide_height = slide_w, slide_h
        blank = next(l for l in prs.slide_layouts if l.name == "Blank")
        slide = prs.slides.add_slide(blank)
        for d in shapes:
            x, y, w, h = (inches(d[k]) for k in ("x", "y", "w", "h"))
            if d["kind"] == "picture":
                buf = BytesIO()
                Image.new("RGB", tuple(d.get("px", (100, 100))),
                          (0x80, 0x80, 0x80)).save(buf, "PNG")
                buf.seek(0)
                sh = slide.shapes.add_picture(buf, x, y, w, h)
            else:
                sh = slide.shapes.add_textbox(x, y, w, h)
                if "text" in d:
                    sh.text_frame.text = d["text"]
            sh.name = d["name"]
            if d.get("rotation"):
                sh.rotation = d["rotation"]
        path = tmp_path / "tiny.pptx"
        prs.save(path)
        return path
    return make


def pytest_collection_modifyitems(config, items):
    from slideproof.render.soffice import find_soffice
    if find_soffice() is None:
        skip = pytest.mark.skip(reason="LibreOffice not installed")
        for item in items:
            if "soffice" in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def make_finding():
    from slideproof.findings import Finding

    def make(check_id, slide_index, eid, severity, magnitude):
        return Finding(check_id, slide_index, slide_index, (eid,), severity,
                       "definite", magnitude, {}, fix=None)
    return make


@pytest.fixture
def make_render():
    """Build a RenderResult by hand: make_render([[(text, (x, y, w, h) in EMU), ...] per slide])."""
    from slideproof.render.pdf import RenderedSlide, RenderedSpan
    from slideproof.render.pipeline import RenderResult
    from slideproof.units import Rect

    def make(slides_spans):
        slides = []
        for i, spans in enumerate(slides_spans):
            if spans is None:
                slides.append(None)
                continue
            slides.append(RenderedSlide(i, Path("x.png"), [
                RenderedSpan(t, Rect(*b), "Arial", 18.0, (0, 0, 0)) for t, b in spans]))
        return RenderResult("ok", None, slides)
    return make
