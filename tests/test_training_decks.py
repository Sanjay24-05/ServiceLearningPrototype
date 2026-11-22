import importlib.util
from pathlib import Path

from slideproof.intent.features import FEATURES, features_for, raw_candidates
from slideproof.loader import load_deck

_SPEC = importlib.util.spec_from_file_location(
    "make_training_decks", Path(__file__).resolve().parents[1] / "tools" / "make_training_decks.py")
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
build_training_decks = _MOD.build_training_decks


def _signature(paths):
    out = []
    for p in paths:
        deck = load_deck(p)
        names = {e.id: e.name for s in deck.slides for e in s.elements}
        out.append([(c.check_id, c.slide_index, tuple(names[i] for i in c.element_ids))
                    for c in raw_candidates(deck)])
    return out


def test_builds_requested_number_of_decks(tmp_path):
    paths = build_training_decks(tmp_path, 3, 1)
    assert len(paths) == 3 and all(p.suffix == ".pptx" and p.exists() for p in paths)
    for p in paths:
        assert 6 <= len(load_deck(p).slides) <= 10


def test_same_seed_same_decks(tmp_path):
    a = _signature(build_training_decks(tmp_path / "a", 3, 1))
    b = _signature(build_training_decks(tmp_path / "b", 3, 1))
    assert a == b and any(a)


def test_both_classes_present(tmp_path):
    sig = _signature(build_training_decks(tmp_path, 5, 2))
    flat = [names for deck in sig for _, _, names in deck]
    assert sum(any(n.startswith("deliberate-") for n in ns) for ns in flat) >= 10
    assert sum(any(n.startswith("mistake-") for n in ns) for ns in flat) >= 10


def _labelled_rows(paths):
    """Feature vectors of raw candidates, labelled by name prefix (mixed or unlabelled are dropped)."""
    rows = {"deliberate": [], "mistake": []}
    for p in paths:
        deck = load_deck(p)
        names = {e.id: e.name for s in deck.slides for e in s.elements}
        for c in raw_candidates(deck):
            ns = [names[i] for i in c.element_ids]
            d = any(n.startswith("deliberate-") for n in ns)
            m = any(n.startswith("mistake-") for n in ns)
            if d != m:
                rows["deliberate" if d else "mistake"].append(
                    features_for(c.check_id, c.element_ids, c.magnitude, deck))
    return rows


def test_all_pattern_kinds_appear(tmp_path):
    import re
    paths = build_training_decks(tmp_path, 30, 7)
    names = {e.name for p in paths for s in load_deck(p).slides for e in s.elements}
    assert len(_MOD.PATTERN_KINDS) == 16
    for kind in _MOD.PATTERN_KINDS:
        assert any(re.match(rf"^(deliberate|mistake)-{kind}-\d+", n) for n in names), kind


def test_no_single_feature_separates_the_classes(tmp_path):
    """For each feature, both classes need >= 10% of their rows on each side of a split.

    Binary features split on their value. Others split on the pooled median (values above it vs
    the rest; values at or above it when nothing lies above). A class that sits wholly on one side
    would let a model read the label from that feature alone.
    """
    rows = _labelled_rows(build_training_decks(tmp_path, 30, 7))
    assert len(rows["deliberate"]) > 100 and len(rows["mistake"]) > 100
    for name in ["edges_touched", "span_w", "area_share", "has_text", "upper_inside_lower",
                 "lower_is_text", "repeats"]:
        j = FEATURES.index(name)
        cols = {k: [r[j] for r in v] for k, v in rows.items()}
        pooled = cols["deliberate"] + cols["mistake"]
        if set(pooled) <= {0.0, 1.0}:
            sides = lambda v: v == 1.0
        else:
            med = sorted(pooled)[len(pooled) // 2]
            sides = (lambda v: v > med) if any(v > med for v in pooled) else (lambda v: v >= med)
        for k, col in cols.items():
            share = sum(map(sides, col)) / len(col)
            assert 0.10 <= share <= 0.90, (name, k, round(share, 2))
