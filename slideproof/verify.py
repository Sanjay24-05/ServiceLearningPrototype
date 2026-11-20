"""Export fixes to a copy, re-check it, and roll back fixes that do not work."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from slideproof.analysis import Analysis, analyse
from slideproof.findings import Fix
from slideproof.fixes import apply_fixes


@dataclass
class ExportResult:
    output: Path | None
    applied: list[Fix]
    rolled_back: list[tuple[Fix, str]]
    resolved: int
    new_visible: int
    final: Analysis | None


def export_and_verify(original: Analysis, selected: list[Fix], out: Path,
                      run_dir: Path,
                      progress: Callable[[str], None] = lambda m: None
                      ) -> ExportResult:
    active = list(selected)
    rolled_back: list[tuple[Fix, str]] = []
    before_keys = {f.key for f in original.findings}
    by_fix = {f.fix.fix_id: f for f in original.findings if f.fix}
    for attempt in range(len(selected) + 1):
        if not active:
            if out.exists():
                out.unlink()
            return ExportResult(None, [], rolled_back, 0, 0, None)
        progress("Applying fixes…")
        try:
            apply_fixes(original.deck.path, out, active)
        except Exception:
            if out.exists():
                out.unlink()
            raise
        after = analyse(out, run_dir / f"verify{attempt}",
                        lambda m: progress("Checking the corrected copy: " + m))
        after_keys = {f.key for f in after.findings}
        bad: list[tuple[Fix, str]] = []
        for fx in active:
            target = by_fix[fx.fix_id]
            if target.key in after_keys:
                bad.append((fx, "the problem was still there after the fix"))
            elif any(f.severity == "visible" and f.key not in before_keys
                     and fx.element_id in f.element_ids for f in after.findings):
                bad.append((fx, "it caused a new problem"))
        if not bad:
            resolved = len([f for f in original.findings
                            if f.key not in after_keys])
            new_visible = len([f for f in after.findings
                               if f.severity == "visible"
                               and f.key not in before_keys])
            return ExportResult(out, active, rolled_back, resolved,
                                new_visible, after)
        rolled_back += bad
        bad_ids = {b[0].fix_id for b in bad}
        active = [fx for fx in active if fx.fix_id not in bad_ids]
    return ExportResult(None, [], rolled_back, 0, 0, None)
