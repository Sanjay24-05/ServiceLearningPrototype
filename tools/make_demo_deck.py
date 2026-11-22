"""Build the Slide Proof demo deck and its ground-truth findings.

Usage: python tools/make_demo_deck.py <out_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from slideproof.demo_deck import build_demo_deck  # noqa: E402

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/output")
    for p in build_demo_deck(out):
        print(p)
