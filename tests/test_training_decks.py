import importlib.util
from pathlib import Path

from slideproof.intent.features import raw_candidates
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
