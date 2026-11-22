import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _trainer():
    spec = importlib.util.spec_from_file_location("train_intent_model",
                                                  ROOT / "tools" / "train_intent_model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["train_intent_model"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def run_a(tmp_path_factory):
    d = tmp_path_factory.mktemp("a")
    return d, _trainer().train(d, d / "card.md", n_decks=12)


def test_quick_training_writes_artifacts(run_a):
    d, _ = run_a
    for n in ("model.joblib", "features.json", "metrics.json", "card.md"):
        assert (d / n).is_file()
    f = json.loads((d / "features.json").read_text())
    assert f["version"] == 1 and f["family"] in ("logreg", "hgb")


def test_training_is_reproducible(run_a, tmp_path):
    _, m1 = run_a
    m2 = _trainer().train(tmp_path, tmp_path / "card.md", n_decks=12)
    assert m1 == m2


def test_card_states_synthetic(run_a):
    d, _ = run_a
    first = (d / "card.md").read_text(encoding="utf-8").split("\n\n")
    para = next(p for p in first if p.strip() and not p.lstrip().startswith("#"))
    assert "All training data is synthetic" in para


def test_threshold_meets_safety_or_flags(run_a):
    _, m = run_a
    assert m["mistake_recall"] >= 0.95 or m["safety_target_missed"] is True
