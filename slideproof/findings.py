"""Finding and Fix records produced by checks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Fix:
    kind: str  # "F1".."F7"
    safety: Literal["safe", "confirm"]
    element_id: str
    params: dict

    @property
    def fix_id(self) -> str:
        return f"{self.kind}:{self.element_id}"


@dataclass
class Finding:
    check_id: str
    slide_index: int
    slide_id: int
    element_ids: tuple[str, ...]
    severity: str
    confidence: str
    magnitude: float
    measurements: dict
    fix: Fix | None = None

    @property
    def key(self) -> tuple:
        return (self.check_id, self.slide_id, self.element_ids)

    @property
    def id(self) -> str:
        return f"{self.check_id}-{self.slide_id}-{'-'.join(self.element_ids)}"
