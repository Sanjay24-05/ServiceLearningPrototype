"""EMU unit helpers and axis-aligned rectangle geometry."""
from __future__ import annotations

import math
from dataclasses import dataclass

EMU_PER_INCH = 914400
EMU_PER_PT = 12700


def inches(v: float) -> int:
    return round(v * EMU_PER_INCH)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def intersect(self, other: Rect) -> Rect | None:
        x, y = max(self.x, other.x), max(self.y, other.y)
        r, b = min(self.right, other.right), min(self.bottom, other.bottom)
        if r <= x or b <= y:
            return None
        return Rect(x, y, r - x, b - y)

    def contains(self, other: Rect) -> bool:
        return (self.x <= other.x and self.y <= other.y
                and other.right <= self.right and other.bottom <= self.bottom)

    def translate(self, dx: int, dy: int) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]

    @classmethod
    def from_list(cls, v: list[int]) -> Rect:
        return cls(v[0], v[1], v[2], v[3])


def rotated_aabb(frame: Rect, degrees: float) -> Rect:
    """Axis-aligned bounding box of `frame` rotated about its centre."""
    t = math.radians(degrees)
    c, s = abs(math.cos(t)), abs(math.sin(t))
    w = frame.w * c + frame.h * s
    h = frame.w * s + frame.h * c
    cx, cy = frame.center
    return Rect(round(cx - w / 2), round(cy - h / 2), round(w), round(h))
