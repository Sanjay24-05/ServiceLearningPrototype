"""Build the Slide Proof demo deck and its ground-truth findings.

Usage: python tools/make_demo_deck.py <out_dir>
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from slideproof.units import inches  # noqa: E402

SLIDE_W, SLIDE_H = 12192000, 6858000
DARK_GREEN = (0x1B, 0x5E, 0x20)


def _layout(prs, name):
    return next(l for l in prs.slide_layouts if l.name == name)


def _png(px, color):
    buf = BytesIO()
    Image.new("RGB", px, color).save(buf, "PNG")
    buf.seek(0)
    return buf


def _face_png(px):
    """Light background, big circle face, eyes, smile and stripes: a circle
    visibly turns into an oval when the picture is stretched."""
    w, h = px
    img = Image.new("RGB", px, (0xE3, 0xF2, 0xFD))
    d = ImageDraw.Draw(img)
    for x in range(0, w, w // 10):
        d.line([(x, 0), (x, h)], fill=(0xB0, 0xC4, 0xDE), width=3)
    r = int(h * 0.4)
    cx, cy = w // 2, h // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0xFF, 0xCC, 0x80),
              outline=(0x4E, 0x34, 0x2E), width=8)
    er = r // 9
    for ex in (cx - r // 2, cx + r // 2):
        d.ellipse([ex - er, cy - r // 3 - er, ex + er, cy - r // 3 + er],
                  fill=(0x21, 0x21, 0x21))
    d.arc([cx - r // 2, cy - r // 4, cx + r // 2, cy + r // 2], 20, 160,
          fill=(0x21, 0x21, 0x21), width=10)
    return img


def _logo_png(px):
    w, h = px
    img = Image.new("RGB", px, (0xFF, 0xFF, 0xFF))
    ImageDraw.Draw(img).ellipse([8, 8, w - 8, h - 8], fill=(0x2E, 0x7D, 0x32))
    return img


def _img_png(img):
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def add_picture(slide, name, px, color, x, y, w, h, alt, image=None):
    """x/y/w/h in inches. `image` is an optional PIL image to use instead of a flat colour."""
    pic = slide.shapes.add_picture(
        _img_png(image) if image is not None else _png(px, color),
        inches(x), inches(y), inches(w), inches(h))
    pic.name = name
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def add_text(slide, name, x, y, w, h, lines, size=None, color=None, font=None):
    tb = slide.shapes.add_textbox(inches(x), inches(y), inches(w), inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = line
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor(*color)
        if font:
            run.font.name = font
    return tb


def _title(slide, text, name="slide-title"):
    slide.shapes.title.text = text
    slide.shapes.title.name = name
    return slide.shapes.title


def build_demo_deck(out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    title_only = _layout(prs, "Title Only")
    expected: list[dict] = []

    def row(slide, check, shapes, severity, fix):
        expected.append({"slide": slide, "check": check, "shapes": shapes,
                         "severity": severity, "fix": fix})

    # 1: clean title slide
    s = prs.slides.add_slide(_layout(prs, "Title Slide"))
    s.shapes.title.text = "Community Garden Project"
    s.placeholders[1].text = "Spring update"

    # 2: agenda box sticks out on the right (~20%)
    s = prs.slides.add_slide(title_only)
    _title(s, "Agenda")
    add_text(s, "agenda-box", 10.13, 1.5, 4.0, 3.0,
             ["Welcome and introductions from our team",
              "Garden progress since last spring",
              "Budget and funding for next year",
              "Next steps and volunteer sign-up"], size=24)
    row(2, "C1", ["agenda-box"], "visible", "F1")

    # 3: text overlapping a chart picture
    s = prs.slides.add_slide(title_only)
    _title(s, "Results")
    add_text(s, "results-list", 0.5, 1.5, 7, 4.5,
             ["Tomatoes: 120 kg", "Beans: 80 kg", "Squash: 95 kg",
              "Herbs: 30 kg", "Lettuce: 60 kg"], size=24)
    add_picture(s, "results-chart", (1000, 600), (0x4C, 0xAF, 0x50),
                5, 3.5, 5, 3, "Bar chart of harvest results")
    row(3, "C2", ["results-list", "results-chart"], "visible", "F6")

    # 4: stretched photo and low-DPI logo
    s = prs.slides.add_slide(title_only)
    _title(s, "Our team")
    add_picture(s, "team-photo", (800, 600), (0x79, 0x55, 0x48),
                2.5, 1.5, 8, 3.75, "Team photo",
                image=_face_png((800, 600)))
    add_picture(s, "logo", (100, 100), (0x2E, 0x7D, 0x32),
                11, 5.3, 2, 2, "Garden logo",
                image=_logo_png((100, 100)))
    row(4, "C4", ["team-photo"], "visible", "F2")
    row(4, "C5", ["logo"], "visible", None)

    # 5: title shifted down 0.6 in vs layout, mixed fonts
    s = prs.slides.add_slide(title_only)
    t = _title(s, "Budget")
    lay = next(sh for sh in title_only.placeholders
               if sh.placeholder_format.idx == t.placeholder_format.idx)
    t.left, t.width, t.height = lay.left, lay.width, lay.height
    t.top = lay.top + 548640
    add_text(s, "budget-text", 0.5, 3.0, 8, 1.0,
             ["Total budget: $4,200"], size=24, font="Calibri")
    add_text(s, "budget-note", 0.5, 4.5, 8, 1.0,
             ["Funded by local grants"], size=24, font="Georgia")
    row(5, "C8", ["slide-title"], "visible", "F3")
    row(5, "C9", ["budget-note"], "minor", "F5")

    # 6: overflowing text box
    s = prs.slides.add_slide(title_only)
    _title(s, "Timeline")
    tb = add_text(s, "timeline-list", 0.5, 1.5, 6, 4,
                  [f"Milestone {i}: task {i}" for i in range(1, 15)], size=20)
    tb.text_frame.auto_size = MSO_AUTO_SIZE.NONE
    tb.text_frame.word_wrap = True
    row(6, "C3", ["timeline-list"], "visible", "F7")

    # 7: low-contrast text
    s = prs.slides.add_slide(title_only)
    _title(s, "Volunteers")
    add_text(s, "grey-text", 0.5, 2.0, 5, 1.0, ["Join a work party"],
             size=28, color=(0xBB, 0xBB, 0xBB))
    add_picture(s, "bright-photo", (800, 400), (0xFF, 0xF5, 0x9D),
                6, 2, 6, 3, "Volunteers planting seedlings")
    add_text(s, "photo-caption", 6.5, 3.0, 5, 1.0, ["Saturday mornings"],
             size=28, color=(0xFF, 0xFF, 0xFF))
    row(7, "C7", ["grey-text"], "visible", None)
    row(7, "C7", ["photo-caption"], "visible", None)

    # 8: full-slide background (bottom of z-order), legit overlays, one empty box
    s = prs.slides.add_slide(title_only)
    bg = add_picture(s, "background", (1920, 1080), DARK_GREEN,
                     0, 0, 1, 1, "Dark green background")
    bg.left, bg.top, bg.width, bg.height = 0, 0, SLIDE_W, SLIDE_H
    tree = s.shapes._spTree
    tree.remove(bg._element)
    tree.insert(2, bg._element)  # after nvGrpSpPr, grpSpPr: first in z-order
    title = _title(s, "Thank you")
    title.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
    add_text(s, "thanks-text", 0.8, 2.5, 8, 1.2, ["Thanks for growing with us"],
             size=40, color=(0xFF, 0xFF, 0xFF))
    co = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                            inches(0.8), inches(4.2), inches(3), inches(1))
    co.name = "callout"
    co.fill.solid()
    co.fill.fore_color.rgb = RGBColor(0xF5, 0x7F, 0x17)
    co.line.fill.background()
    co.text_frame.text = "Join us!"
    run = co.text_frame.paragraphs[0].runs[0]
    run.font.size = Pt(28)
    run.font.color.rgb = RGBColor(0, 0, 0)
    stray = s.shapes.add_textbox(inches(9), inches(5.5), inches(2), inches(0.8))
    stray.name = "stray-box"
    row(8, "C10", ["stray-box"], "minor", "F4")

    deck_path = out_dir / "demo_deck.pptx"
    gt_path = out_dir / "expected_findings.json"
    prs.save(deck_path)
    gt_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return deck_path, gt_path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/output")
    for p in build_demo_deck(out):
        print(p)
