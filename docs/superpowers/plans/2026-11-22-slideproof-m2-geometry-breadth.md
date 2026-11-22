# Slide Proof M2 (Geometry Breadth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the working M1 loop with five more checks a sighted audience would notice (overlap C2, low-resolution pictures C5, title position C8, mixed fonts C9, empty or stray objects C10), two more safe fixes (F3 match title position, F4 remove empty text box), and a spoken "Layout of slide N" map for each finding.

**Architecture:** Each check stays a pure function in `slideproof/checks/` that emits structured `Finding`s. Its wording goes into `slideproof/describe/`, and its safe fix (if any) is applied by `slideproof/fixes/`.
- **Overlap (C2)** uses a new content-box module. In M2 it estimates the area text actually fills from the file (spec §7.1, content-box rule, "without rendering"); M3 will switch it to rendered spans.
- **The report page** gains a per-finding slide map. The "what this version checks" sentence is updated.

**Tech Stack:** Python 3.12 venv (`.venv`), python-pptx 1.0.2, PyMuPDF, Pillow, FastAPI/Jinja2, pytest, Playwright (Edge via `channel="msedge"`), LibreOffice 26.8 (installed).

**Spec:** `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md` (§7.1, §7.2, §7.3, §8.1, §8.2, §9.1, §14 M2). Audit context: `docs/testing/2026-11-22-m1-audit.md`.

**Base branch:** `m1-fixes` (40fab35). Work on a new branch `m2-geometry` cut from it.

## Global Constraints

- Checks never produce prose; presenters never compute geometry (spec §5.3).
- Element ids are `f"s{slide_id}-sh{shape_id}"`; `Finding.key = (check_id, slide_id, element_ids)`.
- Severity `"visible" | "minor"`; confidence `"definite" | "likely"`. Findings based on estimated text extent are `"likely"` (spec §7.1).
- Units: 914,400 EMU = 1 inch; 1 pt = 12,700 EMU.
- The original upload is never modified; fixes apply to a copy in `FIX_ORDER = ["F4", "F5", "F3", "F2", "F1", "F7", "F6"]`, and verification re-checks the copy and rolls back any fix that didn't work (existing `verify.py`).
- Safe fixes are pre-checked; confirm fixes are unchecked; each label says which kind (spec §8.2).
- Element names never expose internal shape names. Location uses the 3×3 grid; amounts are relative to the slide, not inches; fixed terms "covers", "sticks out", "stretched" (spec §8.1).
- Coverage words: < 15% "a small part of"; 15–30% "about a quarter of"; 30–40% "about a third of"; 40–60% "about half of"; 60–90% "most of"; > 90% "all of" (existing `coverage_phrase`).
- Semantic HTML only; heading navigation is the main way around the report; no aria-live spam (spec §8.2).
- Every new check must produce **no finding** on the clean decks from `tools/make_test_decks.py` (`clean_student_deck`, `long_40_slides`) and on the four LibreOffice template decks. A false alarm on a clean deck is a failed task.

## Review Focus

1. **Template decks full of decorative freeform shapes, lines and pictures** (LibreOffice templates such as Freshes and Grey Elegant): overlap and stray checks must not fire on decorative artwork behind or around text. → Task 9 asserts zero findings on all four template decks.
2. **Placeholders that are empty in edit view** (an unused "Click to add text" body placeholder): they don't show in a slideshow, so C10 must treat an empty *placeholder* like an empty text box (minor, removable), never visible. → test in Task 4.
3. **A deck where every slide's title is in a different place** (no dominant position): C8 must stay silent rather than flag every slide. → test in Task 5.
4. **Fonts set only through the theme** (runs with no explicit font, the common case): C9 must not call the theme font "stray", and must not flag a deck that mixes "theme font" with one explicit font used everywhere. → test in Task 5.
5. **Text over a picture used as a deliberate label** (a caption box fully inside a photo, like the demo's slide 7 caption): a caption sitting on top of a picture is not an overlap problem. Only an upper element covering a lower element's content is. → test in Task 3.

---

## File Structure

```
slideproof/
  model.py                 + Element.outlined, Element.paragraphs, Element.anchor, Element.insets
  loader.py                + read those fields
  checks/
    __init__.py            register new checks
    content.py   (new)     content_box(): estimated text extent / bbox
    overlap.py   (new)     C2
    resolution.py(new)     C5
    stray.py     (new)     C10
    titles.py    (new)     C8
    fonts.py     (new)     C9
    offslide.py            hand empty text elements to C10
  describe/
    __init__.py            dispatch table per check + generic fallback; F3/F4 labels and change logs
    copy.py      (new)     per-check headline/full wording (keeps __init__ small)
    layout_map.py(new)     slide_map()
    coverage.py            update CHECKS_RUN / NOT_CHECKED_YET
  fixes/
    __init__.py            accept F3, F4
    writer.py              + delete_shape()
  web/app.py, templates/report.html   per-finding "Layout of slide N"
tools/make_demo_deck.py    demo adjustments (Task 2)
tests/                     new test files named per task
```

---

### Task 1: Model fields for content boxes and outlines

**Files:**
- Modify: `slideproof/model.py`, `slideproof/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Produces (new `Element` fields, all with defaults so existing constructors keep working):
  - `outlined: bool = False`: the shape has a visible line (`shape.line.fill.type` is solid/gradient/pattern and width > 0; any exception → False).
  - `paragraphs: list[tuple[int, float | None]]`: per paragraph, (character count, font size in pt of its first run with a size, else None). Empty list when there's no text frame.
  - `anchor: Literal["top", "middle", "bottom"] = "top"`, from `text_frame.vertical_anchor` (None → "top").
  - `insets: tuple[int, int, int, int]`: `(margin_left, margin_top, margin_right, margin_bottom)` in EMU. The python-pptx defaults are 91440, 45720, 91440, 45720.
- This also covers a deferred T4 minor: the group transform test is strengthened.

- [ ] **Step 1: Write the failing tests**

```python
def test_text_fields_loaded(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "t", "x": 1, "y": 1, "w": 4, "h": 2, "text": "Hello world"}]))
    e = d.slides[0].elements[0]
    assert e.paragraphs and e.paragraphs[0][0] == len("Hello world")
    assert e.anchor == "top" and e.insets == (91440, 45720, 91440, 45720)
    assert e.outlined is False

def test_outlined_shape(tmp_path): ...   # autoshape with line.color set and line.width = Pt(2) → outlined True

def test_group_with_child_offset_and_scale(tmp_path): ...
    # group off=(2in,1in) ext=(4in,2in), chOff=(1in,1in) chExt=(2in,1in); child at (1in,1in) size (1in,0.5in)
    # → child frame == Rect(inches(2), inches(1), inches(2), inches(1))

def test_nested_group_composes(tmp_path): ...   # inner group inside outer group; assert absolute child position
```

- [ ] **Step 2: Run** `python -m pytest tests/test_loader.py -v`. Expected: the 4 new tests FAIL.
- [ ] **Step 3: Implement** the fields in `model.py` and read them in `loader.py` (guard every python-pptx access the same way `_is_filled` does).
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: load outline, paragraph, anchor and inset data`.

---

### Task 2: Content boxes and demo deck adjustments

**Files:**
- Create: `slideproof/checks/content.py`
- Modify: `tools/make_demo_deck.py`
- Test: `tests/test_content.py`, `tests/test_demo_deck.py`

**Interfaces:**
- Consumes: Task 1 fields.
- Produces: `content_box(el: Element) -> tuple[Rect, str] | None`, returning `(rect, confidence)`:
  - **picture, table, chart, filled shape:** `(el.bbox, "definite")`.
  - **text element** (title, body, textbox, or shape with text): the estimated extent, with confidence `"likely"`:
    - `usable_w = frame.w − insets_l − insets_r`
    - For each paragraph `(chars, size)`, with `size = size or 18.0`:
      `lines = max(1, ceil(chars × 0.5 × size × 12700 / usable_w))`, and the paragraph's height is `lines × size × 1.2 × 12700`.
    - `text_h` = sum of the paragraph heights, capped at the frame's inner height.
    - `text_w = min(usable_w, max(chars × 0.5 × size × 12700))` over all paragraphs.
    - The rect starts at the inner left. Vertically it sits at the inner top, middle or bottom according to `anchor`. It is padded by 0.05 in (45720 EMU) on each side, then clipped to the frame.
  - **empty text, or an unfilled shape with no text:** `None`.
  - Rotated elements use `bbox`, with confidence `"likely"`.
- Demo deck changes (the ground-truth rows stay exactly as they are):
  - **Slide 3:** `results-list` gets 5 long lines (each 35–45 characters, 24 pt). `results-chart` moves to x 4.5, y 2.6, w 5, h 3, so the estimated *and* rendered text of the lower lines runs under the chart. Render the slide (LibreOffice → PNG in the scratchpad) and confirm by eye that the chart covers part of the visible text.
  - **Slide 4:** `team-photo` becomes 1600 × 1200 px (same 4:3 ratio, same face image scaled up). At 8 in wide that is 200 DPI, so C5 does not fire on it. This was parked from M1.

- [ ] **Step 1: Write the failing tests**

```python
def test_picture_content_is_bbox(tiny_deck): ...          # picture → (bbox, "definite")
def test_short_text_content_is_small(tiny_deck):
    # 6x3 in textbox, text "Hi" at 24 pt → content height < 0.6 in, width < 1 in, confidence "likely"
def test_long_text_wraps(tiny_deck):
    # 3 in wide box, 120 chars at 20 pt → lines >= 4; content height >= 4*20*1.2 pt
def test_middle_anchor_centres(tmp_path): ...             # anchor middle → content centre y ≈ frame centre y (±1%)
def test_empty_text_has_no_content(tiny_deck): ...        # → None
def test_team_photo_resolution(demo_deck):                # in test_demo_deck.py
    # team-photo image px == (1600, 1200); displayed ratio still 1.6× its natural shape
```

- [ ] **Step 2: Run** `python -m pytest tests/test_content.py tests/test_demo_deck.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `content.py` and the demo changes. Check that `tests/output/expected_findings.json` is unchanged.
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass (the existing C1/C4 ground-truth test included).
- [ ] **Step 5: Commit** `feat: estimated content boxes; demo slide 3 overlap and sharper team photo`.

---

### Task 3: C2 overlap (with exemptions) and its wording

**Files:**
- Create: `slideproof/checks/overlap.py`, `slideproof/describe/copy.py`
- Modify: `slideproof/checks/__init__.py`, `slideproof/describe/__init__.py`
- Test: `tests/test_overlap.py`, `tests/test_describe.py`

**Interfaces:**
- Consumes: `content_box` (Task 2).
- Produces: `check_overlap(deck, render) -> list[Finding]`, registered in `CHECKS` after `check_distortion`.
  - **Pairs:** for each pair (lower, upper) on a slide, with `upper.z > lower.z`.
  - **Upper element:** a picture, or an element with `filled=True`; otherwise skipped.
  - **Lower content:** `lc = content_box(lower)`; skip if None.
  - **Coverage:** `cov = area(upper.bbox ∩ lc.rect) / area(lc.rect)`.
  - **Flag when** `cov ≥ 0.05`.
  - **Also flag** two text elements whose content boxes intersect (either order), with `cov` measured against the smaller content box.
  - **Exemptions (spec §7.2):**
    - the lower element is a background picture (≥ 90% of the slide, lowest z);
    - the upper element is a text label whose bbox lies fully inside the lower element's bbox (captions on photos, text on shapes);
    - both elements share a `group_id`;
    - an element is never compared with itself.
  - **Finding:** `element_ids = (upper.id, lower.id)`, `severity="visible"`, `confidence` = the lower content box's confidence, `magnitude=cov`, `measurements={"coverage": cov, "lower_is_text": bool}`, `fix=None` (F6 comes in M4).
- `describe/copy.py` holds the wording for every check as small functions: `headline_<check>(...)` and `full_<check>(...)`. Move the existing C1/C4 wording there unchanged. `describe()` dispatches through a dict keyed by check id. **An unknown check id falls back** to headline `"a layout problem was found"` and full `"A layout problem was found on this slide. Confidence: {confidence}."`; it no longer raises (deferred T6 minor).
- **C2 copy:**
  - headline: `"{upper} covers {coverage_phrase(cov)} {lower}"`
  - full, lower is text: `"{Upper}, {loc_upper}, sits on top of {coverage_phrase(cov)} {lower}, {loc_lower}. Your audience may not be able to read the covered text. Confidence: {confidence}."`
  - full, lower not text: same, ending `"Your audience may not be able to see the covered part. Confidence: {confidence}."`
  - grouped: `"{count} objects overlap each other"` / `"{count} objects on this slide overlap each other. Confidence: {confidence}."`

- [ ] **Step 1: Write the failing tests**

```python
def test_picture_over_text_flagged(tiny_deck): ...        # long text box + picture covering its lower half → 1 C2, coverage >= 0.3, likely
def test_picture_beside_short_text_not_flagged(tiny_deck): ...  # picture over the empty right part of a big box with short text → none
def test_caption_inside_photo_not_flagged(tiny_deck): ... # text box fully inside a picture, above it → none (Review Focus 5)
def test_background_below_text_not_flagged(demo_deck): ...# slide 8 → no C2
def test_grouped_members_not_flagged(tmp_path): ...
def test_demo_slide3_c2(demo_deck):
    # exactly one C2 on slide 3 with shapes {"results-chart", "results-list"}; describe().short starts
    # 'Slide 3: picture "Bar chart of harvest results" covers ' and contains 'text box "'
def test_unknown_check_has_fallback_copy(demo_deck): ...  # Finding with check_id "C99" → headline "a layout problem was found"
```

- [ ] **Step 2: Run** `python -m pytest tests/test_overlap.py tests/test_describe.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `overlap.py`, `copy.py` and the dispatch.
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: overlap check C2 with exemptions; describer dispatch table`.

---

### Task 4: C5 low resolution, C10 empty or stray objects, and F4 remove

**Files:**
- Create: `slideproof/checks/resolution.py`, `slideproof/checks/stray.py`
- Modify: `slideproof/checks/offslide.py`, `slideproof/checks/__init__.py`, `slideproof/describe/copy.py`, `slideproof/describe/__init__.py`, `slideproof/fixes/__init__.py`, `slideproof/fixes/writer.py`
- Test: `tests/test_resolution.py`, `tests/test_stray.py`, `tests/test_fixes.py`

**Interfaces:**
- **`check_resolution(deck, render) -> list[Finding]`:**
  - Pictures with `image` only.
  - `dpi = min(px_w × (1 − cl − cr) / (frame.w / 914400), px_h × (1 − ct − cb) / (frame.h / 914400))`.
  - `< 72` → visible; `< 110` → minor; `confidence="definite"`; `magnitude = 1 − dpi/110`; `measurements={"dpi": round(dpi)}`; `fix=None`.
  - Background pictures are included (a blurry background is visible).
- **`check_stray(deck, render) -> list[Finding]`:**
  - **(a) empty text element** (kind title/body/textbox, `text` empty or whitespace): severity `visible` if `filled or outlined`, else `minor`; `measurements={"kind": "empty"}`. Fix `F4`, safe, only when not filled, not outlined, `fixable`, and no `group_id`.
  - **(b) near-zero size:** both `frame.w` and `frame.h` < 0.05 in (45720 EMU). Lines with one zero dimension are not "near-zero". Minor; `{"kind": "tiny"}`; no fix.
  - **(c) entirely off-slide:** bbox doesn't intersect the slide. Minor; `{"kind": "offslide"}`; no fix.
  - An element gets at most one C10 finding, checked in the order (a), (b), (c).
- **`check_offslide` (C1) now skips empty text elements entirely.** They belong to C10. This replaces the M1 rule "empty unfilled text that sticks out is minor". Update spec §7.2's last bullet to say so, and update the C1 tests that expected minor C1 for empty boxes so they expect the C10 finding instead.
- **F4:** `delete_shape(prs, slide_id: int, shape_id: int) -> None` in `writer.py` removes the shape's XML element (raises `KeyError` if it isn't found). `apply_fixes` accepts `F4`.
- **Copy** (`{label}` for empty text elements is already "empty text box"):
  - **C5:** headline `"{label} is low resolution"`; full `"{Label}, {loc}, has about {dpi} pixels per inch at its current size, so it will look blurry or blocky when projected. Use a larger or sharper version of the image. Confidence: definite."`
  - **C10 empty:** headline `"{label} is empty"`. Full, minor: `"{Label}, {loc}, has no text. It is invisible when presenting but gets in the way when you edit the slide. Confidence: definite."` Full, visible: `"{Label}, {loc}, has no text but has a fill or outline, so it shows as a blank shape. Confidence: definite."`
  - **C10 tiny:** headline `"{label} is too small to see"`; full `"{Label}, {loc}, is almost zero in size, so it cannot be seen. It is probably left over from editing. Confidence: definite."`
  - **C10 off-slide:** headline `"{label} is completely off the slide"`; full `"{Label} is entirely outside the slide, so it will not be shown when presenting. Confidence: definite."`
  - **F4:** fix_label `"Remove the empty text box. Safe fix."`; change_log `"Slide {n}: an empty text box was removed."`
  - **Grouped:** C5 `"{count} pictures are low resolution"`; C10 `"{count} empty or stray objects"`, each with a matching full sentence ending in `"Confidence: definite."`

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_logo_low_resolution(demo_deck):   # exactly one C5: logo, visible, dpi 50; no C5 for team-photo
def test_minor_band(tiny_deck): ...             # 800 px across 8.5 in (≈94 DPI) → minor
def test_stray_box_c10_with_f4(demo_deck):      # slide 8 stray-box → C10 minor, fix F4 safe; no C1 for it
def test_empty_placeholder_is_minor(tmp_path): ...  # unused body placeholder (Review Focus 2) → C10 minor + F4
def test_filled_empty_box_visible_no_fix(tmp_path): ...
def test_offslide_element(tiny_deck): ...       # textbox at x 20 in → C10 offslide minor, no C1
def test_line_not_tiny(tmp_path): ...           # straight connector 3 in long, 0 height → no C10
def test_f4_deletes_shape(demo_deck, tmp_path): # apply F4 → reloaded slide 8 has no "stray-box"; original unchanged
```

- [ ] **Step 2: Run** the three test files. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: low-resolution (C5) and empty/stray (C10) checks; F4 remove empty text box`.

---

### Task 5: C8 title position with F3, and C9 mixed fonts

**Files:**
- Create: `slideproof/checks/titles.py`, `slideproof/checks/fonts.py`
- Modify: `slideproof/checks/__init__.py`, `slideproof/describe/copy.py`, `slideproof/describe/__init__.py`, `slideproof/fixes/__init__.py`
- Test: `tests/test_titles.py`, `tests/test_fonts.py`

**Interfaces:**
- **`check_titles(deck, render) -> list[Finding]`:**
  - **Candidates:** title elements with `placeholder_type == "TITLE"` (title-slide `CENTER_TITLE` is excluded), not hidden slides, not rotated.
  - **Needs ≥ 3 candidates.** Cluster by (left, top) with a tolerance of 0.1 in (91440 EMU). The dominant cluster must hold **more than half** of the candidates; otherwise return nothing (Review Focus 3).
  - **Dominant geometry:** the full frame of the first member of the dominant cluster.
  - **Flag** any title whose `|left − dom.left|` or `|top − dom.top|` > 0.15 in (137160 EMU).
  - **Finding:** severity visible, confidence definite, `magnitude = min(1, max(|dx|, |dy|) / slide_h)`, `measurements={"dx": dx, "dy": dy, "others": len(candidates) - 1}`.
  - **Fix F3**, safe, `params={"frame": dom.as_list()}`, applied through the existing `set_frame` (`apply_fixes` accepts F3).
- **`check_fonts(deck, render) -> list[Finding]`:**
  - Counts characters per **explicit** font family from `Element.runs` (run font None = theme font, which is counted as `"(theme)"` but never flagged).
  - Ignore symbol fonts (`Symbol`, `Wingdings*`, `Webdings`) and monospace code fonts (`Consolas`, `Courier New`, `Cascadia*`).
  - **Stray family:** under 10% of all counted characters **and** used on ≤ 2 slides **and** at least one other family (including "(theme)") has ≥ 50%.
  - **One finding per element** that uses a stray family: severity minor, confidence definite, `measurements={"font": name, "main_font": the most-used family, rendered as "the theme font" when it is "(theme)"}`, `fix=None` (F5 comes in M4).
- **Copy:**
  - **C8:** direction = whichever of dx or dy is larger: dy > 0 "lower", dy < 0 "higher", dx > 0 "further right", dx < 0 "further left". Amount by `|delta| / slide size` on that axis: < 3% "slightly", < 10% "noticeably", else "much".
    - headline `"the title sits {amount} {direction} than on the other {others} slides"`
    - full `"The title on this slide sits {amount} {direction} than on the other {others} slides, so it will seem to jump when the slides change. Confidence: definite."`
    - F3 fix_label `"Move the title to the same position as on the other slides. Safe fix."`; change_log `"Slide {n}: the title moved to the same position as on the other slides."`
  - **C9:** headline `"{label} uses {font}, a font used almost nowhere else"`; full `"{Label}, {loc}, is set in {font}. The rest of the presentation mainly uses {main_font}, so this text will look out of place. Confidence: definite."`

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_slide5_title(demo_deck):
    # exactly one C8 (slide 5, "slide-title"), visible, fix F3 safe;
    # describe().headline == "the title sits noticeably lower than on the other 6 slides"
def test_no_dominant_position_silent(tiny_deck_factory): ... # 4 slides, titles all in different places → no C8
def test_title_slide_excluded(demo_deck): ...                # slide 1 never gets C8
def test_f3_resolves(demo_deck, tmp_path): ...               # export_and_verify with F3 → resolved, 0 new
def test_demo_budget_note_font(demo_deck):                   # exactly one C9: budget-note, minor, font "Georgia"
def test_theme_font_never_stray(tmp_path): ...               # Review Focus 4
def test_symbol_font_ignored(tmp_path): ...
```

Compute the expected "other N slides" count from the demo deck and put the real number in the test.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: title position (C8) with F3, mixed fonts (C9)`.

---

### Task 6: Slide layout map, coverage sentence and report page

**Files:**
- Create: `slideproof/describe/layout_map.py`
- Modify: `slideproof/describe/coverage.py`, `slideproof/web/app.py`, `slideproof/web/templates/report.html`, `tests/transcripts/report.txt` (regenerated)
- Test: `tests/test_layout_map.py`, `tests/test_web.py`

**Interfaces:**
- **`slide_map(slide: SlideModel, deck: DeckModel) -> list[str]`:**
  - One line per element, ordered top-to-bottom, then left-to-right, by bbox centre. Rows are grouped within 10% of the slide height.
  - Format: `"{Label}, {grid_location(bbox)}, {size}"`, where size by bbox area ÷ slide area is < 5% "small", < 25% "medium", < 60% "large", else "covers most of the slide".
  - Elements entirely off the slide get `", off the slide"` instead of a location.
  - Skipped shapes are summarised in one final line: `"{n} other object(s) that could not be read"`.
- **Coverage sentence:**
  - `CHECKS_RUN` = ("objects that stick out past the slide edge", "stretched pictures", "overlapping objects", "low-resolution pictures", "titles out of line with the rest", "stray fonts", "empty or stray objects")
  - `NOT_CHECKED_YET` = ("text overflow", "contrast", "text size")
  - Keep the existing sentence builder ("This version checks seven things: …").
- **Report page:** inside each finding's `<section>`, after the fix fieldset or the no-fix paragraph, add `<details><summary>Layout of slide {n}</summary><ol>{one <li> per slide_map line}</ol></details>`. Grouped findings get it too. The app computes the lines (presenters never compute geometry); the template only loops over them.

- [ ] **Step 1: Write the failing tests**

```python
def test_slide_map_demo_slide4(demo_deck):
    lines = slide_map(<slide 4>, deck)
    assert lines[0].startswith("The title, in the top")
    assert any(l.startswith('Picture "Team photo", in the centre') for l in lines)
    assert any(l.startswith('Picture "Garden logo", in the bottom right, small') for l in lines)
def test_slide_map_offslide_and_skipped(tiny_deck): ...
def test_report_has_layout_details(client, demo_deck): ...   # report HTML contains "<summary>Layout of slide 4</summary>" and an <ol>
def test_coverage_sentence_lists_seven(): ...                # checked_sentence() starts "This version checks seven things: "
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, then regenerate the transcripts with `UPDATE_TRANSCRIPTS=1 python -m pytest tests/test_transcript.py`. Read the diff: it should only add the new findings, the layout-map summaries and the new coverage sentence.
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: per-finding slide layout map; coverage sentence for M2 checks`.

---

### Task 7: Ground truth, realistic-deck regression and docs

**Files:**
- Modify: `tests/test_checks.py` (ground-truth test), `docs/testing/nvda-walkthrough.md` (expected counts), `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md` (§14: mark M2 done, note the C10/C1 hand-off)
- Create: `tests/test_corpus.py`

**Interfaces:**
- Consumes: everything above; `tools/make_test_decks.py`; the LibreOffice templates at `C:\Program Files\LibreOffice\share\template\common\presnt\{Blue_Curve,Focus,Freshes,Grey_Elegant}.otp`.

- [ ] **Step 1: Write the tests**

```python
IMPLEMENTED = {"C1", "C2", "C4", "C5", "C8", "C9", "C10"}
def test_demo_deck_matches_ground_truth(demo_deck):
    tp, fp, missed = match([f for f in run_checks(deck, None) if f.check_id in IMPLEMENTED], deck,
                           load_expected(demo_deck[1], IMPLEMENTED))
    assert fp == [] and missed == []

def test_clean_corpus_has_no_findings(corpus_decks):        # fixture builds decks with tools/make_test_decks.py into tmp
    for name in ("clean_student_deck.pptx", "long_40_slides.pptx", "linked_and_background.pptx"):
        assert run_checks(load_deck(corpus_decks / name), None) == []

def test_constructs_and_lecture_expected(corpus_decks): ...  # expected.json rows still found; no other findings

@pytest.mark.soffice
def test_template_decks_have_no_findings(tmp_path):         # converts the 4 .otp templates to .pptx with soffice, then
    ...                                                      # asserts run_checks(...) == [] for each (Review Focus 1)
```

- [ ] **Step 2: Run** `python -m pytest -q`. Fix any false alarm in the check that caused it (not in the test). If a template decoration really is a problem a sighted viewer would notice, stop and report it instead of changing the expectation.
- [ ] **Step 3: Update docs:** the NVDA walkthrough's expected counts for the demo deck (visible and minor) and spec §14.
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass, 0 skipped.
- [ ] **Step 5: Commit** `test: M2 ground truth and realistic-deck regression; docs`.

**After the plan (controller, not an implementer):** re-run `tools/nvda_pass.py` with real NVDA and the deck audit, then record the results as a new section in `docs/testing/` before calling M2 done.
