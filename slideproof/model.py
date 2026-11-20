"""Plain dataclasses describing a loaded presentation in absolute EMU coordinates."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from slideproof.units import Rect

Kind = Literal["title", "body", "textbox", "picture", "shape", "table", "chart", "group", "other"]


@dataclass
class ImageInfo:
    px_w: int
    px_h: int
    crop: tuple[float, float, float, float]  # left, top, right, bottom
    alt: str | None
    filename: str | None


@dataclass
class RunStyle:
    font: str | None
    size_pt: float | None
    bold: bool | None
    rgb: tuple[int, int, int] | None


@dataclass
class Element:
    id: str
    slide_index: int
    slide_id: int
    shape_id: int
    name: str
    kind: Kind
    frame: Rect
    bbox: Rect
    z: int
    rotation: float
    filled: bool
    text: str | None = None
    runs: list[RunStyle] = field(default_factory=list)
    image: ImageInfo | None = None
    placeholder_type: str | None = None
    group_id: str | None = None
    fixable: bool = True  # False when no fix may be offered (e.g. duplicate shape id)


@dataclass
class SlideModel:
    index: int
    slide_id: int
    hidden: bool
    title_text: str | None
    elements: list[Element] = field(default_factory=list)
    skipped_shapes: list[str] = field(default_factory=list)


@dataclass
class DeckModel:
    path: Path
    slide_w: int
    slide_h: int
    slides: list[SlideModel] = field(default_factory=list)

    @property
    def slide_rect(self) -> Rect:
        return Rect(0, 0, self.slide_w, self.slide_h)

    def element(self, id: str) -> Element:
        for s in self.slides:
            for e in s.elements:
                if e.id == id:
                    return e
        raise KeyError(id)
