"""pptx -> LibreOffice -> PDF -> PyMuPDF, with graceful skip/fail."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pptx import Presentation

from .pdf import RenderedSlide, RenderedSpan, read_pdf
from .soffice import RenderError, convert_to_pdf, find_soffice


@dataclass
class RenderResult:
    status: Literal["ok", "skipped", "failed"]
    reason: str | None
    slides: list[RenderedSlide | None]
    linked: dict[str, list[RenderedSpan]] = field(default_factory=dict)


def slide_size(pptx: Path) -> tuple[int, int]:
    prs = Presentation(str(pptx))
    return int(prs.slide_width), int(prs.slide_height)


def render_deck(pptx: Path, run_dir: Path, hidden: list[bool]) -> RenderResult:
    n = len(hidden)
    empty: list[RenderedSlide | None] = [None] * n

    def bad(status, reason):
        return RenderResult(status, reason, list(empty))

    soffice = find_soffice()
    if soffice is None:
        return bad("skipped", "LibreOffice is not installed")
    try:
        pdf = convert_to_pdf(soffice, pptx, run_dir / "pdf", run_dir / "lo-profile")
    except subprocess.TimeoutExpired:
        return bad("failed", "LibreOffice took too long")
    except RenderError:
        return bad("failed", "LibreOffice could not render this file")
    try:
        w, h = slide_size(pptx)
        pages = read_pdf(pdf, run_dir / "png", w, h)
    except Exception:
        return bad("failed", "LibreOffice could not render this file")

    visible = [i for i, hid in enumerate(hidden) if not hid]
    if len(pages) == n:
        return RenderResult("ok", None, list(pages))
    if len(pages) == len(visible):
        slides = list(empty)
        for idx, page in zip(visible, pages):
            slides[idx] = page
        return RenderResult("ok", None, slides)
    return bad("failed", "page count did not match slide count")
