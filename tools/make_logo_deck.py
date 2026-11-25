"""Build the school-logo deck used for the AI part of the demo.

The same logo runs off the same corner of every slide (deliberate design), and one photo runs
off slide 4 (a real mistake). It was designed to illustrate how the intent model behaves, so it
is not evidence of the model's accuracy.

Usage: python tools/make_logo_deck.py [out.pptx]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from slideproof.demo_deck import SLIDE_H, SLIDE_W, _layout, add_picture  # noqa: E402

TITLES = ["Welcome", "Our school", "Our clubs", "Class trip", "Volunteering", "Thank you"]


def _logo() -> Image.Image:
    img = Image.new("RGB", (480, 480), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([6, 6, 474, 474], fill=(0x1B, 0x5E, 0x20))
    d.polygon([(240, 110), (370, 240), (240, 370), (110, 240)], fill=(0xFF, 0xC1, 0x07))
    return img


def _photo() -> Image.Image:
    img = Image.new("RGB", (1200, 801), (0x90, 0xCA, 0xF9))
    d = ImageDraw.Draw(img)
    d.ellipse([850, 70, 1010, 230], fill=(0xFF, 0xEB, 0x3B))
    d.polygon([(0, 640), (330, 210), (660, 640)], fill=(0x60, 0x7D, 0x8B))
    d.polygon([(420, 640), (780, 300), (1150, 640)], fill=(0x78, 0x90, 0x9C))
    d.rectangle([0, 600, 1200, 801], fill=(0x55, 0x8B, 0x2F))
    return img


def build_logo_deck(out: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    layout = _layout(prs, "Title Only")
    for i, title in enumerate(TITLES, 1):
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = title
        add_picture(slide, "school-logo", None, None, -0.5, -0.5, 1.6, 1.6, "School logo", _logo())
        if i == 4:
            add_picture(slide, "trip-photo", None, None, 11.2, 3.0, 4.0, 2.67,
                        "Class trip photo", _photo())
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


if __name__ == "__main__":
    print(build_logo_deck(Path(sys.argv[1]) if len(sys.argv) > 1
                          else Path("docs/presentation/school_logo_deck.pptx")))
