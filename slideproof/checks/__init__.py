"""Check registry."""
from __future__ import annotations

from typing import Callable

from slideproof.checks.distortion import check_distortion
from slideproof.checks.offslide import check_offslide
from slideproof.findings import Finding

CHECKS: list[Callable] = [check_offslide, check_distortion]


def run_checks(deck, render) -> list[Finding]:
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(deck, render))
    return findings
