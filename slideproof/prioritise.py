"""Rank findings and collapse noisy groups."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from slideproof.findings import Finding

_SEVERITY = {"visible": 2, "minor": 1}
_CONFIDENCE = {"definite": 1.0, "likely": 0.7}
GROUP_THRESHOLD = 5


@dataclass
class Report:
    visible: list[Finding]
    minor: list[Finding]
    slides_checked: int
    slides_with_visible: int
    intentional: list[Finding] = field(default_factory=list)


def score(f: Finding) -> float:
    return _SEVERITY[f.severity] * f.magnitude * _CONFIDENCE[f.confidence]


def _group(findings: list[Finding]) -> list[Finding]:
    buckets: dict[tuple, list[Finding]] = defaultdict(list)
    for f in findings:
        buckets[(f.check_id, f.slide_index)].append(f)
    out: list[Finding] = []
    for group in buckets.values():
        if len(group) <= GROUP_THRESHOLD:
            out.extend(group)
            continue
        ids = tuple(sorted({e for f in group for e in f.element_ids}))
        severity = "visible" if any(f.severity == "visible" for f in group) else "minor"
        out.append(replace(group[0], element_ids=ids, severity=severity,
                           magnitude=max(f.magnitude for f in group),
                           measurements={"grouped": len(group)}, fix=None))
    return out


def prioritise(findings: list[Finding], slides_checked: int,
               intent_threshold: float | None = None) -> Report:
    def intentional(f: Finding) -> bool:
        return (intent_threshold is not None
                and f.measurements.get("intent_p", 0.0) >= intent_threshold)

    # tiers are split before grouping, so a grouped finding never mixes tiers
    tier = [f for f in findings if intentional(f)]
    rest = [f for f in findings if not intentional(f)]

    def ranked(fs):
        return sorted(_group(fs), key=lambda f: (-score(f), f.slide_index))

    ordered = ranked(rest)
    visible = [f for f in ordered if f.severity == "visible"]
    minor = [f for f in ordered if f.severity != "visible"]
    return Report(visible, minor, slides_checked, len({f.slide_index for f in visible}),
                  ranked(tier))
