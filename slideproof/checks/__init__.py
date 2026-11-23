"""Check registry."""
from __future__ import annotations

from typing import Callable

from slideproof.checks.distortion import check_distortion
from slideproof.checks.offslide import check_offslide
from slideproof.checks.overlap import check_overlap
from slideproof.checks.overflow import check_overflow
from slideproof.checks.resolution import check_resolution
from slideproof.checks.stray import check_stray
from slideproof.checks.textsize import check_textsize
from slideproof.checks.titles import check_titles
from slideproof.checks.fonts import check_fonts
from slideproof.findings import Finding

CHECKS: list[Callable] = [check_offslide, check_distortion, check_overlap,
                             check_resolution, check_stray, check_titles, check_fonts,
                             check_overflow, check_textsize]


def run_checks(deck, render) -> list[Finding]:
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(deck, render))
    return findings
