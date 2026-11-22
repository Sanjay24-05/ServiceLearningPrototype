# Slide Proof: "Mistake or on purpose?" model, and a presentable prototype

**Design document · 2026-11-22 · Status: draft for approval (revised after builder check; data approach B chosen by the user)**
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

### 5.3 Training data: fully synthetic (approach B, chosen by the user)

**Why synthetic.** The 23 LibreOffice templates contain only 5 C1/C2 findings (all on one template) and 7 objects crossing a slide edge at all. That is too few deliberate examples to train or test on. The user chose to generate **both classes synthetically** for the prototype. The model card must say so plainly (§5.4).

- **Generator.** New script `tools/make_training_decks.py` builds many varied decks with a fixed random seed. It reuses the realistic content of `tools/make_test_decks.py`: text, pictures, charts, tables; 16:9 and 4:3; Title Only, Title and Content, Section Header and Blank layouts.
- **Deliberate patterns (label "deliberate").** Each is a common designer move, randomised in position, size and colour:
  - **Bleeds:**
    - a full-bleed photo;
    - a banner or strip across the top or bottom running past the edge;
    - a half-circle, half-donut or chart graphic cut by one edge;
    - a corner badge or ribbon over a corner.
  - **Repeated decoration:** a logo in the same corner on every slide; a footer bar on every slide.
  - **Composition:** an icon built from stacked shapes; a caption band inside a photo; a picture frame behind a picture; text on a coloured panel.
  - Each pattern is placed so that today's rules would produce a C1 or C2 *raw candidate* (§5.3a).
- **Mistake patterns (label "mistake"):**
  - a text box or picture nudged past one edge by 10–60%;
  - a picture dragged over a text box (10–80% of the text covered);
  - a pasted box partly off the slide;
  - a duplicated object offset onto another;
  - a resized picture spilling over the title.
  - These are applied to the same generated decks, so both classes share slides, layouts and content.
- **Avoiding "learning the generator".** Both classes are randomised over the *same* position, size, kind and colour ranges wherever the pattern allows. The model card lists every pattern and its parameter ranges, so a reader can judge what the model can and can't have learned.
- **Real templates as a sanity check, not training data.** The 23 LibreOffice templates and the realistic corpus are **held out**. They are only used to check that the model doesn't move real mistakes and does move the Yellow Idea half-donut. Results are reported in the model card.

### 5.3a What the model sees

The model is trained on **raw candidates**: every element that crosses a slide edge by more than 2%, and every pair where an upper picture or filled shape covers at least 5% of a lower element's content. That is, C1/C2 *before* the decorative exemptions of main spec §7.2 (deliberate bleed, plain-shape artwork, caption inside a photo).

At run time the exemptions stay exactly as they are (they are tested and safe). The model **only judges findings that survive them**. Training on the broader raw set gives it many more examples of each pattern; the exemptions remain a hard safety floor.

### 5.4 Training and evaluation

- **Script:** `tools/train_intent_model.py`. It builds the dataset, trains both model families, evaluates them, and writes:
  - `slideproof/intent/model.joblib`
  - `slideproof/intent/features.json` (feature order and version)
  - `docs/ml/intent-model-card.md`
- **Evaluation:** grouped cross-validation by generated deck (5 folds), so the score always comes from decks the model never saw. A separate report on the held-out real templates and corpus (§5.3).
  - Metrics: precision, recall and F1 for "deliberate"; the confusion matrix; the calibration curve.
  - **Mistake recall is the key safety number:** the share of real mistakes *not* sent to "Probably intentional".
- **Success criteria.** Mistake recall comes first and always wins when the two conflict.
  1. **Safety:** at least 95% of held-out synthetic mistakes stay in the main lists. Every planted mistake in the demo deck and the realistic corpus stays in the main lists (asserted in tests).
  2. **Usefulness:** at least 50% of held-out synthetic deliberate patterns move to "Probably intentional" at the threshold that meets (1).
  3. **Real-template check (reported, not required):** how many of Yellow Idea's 5 half-donut findings move. If fewer than 4 move, the result is reported honestly in the model card and the milestone can still ship.
- **Model card** (`docs/ml/intent-model-card.md`) covers:
  - purpose;
  - **"All training data is synthetic"**, stated in the first paragraph;
  - every pattern with its ranges;
  - class counts;
  - metrics with confusion matrix and calibration;
  - held-out real-template results;
  - known limits: it may have learned generator quirks; it is untested on real-world decks;
  - how to retrain.
- **Machine-readable metrics:** the script also writes `slideproof/intent/metrics.json`, which the "How it works" page reads.
- **Versioning:** `features.json` records the feature list version and the scikit-learn version used. `scikit-learn` is pinned in `requirements.txt`. If the installed scikit-learn version differs, or the file fails to load, `judge()` returns findings unchanged and the report says "The 'probably intentional' judgement is unavailable in this setup." It never fails silently.

### 5.5 Using the prediction

- **Inference:** `slideproof/intent/__init__.py` exposes `judge(findings, deck) -> list[Finding]`. It adds to each C1/C2 finding's `measurements`:
  - `"intent_p"`: the probability that it's deliberate;
  - `"intent_reasons"`: up to two short reason codes.
  `analyse()` calls it after `run_checks` and before `prioritise`. If the model can't be loaded, it returns the findings unchanged and the report says "The 'probably intentional' judgement is unavailable."
- **Pipeline placement:** `judge()` runs after `run_checks` and before `prioritise()`. `prioritise()` gains a third tier, `intentional`. Grouping (more than 5 of a check on one slide) happens **within** a tier, so a group never mixes intentional and non-intentional findings.
- **Counting:** "Probably intentional" findings don't count as visible problems in the summary or the page title. The summary lists them separately.
- **Fixes and verify:** they stay ordinary findings to the fix re-check (same keys). A fix offered for one is shown **unticked**, and applied only if the user ticks it.
- **Relation to M4 "Mark as intentional":** that is the user's own decision and gets its own section, "Marked intentional", separate from the model's guesses.
- **Threshold:** `intent_p ≥ 0.80`, unless the evaluation picks a stricter value to keep mistake recall at or above 95%. The finding moves to the new **"Probably intentional"** tier, after "Minor polish".
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
- **Yellow Idea template:** a test records how many of its 5 half-donut findings move. It asserts only that the number is reported in `metrics.json` (§5.4, criterion 3), never a tuned target.
- **Version fallback:** a mismatched scikit-learn version in `features.json` produces the "unavailable" note and unchanged findings.
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
   - Shown only when LibreOffice rendering is available. The images come from slide PNGs the analysis and the fix re-check already render (the original run and the final verify attempt), so no extra rendering pass is needed. The side-by-side image is composed with Pillow.
4. **"How it works" page.**
   - Linked from the footer of every page, titled `How Slide Proof works`.
   - Five short sections: what it checks; what "Probably intentional" means; the model's measured accuracy (read from the model card's numbers); privacy (everything stays on this computer); and what it can't do yet.
5. **Demo script refresh.** Update `docs/testing/` and the main spec §10.2 demo script to include the model ("watch the half-donut move to Probably intentional") and the before/after view.

## 7. Roadmap placement and running in parallel with M3

The user wants the AI work to run **alongside** M3 and later milestones. The order:

| Step | Effort | Runs | Deliverables | Exit criteria |
|---|---|---|---|---|
| **P Presentable** | 0.5 wk | **First, alone.** It restyles the shared page templates, so it goes before the parallel tracks to avoid conflicts | Part B items 1, 2 and 4 (style, demo button, "How it works" page without model numbers yet). Item 3, the before/after view, and item 5, the demo script, wait for the AI track | Transcript and axe tests unchanged; the demo runs from the button |
| **AI Intent model** | 1.5 wks | **In parallel with M3**, in its own branch and worktree | Part A complete; Part B items 3 and 5; model numbers on the "How it works" page | §5.4 criteria 1–2 met and reported; criterion 3 reported; NVDA pass of the new section |
| **M3 Render checks** | 1.5 wks | **In parallel with the AI track**, in its own branch and worktree | As main spec §14 | As main spec §14 |
| M4, M5 | as planned | After both merge | As main spec §14 | As main spec §14 |

**Keeping the two parallel tracks apart.**

*Files each track owns:*
- **AI track:** a new package `slideproof/intent/`; new tools `make_training_decks.py` and `train_intent_model.py`; `docs/ml/`. It also makes small edits to `analysis.py` (one call to `judge()`), `prioritise.py` (the third tier), `describe/copy.py` (one sentence), `coverage.py`, and the report template (one new section).
- **M3 track:** `render/`, `checks/content.py`, and new check modules. It also adds entries to `describe/copy.py`, `coverage.py` and the report template.

*Shared contract, frozen before both start:*
- `Finding.measurements` may carry `intent_p` and `intent_reasons`.
- `Report` gains an `intentional` list.
- The AI track adds that field and the section; M3 does not touch them.

*Features independent of M3:*
- The model's features (§5.2) use element geometry and `magnitude`. M3 changes how C2's coverage is measured (rendered text instead of the estimate), so C2 magnitudes shift.
- The training script is re-run after M3 merges; it takes minutes. That re-run is part of the merge checklist, and its new metrics replace the old ones in the model card.

*Merge order:*
- Whichever track finishes first merges first.
- The second rebases, re-runs the whole suite, and (if it's the AI track, or M3 landed after it) retrains.

## 8. Left to the builder

- Exact feature formulas within §5.2 (tolerances, normalisation), as long as each is unit-tested.
- Perturbation ranges and counts, within §5.3.
- CSS details within §6.1, as long as contrast meets WCAG AA and the axe tests pass.
- Before/after image size and layout.
