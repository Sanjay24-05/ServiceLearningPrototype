# Slide Proof: "Mistake or on purpose?" model, and a presentable prototype

**Design document · 2026-11-22 · Status: draft for approval**
Builds on: `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md` (the main spec) and M0–M2 (merged or in PR on `m2-geometry`).

---

## 1. Intent and why

**Why now.** The faculty expects the prototype to include an AI/ML component that helps its users. Separately, the prototype needs to look and run well when it is presented.

**The user problem the ML solves.** Slide Proof's checks are rules ("more than 2% outside the slide", "a picture covers 5% of a text box"). Rules can't tell a **mistake** from a **design choice**. The M1 and M2 audits found real cases:
- Yellow Idea's half-donut chart deliberately runs off the edge, and the tool reports five visible "sticks out" problems.
- Decorative strips, corner badges and bleed photos sit right at the boundary of the rules.

Every false alarm costs a blind user time. Worse, it teaches them not to trust the report, and they can't glance at the slide to dismiss it themselves. Telling mistakes from intent is a judgement problem, and judgement problems are what machine learning is good at.

**What we build.**
1. **An intent model.** A small, local, explainable machine-learning model that estimates, for each finding, how likely it is to be a deliberate design choice rather than a mistake. Findings the model is confident are deliberate move into a separate "Probably intentional" section. They are never deleted. Each one comes with a plain-language reason.
2. **A presentable prototype.** A clean visual design for the sighted people watching a demo, a one-click demo deck, a before/after view of fixed slides, and a short "How it works" page that includes the model's measured accuracy. Screen-reader structure stays unchanged.

## 2. Goals, non-goals, anti-goals

**Goals**
- Fewer false alarms on deliberate designs, with real mistakes still reported.
- A real, measurable ML component: a training set, a held-out evaluation, and metrics reported in a model card.
- Every model decision is explained in words a screen-reader user can hear.
- Everything still runs locally. Files never leave the computer.
- The prototype can be demonstrated end to end, smoothly, to a mixed sighted and blind audience.

**Non-goals (for this work)**
- Describing image content, captioning, or visual critique of slides (approaches #2 and #3 below; possible later).
- Learning from each user's own feedback ("Mark as intentional" arrives in M4; learning from it is future work).
- Packaging an installer.

**Anti-goals (this would be a failure even if it technically works)**
- **The model hides a real mistake** with no way to find it. Every finding stays reachable, and the "Probably intentional" section is always listed in the summary.
- **"Black box" verdicts.** A reason the user can't hear or check isn't acceptable.
- **A cloud dependency** or sending deck content anywhere.
- **A polished look that degrades the screen-reader experience.** The transcript and axe tests must still pass with their current structure.

## 3. Constraints

- Python 3.12 on the developer's Windows laptop; local only (main spec §5.1a).
- New dependency: `scikit-learn` (pinned, CPU only), plus `joblib`, which comes with it. No GPU, no downloads at run time.
- The model file ships in the repository (it is small, a few hundred KB at most). It is trained by a script anyone can re-run. If the model file or scikit-learn is missing, the tool behaves exactly as it does today.
- Checks never produce prose; presenters never compute geometry (main spec §5.3). The model sits between the checks and the prioritiser.

## 4. Approaches considered

| # | Approach | Trade-off | Decision |
|---|---|---|---|
| 1 | **Intent model.** A small classifier over features of each finding: mistake vs deliberate | Runs locally and privately; measurable; tackles the measured trust problem. Less flashy; training data is partly synthetic | **Chosen** (user's pick) |
| 2 | Local image captioning to draft alt text for pictures | Impressive demo, but drifts towards "camera description", which the user ruled out at the start, and PowerPoint already does it | Not now; possible bonus later |
| 3 | A vision model giving a sighted-eye impression of each slide | Richest output, but needs a cloud model (breaks privacy) and can make things up | Rejected |

**Model family (designer's call).** Logistic regression on hand-built features is the shipped model, because each feature's contribution can be turned into a spoken reason. A gradient-boosted tree model (`HistGradientBoostingClassifier`) is trained alongside it as a comparison and reported in the model card. Logistic regression stays the shipped model unless gradient boosting beats it by more than 5 points of F1 on the held-out templates. If it does, ship gradient boosting and derive reasons from the rule-based feature phrases instead (§5.5).

## 5. Part A: the intent model

### 5.1 Scope

The model judges **C1 (sticks out)** and **C2 (overlap)** findings: the checks where intent is genuinely ambiguous and where the audits found false alarms. Other checks are left untouched for now.

### 5.2 Features (one vector per finding)

All features are computed from the existing model (`DeckModel`, `Element`, `Finding`). No pixels are needed.

| Feature | Meaning |
|---|---|
| `check` | C1 or C2 (one-hot) |
| `magnitude` | outside fraction (C1) or coverage (C2) |
| `edges_touched` | number of slide edges the element's bbox reaches or crosses (0–4) |
| `span_w`, `span_h` | element width and height ÷ slide width and height |
| `area_share` | element area ÷ slide area |
| `has_text` | whether the element has text |
| `kind_*` | picture / shape / text / chart / table / other (one-hot) |
| `is_placeholder` | whether the element is a placeholder |
| `in_group` | whether the element is part of a group |
| `z_rank` | position in the stacking order, normalised 0–1 within the slide |
| `repeats_across_slides` | number of other slides with an element of the same kind and nearly the same geometry (±0.1 in), a strong sign of template decoration |
| `same_layout_repeats` | the same, counted only on slides with the same layout |
| `elements_on_slide` | clutter |
| `rotated` | whether the element is rotated |
| C2 only: `lower_is_text`, `upper_kind_*`, `upper_inside_lower` | relation between the two elements |

### 5.3 Training data (generated locally, labelled automatically)

- **Deliberate examples.** Run the checks on every installed LibreOffice template (23 today), the realistic corpus from `tools/make_test_decks.py`, and the demo deck's clean slides. Every C1/C2 finding these designer-made or clean decks produce is labelled **deliberate**.
- **Mistake examples.** New script `tools/make_training_mistakes.py` takes the *same* decks and applies random, realistic perturbations:
  - nudge a text box or picture past one edge by 10–60%;
  - drag a picture over a text box (10–80% coverage);
  - paste a box partly off the slide;
  - duplicate and offset an object.
  Each perturbation is labelled **mistake**, with a fixed random seed. Both classes come from the same decks, so the model learns the *pattern*, not which deck it came from.
- **Balance.** Cap the number of examples per deck so one template can't dominate. Report class counts in the model card.

### 5.4 Training and evaluation

- **Script:** `tools/train_intent_model.py`. It builds the dataset, trains both model families, evaluates them, and writes:
  - `slideproof/intent/model.joblib`
  - `slideproof/intent/features.json` (feature order and version)
  - `docs/ml/intent-model-card.md`
- **Evaluation:** leave-one-template-out (grouped) cross-validation, so the score always comes from decks the model never saw.
  - Metrics: precision, recall and F1 for "deliberate"; the confusion matrix; the calibration curve.
  - **Mistake recall is the key safety number:** the share of real mistakes *not* sent to "Probably intentional".
- **Success criteria (both must hold on held-out decks):**
  - At least 95% of synthetic mistakes stay in the main lists (classified "mistake").
  - At least 50% of the findings on designer templates move to "Probably intentional".
  - And the demo deck's planted mistakes all stay in the main lists (asserted in a test).
- **Model card** (`docs/ml/intent-model-card.md`): purpose, data sources, labelling method, class counts, metrics, known limits (synthetic mistakes; LibreOffice templates as the stand-in for designer decks), and how to retrain.

### 5.5 Using the prediction

- **Inference:** `slideproof/intent/__init__.py` exposes `judge(findings, deck) -> list[Finding]`. It adds to each C1/C2 finding's `measurements`:
  - `"intent_p"`: the probability that it's deliberate;
  - `"intent_reasons"`: up to two short reason codes.
  `analyse()` calls it after `run_checks` and before `prioritise`. If the model can't be loaded, it returns the findings unchanged and the report says "The 'probably intentional' judgement is unavailable."
- **Threshold:** `intent_p ≥ 0.80`. The finding moves to a new **"Probably intentional"** tier, after "Minor polish".
  - Its fix checkbox (if any) is **unchecked by default**.
  - It is never removed, and the user can still apply its fix.
  - The threshold is a constant in one place, tuned on the held-out evaluation so that mistake recall stays at or above 95%.
- **Report wording** (follows main spec §8; new copy):
  - Summary: `… 2 minor, 3 probably intentional.`
  - Section: `<h2>Probably intentional (3)</h2>` with one sentence: "Slide Proof's model thinks these look like deliberate design. Check them if you are unsure."
  - Each finding keeps its normal headline and full text, plus one sentence: `"Probably intentional ({pct}% sure): {reason 1}{ and reason 2}."`
  - Reason phrases, from the largest positive contributions:
    - `repeats_across_slides` → "the same object appears in the same place on {n} other slides"
    - `edges_touched ≥ 2` → "it runs along the edge of the slide like a design element"
    - `span_w/span_h ≥ 0.9` → "it spans the full width or height of the slide"
    - `has_text = 0` → "it contains no text"
    - `z_rank` low → "it sits behind the other objects"
    - `is_placeholder` → "it comes from the slide's layout"
- **The coverage sentence** gains: "A small on-device model sorts findings that look like deliberate design into 'Probably intentional'."

### 5.6 Tests

- **Feature extraction:** unit tests per feature on tiny decks.
- **`judge()`:**
  - deterministic for a fixed model;
  - no-op when the model is missing;
  - never changes non-C1/C2 findings.
- **Demo deck:** no planted mistake moves to "Probably intentional".
- **Yellow Idea template:** at least 4 of its 5 half-donut findings move to "Probably intentional", given the shipped model. If this proves impossible, report it rather than tuning to the test.
- **Training script:** a smoke test (small subset, seconds) that it runs end to end and writes a model and a card.
- **Transcripts and axe:** regenerated and passing with the new section.

## 6. Part B: a presentable prototype

Everything here must leave the screen-reader structure (headings, landmarks, form controls, order) as it is. The transcript and axe tests are the guard.

1. **Visual design.**
   - **Typography and layout:** one small stylesheet (no framework); readable system font at 18 px base; a comfortable reading width; clear spacing.
   - **Colour and focus:** high contrast (WCAG AA); visible focus rings; dark mode via `prefers-color-scheme`.
   - **Look of the findings:** headings by tier; findings shown as cards with a severity label in text, never colour alone.
2. **Demo deck button.**
   - The start page gets a secondary button, "Try the demo presentation". It runs the bundled demo deck without a file dialog, so the presenter doesn't fumble with files.
   - The demo deck is generated at start-up into the run folder if it is missing.
3. **Before/after view (for sighted viewers).**
   - On the result page, a collapsed `<details><summary>Show the changed slides</summary>` holds a side-by-side PNG for each changed slide, original left and corrected right.
   - Each image has alt text such as "Slide 4 before and after: the team photo is narrower and no longer stretched", built from the change log.
   - Shown only when LibreOffice rendering is available.
4. **"How it works" page.**
   - Linked from the footer of every page, titled `How Slide Proof works`.
   - Five short sections: what it checks; what "Probably intentional" means; the model's measured accuracy (read from the model card's numbers); privacy (everything stays on this computer); and what it can't do yet.
5. **Demo script refresh.** Update `docs/testing/` and the main spec §10.2 demo script to include the model ("watch the half-donut move to Probably intentional") and the before/after view.

## 7. Roadmap placement

The main spec §14 gets two new milestones after M2 and before M3:

| Milestone | Effort | Deliverables | Exit criteria |
|---|---|---|---|
| **P Presentable** | 0.5 wk | Part B items 1–5 | Transcript and axe tests unchanged or extended; the demo runs from the button; the before/after view appears when LibreOffice is present |
| **AI Intent model** | 1.5 wks | Part A: features, mistake generator, training script, model and card, `judge()`, report section, tests | §5.4 success criteria met and reported in the model card; NVDA pass of the new section; Yellow Idea case resolved |

M3–M5 keep their order afterwards. M4's "Mark as intentional" later becomes a source of real labels (future work).

## 8. Left to the builder

- Exact feature formulas within §5.2 (tolerances, normalisation), as long as each is unit-tested.
- Perturbation ranges and counts, within §5.3.
- CSS details within §6.1, as long as contrast meets WCAG AA and the axe tests pass.
- Before/after image size and layout.
