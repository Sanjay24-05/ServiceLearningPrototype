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


def test_card_wording_is_honest(run_a):
    d, _ = run_a
    card = (d / "card.md").read_text(encoding="utf-8")
    first = next(p for p in card.split("\n\n") if p.strip() and not p.lstrip().startswith("#"))
    assert "Real decks appear only" not in first
    assert "## Held-out decks (not used in training)" in card and "real-deck" not in card
    assert "hand-built test deck" in card and "only Yellow Idea is a real third-party template" in card
    assert "- Untested on real-world decks." in card
    assert "duplicated-slide mistakes" in card and "text that sticks out is never judged" in card
    assert "demotes a real mistake to the Probably intentional section, with its fix unticked" in card
    assert "hides a real mistake" not in card


def test_card_yellow_listing_has_no_nested_brackets():
    m = _trainer()
    base = {"seed": 7, "n_decks": 1, "cap_per_instance": 3, "safety_target_missed": False, "threshold": 0.8,
            "family": "hgb", "planted_mistakes_moved": 0, "rows_dropped": {"mixed": 0, "content_only": 0}}
    cnt = {"deliberate": 1, "mistake": 1, "total": 2}
    fam = {"mistake_recall": 1, "deliberate_recall": 1, "precision": 1, "f1": 1, "threshold": 0.8,
           "confusion": {"tp": 1, "fp": 0, "fn": 0, "tn": 1}}
    held = {"judged": 1, "moved": 0, "planted": 1, "planted_moved": 0, "moved_findings": []}
    one = {"check": "C1", "slide": 8, "p": 0.997}
    for mv, want in (([one], "- The Yellow Idea move (C1 on slide 8, p = 0.997) has not been confirmed"),
                     ([one, dict(one, slide=9)], "- The Yellow Idea moves (C1 on slide 8, p = 0.997; C1 on "
                                                 "slide 9, p = 0.997) have not been confirmed")):
        yi = dict(held, moved=len(mv), moved_findings=mv, status="ok")
        card = m.render_card(dict(base, class_counts_before_cap=cnt, class_counts_after_cap=cnt,
                                  class_counts_judged=cnt, families={"logreg": fam, "hgb": fam},
                                  held_out={"demo_deck": held, "corpus": held, "yellow_idea": yi}))
        assert want in card
