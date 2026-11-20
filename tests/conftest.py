import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from slideproof.units import inches  # noqa: E402
from make_demo_deck import build_demo_deck  # noqa: E402


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
