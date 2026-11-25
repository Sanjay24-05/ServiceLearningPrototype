"""Build the six-slide talk deck for the faculty presentation.

Usage: python tools/make_talk_deck.py [out.pptx]
Slide 2 uses docs/presentation/demo-slide-3.png (demo slide 3 as LibreOffice renders it).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from slideproof.demo_deck import SLIDE_H, SLIDE_W, _layout, add_picture, add_text  # noqa: E402
from slideproof.units import inches  # noqa: E402

PICTURE = ROOT / "docs" / "presentation" / "demo-slide-3.png"
INK, GREEN = (0x21, 0x21, 0x21), (0x1B, 0x5E, 0x20)
WHITE, AMBER = (0xFF, 0xFF, 0xFF), (0xFF, 0xC1, 0x07)

SLIDES = [
    ("Slide Proof", ["Checking slide layouts without sight"],
     "Slide Proof lets a blind presenter check how their slides look, on their own, before they present."),
    ("It sounds fine. It isn't.", [],
     "Reading the text gives no hint that the chart covers the ends of three bullets. NVDA can report "
     "overlaps in points, shape by shape, if you select each shape. It does not check the whole deck, "
     "or say what the audience loses."),
    ("Who it is for", ["Blind presenters who use NVDA or JAWS",
                       "Check your own slides, alone, before you present",
                       "Files stay on your computer",
                       "Fixes go into a copy, and every change is listed"],
     "The goal is independence: no sighted helper needed, and the presenter decides what to change. "
     "It has been run with NVDA only so far; JAWS is planned."),
    ("Mistake or on purpose?", ["A small model that runs on this computer",
                                "Uses 21 facts about shape and position, never the words",
                                "Says why, and how sure it is",
                                "Never hides a finding"],
     "A logo off the corner of every slide is probably design. A photo off one slide is probably a "
     "slip. The model sorts them; the presenter decides."),
    ("What we measured", ["97.6% of planted mistakes stayed in the main lists",
                          "94.3% of deliberate designs were recognised",
                          "120 synthetic decks, each tested while held out; mildly optimistic",
                          "Untested on real-world decks. No blind user has tested it yet."],
     "Of the findings the app judges, 14 of 593 planted mistakes were wrongly moved. A moved finding is still listed, with its fix "
     "unticked. The threshold and model were chosen on the same predictions, so the figures are "
     "mildly optimistic."),
    ("What comes next", ["The remaining fixes", "Testing with JAWS", "Testing with blind users",
                         "Can you introduce us to testers?"],
     "Our request today: introductions to blind students or staff who make slides."),
]


def build_talk_deck(out: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    layout = _layout(prs, "Title Only")
    ph = next(p for p in layout.placeholders if p.placeholder_format.type == PP_PLACEHOLDER.TITLE)
    ph.left, ph.top, ph.width, ph.height = (inches(v) for v in (0.8, 0.5, 11.7, 1.1))
    for i, (title, lines, notes) in enumerate(SLIDES):
        dark = i in (0, len(SLIDES) - 1)
        slide = prs.slides.add_slide(layout)
        if dark:
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = RGBColor(*GREEN)
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *(inches(v) for v in (0.9, 1.6, 1.6, 0.08)))
        bar.name = "accent-line"
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*(AMBER if dark else GREEN))
        bar.line.fill.background()
        slide.shapes.title.text = title
        p = slide.shapes.title.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        p.runs[0].font.size, p.runs[0].font.bold = Pt(44), True
        p.runs[0].font.color.rgb = RGBColor(*(WHITE if dark else GREEN))
        if lines:
            body = add_text(slide, "points", 0.8, 2.0, 11.7, 4.6, lines, 34,
                            WHITE if dark else INK)
            body.text_frame.auto_size = MSO_AUTO_SIZE.NONE
            for para in body.text_frame.paragraphs:
                para.space_after = Pt(16)
        else:
            img = Image.open(PICTURE).convert("RGB")
            h = 5.2
            w = h * img.width / img.height
            pic = add_picture(slide, "slide-3-picture", None, None, (13.333 - w) / 2, 1.8, w, h,
                              "Demo slide 3: a chart covers part of the bullet list", img)
            pic.line.color.rgb, pic.line.width = RGBColor(*INK), Pt(1.5)
        slide.notes_slide.notes_text_frame.text = notes
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


if __name__ == "__main__":
    print(build_talk_deck(Path(sys.argv[1]) if len(sys.argv) > 1
                          else Path("docs/presentation/slide_proof_talk.pptx")))
