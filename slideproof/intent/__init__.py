"""Judge C1/C2 findings with the trained intent model ("probably intentional" tier)."""
from __future__ import annotations

import json
import warnings
from dataclasses import replace
from pathlib import Path

from slideproof.findings import Finding
from slideproof.intent.features import (_TEXT_KINDS, FEATURES, _has_text, c1_outside,
                                      c2_coverage, features_for)

MODEL_DIR = Path(__file__).resolve().parent
UNAVAILABLE_NOTE = 'The "probably intentional" judgement is unavailable in this setup.'
DEFAULT_THRESHOLD = 0.8
_cache: dict = {}  # per-process: {"dir": Path, "bundle": (model, meta) | None}


def _load():
    """(model, meta), or None when the model is missing, mismatched or unreadable. Cached."""
    if _cache.get("dir") == MODEL_DIR:
        return _cache["bundle"]
    bundle = None
    try:
        import joblib
        import sklearn
        import sklearn.ensemble  # noqa: F401  (import now: import-time warnings are harmless)
        import sklearn.linear_model  # noqa: F401
        import sklearn.pipeline  # noqa: F401
        import sklearn.preprocessing  # noqa: F401
        from sklearn.exceptions import InconsistentVersionWarning
        meta = json.loads((MODEL_DIR / "features.json").read_text(encoding="utf-8"))
        if meta.get("sklearn") == sklearn.__version__ and meta.get("features") == FEATURES:
            with warnings.catch_warnings():
                # only a version-mismatch warning means do not trust the pickle
                warnings.simplefilter("error", InconsistentVersionWarning)
                bundle = (joblib.load(MODEL_DIR / "model.joblib"), meta)
    except Exception:
        bundle = None
    _cache["dir"], _cache["bundle"] = MODEL_DIR, bundle
    return bundle


def available() -> bool:
    return _load() is not None


def accuracy() -> dict | None:
    """{'mistake_recall': %, 'deliberate_recall': %} (whole percents) for the shipped model, or None."""
    if not available():
        return None
    try:
        m = json.loads((MODEL_DIR / "metrics.json").read_text(encoding="utf-8"))
        return {k: round(float(m[k]) * 100) for k in ("mistake_recall", "deliberate_recall")}
    except Exception:
        return None


def threshold() -> float:
    b = _load()
    return float(b[1]["threshold"]) if b else DEFAULT_THRESHOLD


def _reasons(vec: list[float]) -> list[str]:
    """Up to two codes, from simple rules on the raw feature values (the shipped model is
    gradient boosting, which has no coefficients; this is the single implementation)."""
    v = dict(zip(FEATURES, vec))
    rules = [
        ("repeats", v["repeats"] >= 1 or v["same_layout_repeats"] >= 1),
        ("edges", v["edges_touched"] >= 2),
        ("span", v["span_w"] >= 0.9 or v["span_h"] >= 0.9),
        ("no_text", v["has_text"] == 0),
        # the upper element of a C2 overlap is above by definition; one element is behind nothing
        ("behind", v["z_rank"] <= 0.2 and v["elements_on_slide"] > 1 and v["is_c2"] == 0),
        ("layout", v["is_placeholder"] == 1),
    ]
    return [code for code, hit in rules if hit][:2]


def _judgeable(f, deck) -> bool:
    """Whether the model may judge this finding (or raw candidate: anything with check_id and
    element_ids). Text that sticks out is never judged: a text box or title pushed off the slide
    is almost always a mistake, even when it is copied onto several slides. The trainer's
    held-out check uses this same function."""
    if f.check_id == "C1":
        e = deck.element(f.element_ids[0])
        return not (e.kind in _TEXT_KINDS or _has_text(e))
    if f.check_id == "C2":
        up = deck.element(f.element_ids[0])
        return up.kind == "picture" or bool(up.filled)
    return False


def _estimate_magnitude(f, deck) -> float:
    """The magnitude as the model was trained on it: estimate-based, never from rendered text.
    Shares its formulas with raw_candidates. (Only non-text C1 is judged, so the C1 branch is a guard.)"""
    if f.check_id == "C1":
        return c1_outside(deck.element(f.element_ids[0]), deck.slide_rect)
    upper, lower = (deck.element(i) for i in f.element_ids[:2])
    cov = c2_coverage(upper, lower)
    return f.magnitude if cov is None else cov


def judge(findings: list[Finding], deck) -> tuple[list[Finding], str | None]:
    bundle = _load()
    if bundle is None:
        return list(findings), UNAVAILABLE_NOTE
    model, _ = bundle
    try:
        todo = [f for f in findings if _judgeable(f, deck)]
    except Exception:
        return list(findings), UNAVAILABLE_NOTE
    if not todo:
        return list(findings), None
    try:
        vecs = {id(f): features_for(f.check_id, f.element_ids, _estimate_magnitude(f, deck), deck) for f in todo}
        probs = model.predict_proba([vecs[id(f)] for f in todo])[:, 1]
        judged = {id(f): (float(p), vecs[id(f)]) for f, p in zip(todo, probs)}
    except Exception:  # a broken model must never break the report
        return list(findings), UNAVAILABLE_NOTE
    out = []
    for f in findings:
        if id(f) in judged:
            p, vec = judged[id(f)]
            f = replace(f, measurements={**f.measurements, "intent_p": p,
                                         "intent_reasons": _reasons(vec),
                                         "intent_repeats": int(vec[FEATURES.index("repeats")])})
        out.append(f)
    return out, None
