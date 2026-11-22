"""Trains and evaluates the intent model on synthetic decks (spec 5.3-5.4).

Usage: python tools/train_intent_model.py [--quick]

Writes slideproof/intent/{model.joblib,features.json,metrics.json} and docs/ml/intent-model-card.md.
All randomness is seeded; two runs with the same seed give identical metrics.
"""
from __future__ import annotations

import importlib.util
import json
import random
import re
import subprocess
import sys
import tempfile
import time
import warnings
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from slideproof.checks import run_checks  # noqa: E402
from slideproof.intent.features import FEATURES, features_for, raw_candidates  # noqa: E402
from slideproof.loader import load_deck  # noqa: E402

MODEL_DIR = ROOT / "slideproof" / "intent"
CARD_PATH = ROOT / "docs" / "ml" / "intent-model-card.md"
YELLOW_IDEA = Path(r"C:\Program Files\LibreOffice\share\template\common\presnt\Yellow_Idea.otp")
CAP_PER_INSTANCE = 3
INSTANCE = re.compile(r"^((?:deliberate|mistake)-.*?-\d+)")


def _generator():
    spec = importlib.util.spec_from_file_location("make_training_decks",
                                                  ROOT / "tools" / "make_training_decks.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["make_training_decks"] = mod
    spec.loader.exec_module(mod)
    return mod


def _label(names):
    """1 deliberate, 0 mistake, None drop (mixed prefixes or no labelled element)."""
    d = any(n.startswith("deliberate-") for n in names)
    m = any(n.startswith("mistake-") for n in names)
    if d == m:
        return None
    return 1 if d else 0


def _instance(names, label):
    prefix = "deliberate-" if label else "mistake-"
    for n in names:
        if n.startswith(prefix):
            mt = INSTANCE.match(n)
            return mt.group(1) if mt else n
    return ""


def build_dataset(n_decks: int, seed: int):
    rows = []  # (group, label, instance, features, check_id)
    dropped = {"mixed": 0, "content_only": 0}
    with tempfile.TemporaryDirectory() as tmp:
        paths = _generator().build_training_decks(Path(tmp), n_decks, seed)
        for gi, p in enumerate(paths):
            deck = load_deck(p)
            for c in raw_candidates(deck):
                names = [deck.element(e).name for e in c.element_ids]
                lab = _label(names)
                if lab is None:
                    key = "mixed" if any(n.startswith("deliberate-") for n in names) else "content_only"
                    dropped[key] += 1
                    continue
                f = features_for(c.check_id, c.element_ids, c.magnitude, deck)
                rows.append((gi, lab, _instance(names, lab), f, c.check_id))
    before = _counts(rows)
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r[0], r[2])].append(r)
    kept = []
    for key in sorted(buckets):
        b = buckets[key]
        if len(b) > CAP_PER_INSTANCE:
            b = rng.sample(b, CAP_PER_INSTANCE)
        kept.extend(b)
    after = _counts(kept)
    X = np.array([r[3] for r in kept])
    y = np.array([r[1] for r in kept])
    g = np.array([r[0] for r in kept])
    return X, y, g, before, after, dropped


def _counts(rows):
    return {"deliberate": sum(1 for r in rows if r[1] == 1),
            "mistake": sum(1 for r in rows if r[1] == 0), "total": len(rows)}


class _Logreg:
    """Logistic-regression pipeline; silences scipy's OptimizeWarning only around the fit."""

    def __init__(self):
        self.pipe = make_pipeline(StandardScaler(),
                                  LogisticRegression(max_iter=1000, class_weight="balanced"))

    def fit(self, X, y):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Unknown solver options")
            self.pipe.fit(X, y)
        return self.pipe


def _logreg():
    return _Logreg()


def _hgb(seed):
    return HistGradientBoostingClassifier(random_state=seed)


def _oof(make, X, y, g):
    p = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        m = make().fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


def _at(p, y, t):
    pred = p >= t
    tp = int(np.sum(pred & (y == 1))); fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1))); tn = int(np.sum(~pred & (y == 0)))
    prec = tp / (tp + fp) if tp + fp else 0.0
    drec = tp / (tp + fn) if tp + fn else 0.0
    mrec = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * prec * drec / (prec + drec) if prec + drec else 0.0
    return {"mistake_recall": round(mrec, 4), "deliberate_recall": round(drec, 4),
            "precision": round(prec, 4), "f1": round(f1, 4),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}


def pick_threshold(p, y):
    """Smallest t >= 0.80 on a 0.01 grid with mistake recall >= 0.95, else 0.99 (flagged)."""
    neg = p[y == 0]
    for k in range(80, 100):
        t = k / 100
        if len(neg) and np.mean(neg < t) >= 0.95:
            return t, False
    return 0.99, True


# ---------------------------------------------------------------- held-out real decks
def _judge(deck, model, t, planted):
    """Apply the model to C1/C2 findings (C2 only when the upper is a picture or filled shape)."""
    judged = moved = planted_total = planted_moved = 0
    moved_list = []
    for f in run_checks(deck, None):
        if f.check_id not in ("C1", "C2"):
            continue
        if f.check_id == "C2":
            up = deck.element(f.element_ids[0])
            if not (up.kind == "picture" or up.filled):
                continue
        names = {deck.element(e).name for e in f.element_ids}
        is_planted = any(r["check"] == f.check_id and r["slide"] == f.slide_index
                         and set(r["shapes"]) <= names for r in planted)
        p = float(model.predict_proba(
            np.array([features_for(f.check_id, f.element_ids, f.magnitude, deck)]))[0, 1])
        judged += 1
        would_move = p >= t
        moved += would_move
        if is_planted:
            planted_total += 1
            planted_moved += would_move
        if would_move:
            moved_list.append({"check": f.check_id, "slide": f.slide_index,
                               "shapes": sorted(names), "p": round(p, 3), "planted": is_planted})
    return {"judged": judged, "moved": int(moved), "planted": planted_total,
            "planted_moved": int(planted_moved), "moved_findings": moved_list}


def held_out(model, t, quick: bool) -> dict:
    from slideproof.demo_deck import build_demo_deck
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        deck_p, gt_p = build_demo_deck(tmp / "demo")
        planted = [r for r in json.loads(gt_p.read_text(encoding="utf-8")) if r["check"] in ("C1", "C2")]
        out["demo_deck"] = _judge(load_deck(deck_p), model, t, planted)

        corpus = tmp / "corpus"
        corpus.mkdir()
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_test_decks.py"), str(corpus)],
                       check=True, capture_output=True)
        expect = json.loads((corpus / "expected.json").read_text())
        agg = {"judged": 0, "moved": 0, "planted": 0, "planted_moved": 0, "moved_findings": []}
        for name in sorted(expect):
            rows = [{"check": c, "slide": s, "shapes": [n]} for c, s, n in expect[name] if c in ("C1", "C2")]
            r = _judge(load_deck(corpus / name), model, t, rows)
            for k in ("judged", "moved", "planted", "planted_moved"):
                agg[k] += r[k]
            agg["moved_findings"] += [dict(m, deck=name) for m in r["moved_findings"]]
        out["corpus"] = agg

        out["yellow_idea"] = {"status": "skipped (quick mode)"} if quick else _yellow(model, t, tmp)
    return out


def _yellow(model, t, tmp: Path) -> dict:
    from slideproof.render.soffice import find_soffice
    soffice = find_soffice()
    if soffice is None or not YELLOW_IDEA.is_file():
        return {"status": "skipped (LibreOffice or template not found)"}
    out_dir = tmp / "yellow"
    out_dir.mkdir()
    prof = tmp / "profile"
    prof.mkdir()
    subprocess.run([str(soffice), "--headless", "--norestore",
                    f"-env:UserInstallation={prof.resolve().as_uri()}",
                    "--convert-to", "pptx", "--outdir", str(out_dir), str(YELLOW_IDEA)],
                   check=True, capture_output=True, timeout=180)
    pptx = out_dir / "Yellow_Idea.pptx"
    if not pptx.is_file():
        return {"status": "skipped (conversion failed)"}
    r = _judge(load_deck(pptx), model, t, [])
    r["status"] = "ok"
    return r


# ---------------------------------------------------------------- orchestration
def train(out_model_dir: Path, card_path: Path, n_decks: int = 120, seed: int = 7) -> dict:
    out_model_dir = Path(out_model_dir)
    card_path = Path(card_path)
    out_model_dir.mkdir(parents=True, exist_ok=True)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    X, y, g, before, after, dropped = build_dataset(n_decks, seed)

    p_lr = _oof(_logreg, X, y, g)
    p_hg = _oof(lambda: _hgb(seed), X, y, g)
    t_lr, miss_lr = pick_threshold(p_lr, y)
    t_hg, miss_hg = pick_threshold(p_hg, y)
    fam = {"logreg": {"threshold": t_lr, "target_missed": miss_lr, **_at(p_lr, y, t_lr)},
           "hgb": {"threshold": t_hg, "target_missed": miss_hg, **_at(p_hg, y, t_hg)}}
    ship = "hgb" if fam["hgb"]["f1"] - fam["logreg"]["f1"] > 0.05 else "logreg"
    t, missed = fam[ship]["threshold"], fam[ship]["target_missed"]
    model = _logreg().fit(X, y) if ship == "logreg" else _hgb(seed).fit(X, y)
    joblib.dump(model, out_model_dir / "model.joblib")
    (out_model_dir / "features.json").write_text(json.dumps(
        {"version": 1, "features": FEATURES, "sklearn": sklearn.__version__,
         "threshold": t, "family": ship}, indent=2), encoding="utf-8")

    hold = held_out(model, t, quick=n_decks < 40)
    planted_moved = hold["demo_deck"]["planted_moved"] + hold["corpus"]["planted_moved"]
    metrics = {
        "n_decks": n_decks, "seed": seed, "family": ship, "threshold": t,
        "safety_target_missed": bool(missed),
        "mistake_recall": fam[ship]["mistake_recall"],
        "deliberate_recall": fam[ship]["deliberate_recall"],
        "precision": fam[ship]["precision"], "f1": fam[ship]["f1"],
        "class_counts_before_cap": before, "class_counts_after_cap": after,
        "rows_dropped": dropped, "cap_per_instance": CAP_PER_INSTANCE,
        "families": fam, "held_out": hold,
        "planted_mistakes_moved": planted_moved,
        "yellow_idea_moved": hold["yellow_idea"].get("moved"),
    }
    (out_model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    card_path.write_text(render_card(metrics), encoding="utf-8")
    return metrics


def _row(name, m):
    c = m["confusion"]
    return (f"| {name} | {m['threshold']:.2f} | {m['mistake_recall']:.3f} | {m['deliberate_recall']:.3f} "
            f"| {m['precision']:.3f} | {m['f1']:.3f} | {c['tp']} / {c['fp']} / {c['fn']} / {c['tn']} |")


def _held(name, r):
    if "judged" not in r:
        return f"| {name} | {r['status']} | | | |"
    return f"| {name} | {r['judged']} | {r['moved']} | {r['planted']} | {r['planted_moved']} |"


def render_card(m: dict) -> str:
    b, a, h = m["class_counts_before_cap"], m["class_counts_after_cap"], m["held_out"]
    fam = m["families"]
    names = {"logreg": "Logistic regression", "hgb": "Gradient boosting"}
    if m["safety_target_missed"]:
        status = "The safety target (mistake recall of at least 0.95) was **missed**; the threshold was fixed at 0.99."
    else:
        status = f"The safety target (mistake recall of at least 0.95) was met at t = {m['threshold']:.2f}."
    yi = h["yellow_idea"]
    yi_txt = (f"{yi['moved']} of {yi['judged']} judged findings would move" if "judged" in yi
              else yi["status"])
    nf = len(FEATURES)
    d, c = h["demo_deck"], h["corpus"]
    yi_judged = yi.get("judged", 0)
    held_txt = (f"Held-out sets are tiny ({d['judged']} demo, {c['judged']} corpus, {yi_judged} Yellow Idea "
                f"judged findings; {d['planted'] + c['planted']} planted mistakes in total); zero planted "
                f"mistakes moved is weak evidence, not proof.")
    mv = yi.get("moved_findings", [])
    if mv:
        listing = "; ".join(f"{x['check']} on slide {x['slide']} (p = {x['p']:.3f})" for x in mv)
        yi_bullet = (f"- The Yellow Idea moves ({listing}) have not been confirmed as deliberate by a person; "
                     f"they are unverified.\n")
    else:
        yi_bullet = "- No Yellow Idea finding was moved, so there is nothing there to verify.\n"
    return f"""# Intent model card

All training data is synthetic. The decks were generated by `tools/make_training_decks.py` with a fixed seed ({m['seed']}); no real student, teacher or institutional slide was used for training or for choosing the threshold. Real decks appear only in the held-out check below.

## Purpose

Slide Proof's off-slide (C1) and overlap (C2) checks flag geometry that may be a mistake or a deliberate design choice (full-bleed background, corner logo, caption band, frame). The model estimates the probability that a candidate is deliberate. Findings with probability at or above the threshold may be moved out of the main list; everything else stays. A wrong move hides a real mistake from a blind user, so **mistake recall wins over usefulness**: the threshold is chosen for mistake recall first.

## Patterns and ranges

{m['n_decks']} decks, each with 2-4 deliberate patterns (`deliberate-<pattern>-<n>`) and 2-4 mistakes (`mistake-<pattern>-<n>`) placed from overlapping position, size and colour ranges, with variants per pattern so no single feature separates the classes. Labels come from element-name prefixes only. A candidate with names from both prefixes, or from neither, is dropped. The model sees {nf} geometric and structural features (see `features.json`), never names or text.

## Class counts

Rows per (deck, pattern instance) are capped at {m['cap_per_instance']} (seeded) so repeated logos, footers and text-panel highlights do not dominate.

| | Deliberate | Mistake | Total |
|---|---|---|---|
| Before cap | {b['deliberate']} | {b['mistake']} | {b['total']} |
| After cap | {a['deliberate']} | {a['mistake']} | {a['total']} |

Dropped before labelling: {m['rows_dropped']['mixed']} mixed-prefix, {m['rows_dropped']['content_only']} content-only candidates.

## Metrics

Five-fold GroupKFold (grouped by deck), out-of-fold probabilities, at each family's own threshold. The threshold and the model family are chosen on the same out-of-fold predictions that are reported here, so the numbers are mildly optimistic. Confusion is TP / FP / FN / TN with "deliberate" as the positive class (FP = a mistake that would be moved).

| Family | Threshold | Mistake recall | Deliberate recall | Precision | F1 | Confusion |
|---|---|---|---|---|---|---|
{_row(names['logreg'], fam['logreg'])}
{_row(names['hgb'], fam['hgb'])}

Shipped: **{names[m['family']]}** (logistic regression unless gradient boosting F1 is more than 0.05 higher).

## Threshold

The smallest t >= 0.80 on a 0.01 grid where out-of-fold mistake recall is at least 0.95. {status} Shipped threshold: {m['threshold']:.2f}.

## Held-out real-deck results

The shipped model is applied to C1 findings and to C2 findings whose upper element is a picture or filled shape. Text-over-text C2 findings are out of distribution and left unjudged.

| Deck set | Judged | Would move | Planted mistakes | Planted moved |
|---|---|---|---|---|
{_held('Demo deck', h['demo_deck'])}
{_held('Test corpus', h['corpus'])}
{_held('Yellow Idea template', yi)}

Planted mistakes moved: **{m['planted_mistakes_moved']}** (must be 0). Yellow Idea: {yi_txt}.

## Known limits

- The training distribution is generated by us, so scores measure agreement with our own generator, not with real designers. Treat them as a sanity check, not a field accuracy.
- {held_txt}
{yi_bullet}- Text-over-text overlaps are not judged. Rotated, grouped and placeholder-heavy designs are lightly covered.
- Generator history: variants were added so no single feature separates the classes, and rows per pattern instance are capped.

## How to retrain

```
.venv/Scripts/python tools/train_intent_model.py          # full, {m['n_decks']} decks, seed {m['seed']}
.venv/Scripts/python tools/train_intent_model.py --quick  # 12 decks, for tests
```

This rewrites `slideproof/intent/model.joblib`, `features.json`, `metrics.json` and this card. scikit-learn is pinned to the version recorded in `features.json`.
"""


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    t0 = time.time()
    if quick:
        with tempfile.TemporaryDirectory() as d:
            res = train(Path(d), Path(d) / "card.md", n_decks=12)
    else:
        res = train(MODEL_DIR, CARD_PATH)
    print(json.dumps({k: res[k] for k in ("family", "threshold", "mistake_recall", "deliberate_recall",
                                          "safety_target_missed", "planted_mistakes_moved",
                                          "yellow_idea_moved")}, indent=2))
    print(f"training took {time.time() - t0:.1f}s")
