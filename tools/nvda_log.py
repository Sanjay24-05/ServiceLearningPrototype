"""Read what NVDA said from its IO-level log."""
from __future__ import annotations

import re


def spoken(text: str) -> list[str]:
    """The lines NVDA spoke in this piece of its log, each with its parts joined by " | "."""
    out = []
    for m in re.finditer(r"Speaking \[(.*)\]", text):
        parts = [a or b for a, b in re.findall(r"""'([^']*)'|"([^"]*)\"""", m.group(1))]
        line = " | ".join(p for p in parts if p not in ("en_US",))
        if line:
            out.append(line)
    return out
