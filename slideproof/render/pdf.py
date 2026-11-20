"""Read a rendered PDF: page PNGs plus text spans with position and colour."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from slideproof.units import Rect


@dataclass
class RenderedSpan:
    text: str
    bbox: Rect  # EMU
    font: str
    size_pt: float
    rgb: tuple[int, int, int]


@dataclass
class RenderedSlide:
    page_index: int
    png_path: Path
    spans: list[RenderedSpan] = field(default_factory=list)


def read_pdf(pdf: Path, png_dir: Path, slide_w: int, slide_h: int) -> list[RenderedSlide]:
    png_dir.mkdir(parents=True, exist_ok=True)
    slides: list[RenderedSlide] = []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc):
            png = png_dir / f"slide-{i + 1:03d}.png"
            page.get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72)).save(png)
            scale = slide_w / page.rect.width
            spans: list[RenderedSpan] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for sp in line["spans"]:
                        if not sp["text"].strip():
                            continue
                        x0, y0, x1, y1 = sp["bbox"]
                        c = sp["color"]
                        spans.append(RenderedSpan(
                            text=sp["text"],
                            bbox=Rect(round(x0 * scale), round(y0 * scale),
                                      round((x1 - x0) * scale), round((y1 - y0) * scale)),
                            font=sp["font"],
                            size_pt=sp["size"],
                            rgb=((c >> 16) & 255, (c >> 8) & 255, c & 255),
                        ))
            slides.append(RenderedSlide(i, png, spans))
    return slides
