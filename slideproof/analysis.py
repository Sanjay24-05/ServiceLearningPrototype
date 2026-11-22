"""Analysis pipeline: load, render, check, prioritise."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from slideproof import intent
from slideproof.checks import run_checks
from slideproof.findings import Finding
from slideproof.loader import load_deck
from slideproof.model import DeckModel
from slideproof.prioritise import Report, prioritise
from slideproof.render import RenderResult, render_deck


@dataclass
class Analysis:
    deck: DeckModel
    render: RenderResult
    findings: list[Finding]
    report: Report
    skipped_note: str | None
    intent_note: str | None = None


def analyse(pptx: Path, run_dir: Path,
            progress: Callable[[str], None] = lambda m: None) -> Analysis:
    progress("Reading slides…")
    deck = load_deck(pptx)
    progress("Rendering slides…")
    render = render_deck(pptx, run_dir, [s.hidden for s in deck.slides])
    n = len(deck.slides)
    for i in range(1, n + 1):
        progress(f"Checking slide {i} of {n}…")
    findings = run_checks(deck, render)
    findings, intent_note = intent.judge(findings, deck)
    report = prioritise(findings, n, intent.threshold())
    note = None
    if render.status != "ok":
        note = ("Note: text overflow and contrast checks were skipped because "
                f"{render.reason}.")
    return Analysis(deck, render, findings, report, note, intent_note)
