"""C9: a font used almost nowhere else in the deck (spec §7.1 C9), counted from the file's runs."""
from __future__ import annotations

from collections import Counter

from slideproof.findings import Finding

THEME = "(theme)"
_STRAY_SHARE = 0.10
_MAX_SLIDES = 2
_MAIN_SHARE = 0.50
_IGNORED_PREFIXES = ("symbol", "wingdings", "webdings", "consolas", "courier new", "cascadia")


def _family(run, theme_fonts) -> str | None:
    name = run.font
    if name is None or name in theme_fonts or name.startswith("+"):
        return THEME
    if name.lower().startswith(_IGNORED_PREFIXES):
        return None
    return name


def check_fonts(deck, render=None) -> list[Finding]:
    chars: Counter = Counter()
    slides_of: dict[str, set[int]] = {}
    uses: list[tuple] = []  # (slide, element, family)
    theme_fonts = getattr(deck, "theme_fonts", set())
    for s in deck.slides:
        for e in s.elements:
            text_len = len((e.text or "").strip())
            if not text_len or not e.runs:
                continue
            per_run = max(1, text_len // len(e.runs))
            fams = set()
            for r in e.runs:
                fam = _family(r, theme_fonts)
                if fam is None:
                    continue
                chars[fam] += per_run
                slides_of.setdefault(fam, set()).add(s.index)
                fams.add(fam)
            uses.extend((s, e, f) for f in fams)
    total = sum(chars.values())
    if not total:
        return []
    main, main_count = chars.most_common(1)[0]
    if main_count / total < _MAIN_SHARE:
        return []
    stray = {f for f, n in chars.items()
             if f != THEME and n / total < _STRAY_SHARE and len(slides_of[f]) <= _MAX_SLIDES}
    main_name = "the theme font" if main == THEME else main
    return [Finding("C9", s.index, s.slide_id, (e.id,), "minor", "definite",
                    1 - chars[f] / total, {"font": f, "main_font": main_name})
            for s, e, f in uses if f in stray]
