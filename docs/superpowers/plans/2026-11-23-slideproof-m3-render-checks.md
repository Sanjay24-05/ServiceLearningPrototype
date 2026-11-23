# Slide Proof M3 (Render Checks) + Before/After View — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the slides LibreOffice actually renders to:
- measure where text really sits;
- add the checks that need rendered text: text overflow (C3), small text (C6), low contrast (C7), hidden content (C11);
- stop flagging text boxes whose text isn't actually cut off (audit A6);
- show sighted viewers a before/after image of every fixed slide.

**Architecture:**
- **Linking text:** a span linker matches the rendered text spans to the deck's text elements once per analysis, and stores the result on `RenderResult.linked`.
- **Content boxes:** `content_box()` gains a rendered path that uses those spans; it falls back to M2's estimate when rendering is unavailable.
- **New checks:** each is a pure function in `slideproof/checks/` reading `render.linked` and the slide PNGs, with its wording in `describe/copy.py`.
- **The intent model** keeps using estimate-based features, exactly as it was trained.
- **Before/after view:** the result page composes images from PNGs that the analysis and the fix re-check already render.

**Tech Stack:** existing (PyMuPDF, Pillow, numpy via Pillow arrays, LibreOffice 26.8.3).

**Spec:** main spec `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md`:
- §6 step 4 (span linker);
- §7.1 rows C1, C2, C3, C6, C7, C11 and the content-box rule;
- §7.2 exemptions;
- §8 wording rules;
- §14 M3.

Before/after: `docs/superpowers/specs/2026-11-22-intent-model-and-polish-design.md` §6 item 3. Audit finding A6: `docs/testing/2026-11-22-m1-audit.md` §3.

**Base:** `master` ef062b9. Work on a new branch, `m3-render`.

## Global Constraints

- When LibreOffice is missing or fails, nothing breaks:
  - C3, C6 and C7 are skipped;
  - C1, C2 and C11 fall back to M2's estimate;
  - the report note says which checks were skipped and why. Exact text: `Note: text overflow, contrast and text size checks were skipped because {reason}.`
- Checks never produce prose; wording lives in `describe/`.
- Severity and confidence values are as in the spec:
  - C3 visible, likely;
  - C6 visible below 12 pt, minor below 18 pt on body text, definite;
  - C7 visible, likely when the background is a picture, otherwise definite;
  - C11 visible, likely.
- Thresholds (spec §7.1):
  - **C3:** text extends past its box by more than 0.1 in (91440 EMU).
  - **C6:** under 12 pt is visible; under 18 pt on body/textbox text is minor. Exempt `FOOTER`, `DATE` and `SLIDE_NUMBER` placeholders.
  - **C7:** WCAG ratio below 4.5:1, or below 3:1 for text that is ≥ 18 pt, or ≥ 14 pt and bold.
  - **C11:** at least 95% of the lower element's content box is covered by an opaque element above it.
- **The intent model must not change behaviour:** `judge()` keeps feeding it estimate-based features and magnitudes, so no retrain is needed. Every intent test stays green.
- **No false alarms:**
  - the clean realistic decks (`clean_student_deck`, `long_40_slides`, `linked_and_background`) still produce no findings with real rendering;
  - the 23 LibreOffice templates produce no visible findings from the new checks.
- **Exact copy:**
  - **C3:** headline `{label} has more text than fits in its box`; full `{Label}, {loc}, has more text than fits: it runs past the {edge} of its box by {portion} of the box's {dim}, so it may spill onto other content or be cut off. Confidence: likely.` (edge is "bottom" or "right"; dim is height or width)
  - **C6:** headline `{label} has small text`. Full:
    - visible: `{Label}, {loc}, has text as small as {size} point, which is hard to read when projected. Use at least 18 point for body text. Confidence: definite.`
    - minor: the same, with "may be hard to read" instead of "is hard to read".
  - **C7:** headline `{label} has low contrast`; full `{Label}, {loc}, has text that is too close in colour to its background (contrast {ratio}:1, at least {need}:1 is needed), so it will be hard to read, especially on a projector. Confidence: {conf}.` (ratio to 1 decimal; need is 4.5 or 3)
  - **C11:** headline `{lower} is hidden behind {upper}`; full `{Lower}, {lower_loc}, is almost completely covered by {upper}, so your audience will not see it. Confidence: {conf}.`
  - **Grouped:**
    - C3: `{c} text boxes have more text than fits` / `{c} text boxes on this slide have more text than fits. Confidence: likely.`
    - C6: `{c} text boxes have small text` / `… on this slide have small text. Confidence: definite.`
    - C7: `{c} text boxes have low contrast` / `… on this slide have low contrast. Confidence: {conf}.`
    - C11: `{c} objects are hidden behind others` / `{c} objects on this slide are hidden behind others. Confidence: {conf}.`
  - **Before/after:** `<details><summary>Show the changed slides</summary>`, holding one `<img>` per changed slide. Alt text: `Slide {n} before and after: {change log text without the "Slide {n}: " prefix}` (several changes on one slide joined with "; ").

## Review Focus

1. **Font substitution:** LibreOffice may render a font the laptop doesn't have with different metrics. C3 must not flag text that only overflows by less than 0.1 in, and the template guard must catch systematic false alarms. → Task 6.
2. **Text over photos for C7:** the background median under text on a busy photo is noisy. Confidence must be "likely", and white text on a dark photo must not be flagged. → Task 4 test.
3. **Small decorative text** (footer, slide number, date, tiny captions in templates): C6 must exempt footer, date and slide-number placeholders, and the templates must give no *visible* C6. → Task 3 and Task 6.
4. **Spans the linker can't match** (text in tables and charts, WordArt): they're ignored, never crash, and never get attached to the wrong element. → Task 1 test.
5. **The before/after view when the fix re-check rendered nothing** (no LibreOffice, or a render failure): the section is simply absent, and the result page still works. → Task 7 test.

---

## File Structure

```
slideproof/render/pdf.py            RenderedSpan gains bold: bool (span flags & 16)
slideproof/render/pipeline.py       RenderResult gains linked: dict[str, list[RenderedSpan]] = {}
slideproof/render/link.py   (new)   link_spans(deck, render) -> dict[element_id, list[RenderedSpan]]
slideproof/analysis.py              link once after render; note wording
slideproof/checks/content.py        content_box(el, spans=None) rendered path
slideproof/checks/offslide.py       text elements use rendered content (A6)
slideproof/checks/overlap.py        rendered content boxes; skip pairs C11 reports
slideproof/checks/overflow.py (new) C3
slideproof/checks/textsize.py (new) C6
slideproof/checks/contrast.py (new) C7
slideproof/checks/hidden.py   (new) C11
slideproof/intent/__init__.py       C2 magnitude recomputed with the estimate before features_for
slideproof/describe/copy.py, coverage.py; web/templates/report.html, about.html, result.html; web/app.py
slideproof/web/compare.py     (new) before/after image composition
tests: test_link.py, test_render_content.py, test_overflow.py, test_textsize.py, test_contrast.py, test_hidden.py, test_compare.py (+ updates)
```

---

### Task 1: Span linker and rendered content boxes

**Files:** Create `slideproof/render/link.py`. Modify `render/pdf.py`, `render/pipeline.py`, `analysis.py`, `checks/content.py`. Test: `tests/test_link.py`, `tests/test_render_content.py`.

**Interfaces:**
- `RenderedSpan.bold: bool = False`, from PyMuPDF span flags (`flags & 16`).
- `RenderResult.linked: dict[str, list[RenderedSpan]]`, a field defaulting to an empty dict.
- `link_spans(deck, render) -> dict[str, list[RenderedSpan]]`. Algorithm (spec §6 step 4):
  - For each rendered slide with status ok, and each span with non-whitespace text, find the slide's text elements (title, body, textbox, or shape with text) whose whitespace-normalised text contains the span's normalised text.
  - Among those, prefer the ones whose bbox contains the span's start point (left, vertical middle), with a tolerance of 0.1 in.
  - Break ties by highest z.
  - If nothing matches, leave the span unlinked.
  - Hidden slides whose render entry is `None` get nothing.
- `analyse()` sets `render.linked = link_spans(deck, render)` when the status is ok, before running the checks.
- `content_box(el, spans: list[RenderedSpan] | None = None)`. When `spans` is non-empty and the element is a text kind, return the union of the span bboxes padded by 0.05 in, with confidence `"definite"`. Otherwise use the current behaviour.
- Checks get an element's spans with `(render.linked.get(el.id) if render else None)`.

- [ ] **Step 1: Tests**

```python
def test_bold_flag_read(tmp_path): ...            # synthetic PDF with a bold font span → bold True
def test_links_span_to_containing_text_box(make_deck_and_render): ...  # two boxes "Alpha"/"Beta" → each span linked to its box
def test_repeated_text_prefers_containing_box(...): ...    # same word in two boxes → linked by position
def test_unmatched_span_ignored(...): ...                  # span text not in any element → not linked, no error (Review Focus 4)
def test_rendered_content_box_is_span_union(...): ...      # content_box(el, spans) == union padded, "definite"
@pytest.mark.soffice
def test_demo_deck_agenda_spans_link(demo_deck, tmp_path): # real render: agenda-box has ≥ 4 linked spans
```

  Build `RenderResult` and `RenderedSpan` objects by hand for the non-soffice tests; add a small helper in `tests/conftest.py`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: link rendered text spans to elements; rendered content boxes`.

---

### Task 2: C1 and C2 use rendered text; the intent model stays on estimates

**Files:** Modify `checks/offslide.py`, `checks/overlap.py`, `intent/__init__.py`. Test: `tests/test_render_content.py`, `tests/test_intent_pipeline.py`.

**Interfaces:**
- **C1 (fixes audit A6):** for a text element with linked spans, measure "outside" on the span union instead of the bbox. If no rendered text lies outside the slide, there is no finding, even if the box sticks out. Without spans, behaviour is unchanged.
- **C2:** passes the lower element's (and, for text-over-text, the upper's) linked spans to `content_box`.
- **Intent (Global Constraints):** in `judge()`, the C2 magnitude given to `features_for` is recomputed with the estimate. That is `content_box(lower)` with no spans, giving coverage = intersection ÷ estimated content area, exactly as `raw_candidates` does in training. C1 magnitude: use the bbox-based outside fraction, as in training.

- [ ] **Step 1: Tests**

```python
def test_c1_box_sticks_out_but_text_inside_not_flagged(...):  # wide box past the edge, short text well inside; rendered spans inside → no C1
def test_c1_text_cut_still_flagged(...):                      # spans past the edge → C1 visible
@pytest.mark.soffice
def test_demo_slide2_still_flagged_with_render(demo_deck, tmp_path)
def test_judge_uses_estimate_magnitude(...):                  # a C2 finding whose rendered coverage differs from estimate → features_for gets the estimate value
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass, including every intent test.
- [ ] **Step 5: Commit** `feat: off-slide and overlap use rendered text; intent model keeps estimate features`.

---

### Task 3: C3 text overflow and C6 small text

**Files:** Create `checks/overflow.py`, `checks/textsize.py`. Modify `checks/__init__.py`, `describe/copy.py`. Test: `tests/test_overflow.py`, `tests/test_textsize.py`.

**Interfaces:**
- **`check_overflow(deck, render)`:**
  - Runs only when `render` is ok.
  - For each text element with linked spans: overflow below = `spans_union.bottom − frame.bottom`; overflow right = `spans_union.right − frame.right`.
  - Flag when either is more than 91440 EMU. The edge is the larger of the two.
  - `measurements = {"edge": "bottom"|"right", "amount": fraction of frame height or width}`. Severity visible, confidence likely, no fix (F7 is M4).
- **`check_textsize(deck, render)`:**
  - Runs only when `render` is ok.
  - For each text element with linked spans, excluding placeholder types FOOTER, DATE and SLIDE_NUMBER: smallest span size < 12 → visible; < 18 on kind body or textbox → minor.
  - `measurements = {"size": round(min_size)}`. Confidence definite, no fix.
- Both are registered in `CHECKS`, and both have copy plus grouped copy per Global Constraints.

- [ ] **Step 1: Tests** (synthetic `RenderResult` plus one soffice test each)

```python
def test_overflow_flagged_when_text_runs_past_bottom(...)
def test_overflow_ignored_under_tenth_inch(...)            # Review Focus 1
def test_overflow_skipped_without_render(demo_deck)        # render None → []
@pytest.mark.soffice
def test_demo_timeline_overflow(demo_deck, tmp_path)       # slide 6 timeline-list → C3 visible
def test_small_text_visible_and_minor_bands(...)
def test_footer_placeholders_exempt(...)                   # Review Focus 3
def test_copy_c3_c6(...)                                   # exact strings
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: text overflow (C3) and small text (C6) from rendered slides`.

---

### Task 4: C7 low contrast

**Files:** Create `checks/contrast.py`. Modify `checks/__init__.py`, `describe/copy.py`. Test: `tests/test_contrast.py`.

**Interfaces:**
- **`check_contrast(deck, render)`.** Runs only when `render` is ok. For each text element with linked spans, for each span:
  1. Crop the slide PNG to the span bbox (EMU → pixels using the PNG size ÷ slide size).
  2. Background = the median RGB of pixels whose Euclidean RGB distance from the span colour is more than 60. If fewer than 20 such pixels exist, skip the span.
  3. Compute the WCAG relative-luminance contrast ratio between the span colour and the background.
  4. The required ratio is 3.0 if size ≥ 18, or size ≥ 14 and bold; otherwise 4.5.
- **Result:** one finding per element, for its worst span below the required ratio.
  - `measurements = {"ratio": round(r, 1), "need": need}`.
  - Confidence is "likely" if a picture element's bbox lies under the span's bbox with a lower z; otherwise "definite".
  - Severity visible, no fix.
- Registered in `CHECKS`, with copy plus grouped copy.

- [ ] **Step 1: Tests**

```python
def test_contrast_ratio_math(): ...                        # helper: black on white 21.0, #777 on #fff ≈ 4.48
def test_grey_on_white_flagged(...)                        # synthetic PNG + span colour BBBBBB on white → ratio < 4.5
def test_white_on_dark_photo_not_flagged(...)              # Review Focus 2
def test_large_bold_needs_only_3(...)
@pytest.mark.soffice
def test_demo_slide7_two_contrast_findings(demo_deck, tmp_path)   # grey-text (definite) and photo-caption (likely)
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: low contrast (C7) from rendered slides`.

---

### Task 5: C11 hidden content

**Files:** Create `checks/hidden.py`. Modify `checks/overlap.py`, `checks/__init__.py`, `describe/copy.py`. Test: `tests/test_hidden.py`.

**Interfaces:**
- **`check_hidden(deck, render)`:**
  - For each (lower, upper) pair: the upper element is a picture or filled; the lower has a content box (rendered spans if available, otherwise the estimate).
  - Flag when coverage of the lower content box is ≥ 0.95.
  - **Exemptions (§7.2):**
    - the lower element is a background picture;
    - the two elements share a group;
    - a text label inside its lower element;
    - a plain text-less shape as the lower element.
  - `element_ids = (upper.id, lower.id)`, severity visible, confidence likely, `measurements = {"coverage": cov}`, no fix.
  - Runs with or without rendering.
- **C2 then skips** any pair C11 reports (coverage ≥ 0.95), so a pair is never reported twice. Shared helpers come from `overlap.py`; don't duplicate them.
- Registered in `CHECKS`, with copy plus grouped copy. The copy uses `Ctx.other()` for the lower element.

- [ ] **Step 1: Tests**

```python
def test_text_fully_under_picture_is_hidden(tiny_deck/...)   # → one C11, no C2
def test_partial_cover_stays_c2(...)                          # 40% → C2 only
def test_background_lower_exempt(demo_deck)                   # slide 8 → no C11
def test_copy_c11(...)
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: hidden content (C11); overlap no longer double-reports it`.

---

### Task 6: Coverage, note, About page, answer key, no-false-alarm guards

**Files:** Modify `describe/coverage.py`, `analysis.py` (note wording), `web/templates/about.html` ("What it cannot do yet"), `tests/test_corpus.py`, `tests/test_checks.py` or `test_corpus.py` (ground truth), and the transcripts.

**Interfaces:**
- **`CHECKS_RUN` adds** "text that overflows its box", "small text", "low-contrast text" and "content hidden behind other objects".
- **`NOT_CHECKED_YET` becomes** ("text inside charts and diagrams",). The checked sentence reads naturally with 11 items, e.g. "This version checks eleven things: …". Extend the number words, so it never says "11 things".
- **The note text** follows Global Constraints.
- **About page:** the "What it cannot do yet" list is derived as before; drop the bullet about the overlap estimate (now rendered).
- **Answer key:** with LibreOffice, `IMPLEMENTED` gains C3, C6, C7 and C11. The demo deck must match its `expected_findings.json` exactly (soffice-marked). Without LibreOffice, the existing non-render test keeps its current set.
- **Corpus (soffice):** the clean decks give no findings with real rendering.
- **Templates (soffice):** the existing guard additionally allows minor C6 (small template text). Visible C3, C6, C7 or C11 fail the test. If a template produces a visible one, investigate the check (Review Focus 1 and 3) before changing the guard, and record the reason.
- **Transcripts:** regenerate (they run without LibreOffice, so only the coverage sentence and note change). Read the diffs.

- [ ] **Step 1: Tests and updates** as above.
- [ ] **Step 2: Run** `python -m pytest -q`. Expected: all pass, with soffice tests running (LibreOffice is installed).
- [ ] **Step 3: Commit** `feat: coverage and About reflect M3 checks; answer key and no-false-alarm guards with rendering`.

---

### Task 7: Before/after view on the result page

**Files:** Create `slideproof/web/compare.py`. Modify `web/app.py`, `web/templates/result.html`. Test: `tests/test_compare.py`, `tests/test_web.py`.

**Interfaces:**
- `compose(before_png: Path, after_png: Path, out_png: Path) -> None`: a side-by-side image with a 24 px gap on a white background, both halves scaled to the same height.
- **The result route:**
  - **Which slides:** the changed slide numbers come from `export.applied` (each fix's finding `slide_index`).
  - **Before image:** `analysis.render.slides[i-1].png_path`.
  - **After image:** `export.final.render.slides[i-1].png_path`. When a fix deleted an element the slide count is unchanged, so the indices match.
  - Composed images are written under `run.dir/output/compare-slide-{n}.png` and served by `GET /runs/{id}/compare/{n}.png` (404 if absent).
  - The section is included only when both renders have PNGs for every changed slide (Review Focus 5).
  - Alt text comes from the change-log lines, per Global Constraints.

- [ ] **Step 1: Tests**

```python
def test_compose_side_by_side(tmp_path)                  # two small PNGs → output width = w1 + 24 + w2, height = max
def test_result_has_no_compare_without_render(client, demo_deck)   # SOFFICE_PATH missing → no "Show the changed slides"
@pytest.mark.soffice
def test_result_shows_compare_with_render(tmp_path, demo_deck)     # real run → section present, img alt "Slide 4 before and after: …", image served 200
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`, plus axe on a result page with the section (a soffice-marked a11y test).
- [ ] **Step 5: Commit** `feat: before/after view of changed slides`.

**After the plan (controller):**
- a realistic-deck audit with real rendering;
- an NVDA pass on the demo deck (now with C3 and C7 findings);
- main spec §14 M3 row marked ✅ and an audit doc;
- push.
