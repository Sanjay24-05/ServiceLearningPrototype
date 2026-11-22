# Slide Proof: Visual Layout Checker for Blind Presentation Authors

**Design document · 2026-11-20 · Status: final draft for review**

**Constraints at a glance:** one developer; no fixed deadline (finish the working prototype as soon as possible); runs only on the developer's own Windows laptop for development, the faculty demo and later community testing; no installer for participants' devices.

> "Slide Proof" is a working name only.

---

## 1. Problem statement

Blind people who make presentations with a screen reader cannot independently check how their slides **look**. The screen reader reports objects in stacking order, as a one-dimensional list (A11yBoard, CHI '23). It does not report where objects sit, whether they overlap, whether text runs off the slide or overflows its box, whether an image is stretched, or whether the slides are consistent with each other. Those are exactly the things a sighted audience notices first.

Today the workaround is to ask a sighted colleague to look over the deck. That costs the author independence, privacy (confidential work decks), time (waiting for someone), and standing at work (being seen as needing help with routine tasks).

Existing tools work in the opposite direction:

- **PowerPoint's Accessibility Checker** checks whether a deck can be read **by** blind people (alt text, reading order).
- **A11yBoard** (UW, CHI '23 and its Google Slides follow-up) is a research **editing environment** based on touchscreen exploration and spoken commands. It replaces the editor; it is not a proofreading tool for finished files.

**Problem statement:** *A blind screen-reader user who has finished a slide deck has no independent, reliable way to find and fix the visual layout problems a sighted audience will notice before sending or presenting it.*

## 2. Target users and pain points

**Primary users:** fully blind people (including those with light perception only) who use a computer mainly through a screen reader, NVDA or JAWS on Windows, and who make or edit presentations for school or work. Examples: students submitting coursework decks, office workers, teachers, self-advocates giving talks.

**Pain points:**

| # | Pain point | Consequence |
|---|---|---|
| P1 | Can't perceive overlap or hidden content | A picture covers text without the author knowing |
| P2 | Can't perceive off-slide or overflowing content | Text is cut off or spills over in front of the audience |
| P3 | Can't perceive image distortion or blurriness | Stretched logos and photos look unprofessional |
| P4 | Can't perceive inconsistency across slides | Jumping titles and mixed fonts after pasting from other decks |
| P5 | Can't judge whether text is readable for others | Low contrast or tiny text on projected slides |
| P6 | Depend on sighted help to proofread | Loss of independence, privacy and time |
| P7 | Fixing layout blind is risky | Moving objects without feedback often makes things worse |

**Not in scope for the prototype:** low-vision, magnifier and braille-first users. The architecture is built to add them later (§5.3).

## 3. Proposed solution and value proposition

A **local, one-shot checker**. The author opens a .pptx file in a small web app that runs on their own computer, using their usual browser and screen reader. The app:

1. Analyses both the file's structure and **rendered images of each slide**.
2. Reports what a sighted viewer would notice, **in spatial language suited to screen-reader navigation**, ranked by how visible each problem is.
3. Offers **safe, explained fixes**. The author chooses which to apply.
4. Exports a **corrected copy** (the original is never touched) and **re-checks it**, confirming that the problems are gone and no new ones were introduced.

**Value proposition:** *Proofread your slides' appearance yourself, privately, in minutes, without asking a sighted person.*

**Design principles:**

- The author is in control. Nothing changes without consent, and every change is described in words.
- Few, important findings beat many trivial ones. Avoiding false positives matters more than catching everything.
- The tool states its confidence honestly ("likely" or "definitely").
- Everything runs locally. Files never leave the machine.
- The tool judges errors, not taste. It flags things that are objectively broken or inconsistent, not aesthetics.

## 4. Approaches considered

### 4.1 When checking happens (decided by the author of this project)

| Option | Trade-off | Decision |
|---|---|---|
| **One-shot check of a finished file** | Works with any editor's .pptx; allows the rendering step; fast to build | **Chosen** |
| Live PowerPoint add-in | Better feel, but Office.js gives limited shape detail and no rendering; slower to build | Rejected for now |

### 4.2 User interface surface (designer's call)

| Option | Trade-off | Decision |
|---|---|---|
| **Local web app (Python server on localhost + semantic HTML in the user's browser)** | Browsers are the best-supported surface for NVDA and JAWS (browse mode, heading navigation). Plain HTML gives accessibility almost for free. Easy to demo | **Chosen** |
| wxPython desktop app | Good native accessibility (NVDA itself uses wxPython), but harder to make rich, navigable reports | Rejected |
| Command line + HTML report | Simplest, but a weaker experience and harder to apply fixes interactively | Kept as a developer and test entry point only |

### 4.3 Rendering engine (designer's call)

| Option | Trade-off | Decision |
|---|---|---|
| **LibreOffice headless → PDF → PyMuPDF** | Free, cross-platform, scriptable. PDF gives exact rendered text positions, sizes and colours. Rendering can differ from PowerPoint | **Chosen (default)** |
| PowerPoint COM automation (Windows) | Exact fidelity, but needs PowerPoint installed and is Windows-only | Future optional backend behind the same interface |

## 5. Architecture and technology stack

### 5.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best .pptx and PDF libraries |
| Reading and writing .pptx | `python-pptx` (+ direct `lxml` access where needed) | Mature; full access to shape geometry and XML |
| Rendering | LibreOffice 7.6+ headless (`soffice --headless --convert-to pdf`) | See §4.3 |
| PDF parsing and rasterising | `PyMuPDF` (fitz) | Text spans with bounding boxes, font, size, colour; page → PNG |
| Image maths | `Pillow`, `numpy` | Contrast sampling, image size |
| Web server | `FastAPI` + `Jinja2` server-rendered HTML (no JavaScript framework) | Server-rendered semantic HTML is the most predictable for screen readers |
| Tests | `pytest`; `axe-core` via Playwright for automated accessibility checks of the report page | |
| Fonts bundled or required | Carlito (metric-compatible with Calibri), Caladea (Cambria), Liberation Sans/Serif (Arial/Times New Roman) | Makes LibreOffice line-breaking match PowerPoint for the most common fonts |

The prototype runs on Windows (the primary environment for NVDA and JAWS). It should also work on macOS and Linux, but that is not tested.

### 5.1a Deployment (decided)

- **One machine:** the developer's Windows laptop. It is used for development, the faculty demo, and community testing sessions. There is **no packaged installer** and no support for participants' own devices in this phase.
- **Setup is documented in the README and done once:**
  - Python 3.11+ in a virtual environment (`pip install -r requirements.txt`).
  - LibreOffice 7.6+ installed normally. The app finds `soffice.exe` in its standard install path, or through a `SOFFICE_PATH` environment variable.
  - The Carlito, Caladea and Liberation fonts installed for the user.
  - NVDA (free). For testing, JAWS in its 40-minute demo mode.
- **Start-up:** `python -m slideproof` starts the server on `127.0.0.1` only (never on the network) and opens the default browser at the start page. A start-up check reports any missing dependency in plain text in the console and on the start page.
- **Consequence:** setup polish and dependency detection are developer-grade, not consumer-grade. Packaging (for example PyInstaller with bundled LibreOffice) is listed under Future work (§12.3).

### 5.2 Components

```
                ┌──────────────┐
 .pptx ───────► │  Loader      │  python-pptx → Presentation Model (geometry, text, images, z-order)
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  Renderer    │  LibreOffice → PDF → per-slide PNG + text spans
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  Linker      │  matches rendered text spans to model shapes
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  Checks      │  independent check modules → Findings (structured JSON)
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  Prioritiser │  severity × magnitude × confidence; suppression of intentional patterns
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  Describer   │  Findings → spatial language (short + full forms)
                └──────┬───────┘
                       │
                ┌──────▼───────┐       ┌─────────────┐
                │  Presenter   │◄─────►│  Fixer      │ applies selected fixes to a copy → re-runs pipeline
                │  (screen     │       └─────────────┘
                │   reader     │
                │   HTML)      │
                └──────────────┘
```

### 5.3 Extensibility rule

**Checks never produce prose, and presenters never compute geometry.** Every check emits structured `Finding` objects. The Describer turns them into language data (short and full sentence variants plus structured location fields). Presenters only lay that data out. Later views (braille-concise, low-vision visual with zoomed crops) become new presenters over the same findings. Rendered slide PNGs are kept per run so a future low-vision view can crop them.

### 5.4 Core data structures (indicative)

```python
Element:
  id: str                 # f"s{slide_id}-sh{shape_id}" (stable across runs of the same file)
  slide_index: int; slide_id: int; shape_id: int
  kind: "title" | "body" | "textbox" | "picture" | "shape" | "table" | "chart" | "group" | "other"
  label: str              # human label, e.g. 'text box "Revenue grew 12%…"', 'picture "team.jpg"'
  bbox: Rect              # absolute, EMU, axis-aligned (rotation → bounding box of rotated rect)
  z: int                  # stacking order on slide
  rotation: float
  filled: bool            # has an opaque fill / is a picture
  text: str | None
  runs: list[RunStyle]    # font family, size (pt), bold, colour as declared in file
  image: ImageInfo | None # native px size, crop fractions, format
  placeholder_type: str | None

RenderedSpan:  slide_index, text, bbox (points → EMU), font, size_pt, colour_rgb, element_id | None

Finding:
  id, check_id, slide_index, element_ids: list[str]
  severity: "visible" | "minor"
  confidence: "definite" | "likely"
  magnitude: float        # 0..1 check-specific (e.g. fraction covered)
  measurements: dict      # raw numbers, kept for the "details" view and tests
  location: Location      # grid cell(s), relative relationships
  fix: Fix | None

Fix:
  fix_id, kind, safety: "safe" | "confirm", params: dict, describe_before, describe_after
```

## 6. Slide processing and rendering pipeline

1. **Intake.** Accept a single `.pptx` upload (limit 50 MB, 100 slides). Reject `.ppt`, `.key` and `.odp` with a clear message ("Save as .pptx and try again"). Copy into a per-run temporary folder, compute a SHA-256 for run identity, and never modify the upload.
2. **Load the model** (python-pptx):
   - Slide size from `presentation.slide_width/height` (EMU; 914,400 EMU = 1 inch).
   - Walk shapes in z-order. Resolve placeholder geometry inherited from layout or master when the slide shape has no `xfrm`.
   - **Groups:** recurse, transforming child coordinates using the group's `off/ext` and `chOff/chExt` into absolute slide coordinates.
   - **Rotation:** store the axis-aligned bounding box of the rotated rectangle and mark it `rotated`. Checks treat rotated elements with lower confidence.
   - **Pictures:** read native pixel size from the image blob (Pillow) and crop fractions (`crop_left/right/top/bottom`).
   - Charts, SmartArt, tables, media, OLE objects: treated as **opaque boxes**. Geometry checks apply; their internals are not analysed.
   - Hidden slides are analysed but labelled "hidden slide".
3. **Render** (LibreOffice):
   - `soffice --headless --norestore -env:UserInstallation=file:///<temp-profile> --convert-to pdf --outdir <run> deck.pptx`. Use an isolated profile so it does not clash with a LibreOffice instance the user has open. Timeout 120 s.
   - PyMuPDF: for each page, rasterise to PNG at 96 DPI-equivalent for the slide size, and extract text spans (`page.get_text("dict")`) with bbox, font, size and colour.
   - PDF points convert to EMU (1 pt = 12,700 EMU). Check that page count equals slide count. If they differ (for example hidden slides being skipped), map pages to visible slides. If mapping is impossible, disable rendered checks for the deck and say so in the report.
   - **If LibreOffice is missing or fails:** run geometry-only checks and state in the report which checks were skipped and why. The tool must never fail silently.
4. **Link spans to shapes.** For each rendered span, find model text elements whose text contains the span text (normalised whitespace). Choose the candidate whose bbox best contains the span's start point, breaking ties by z-order. Spans that cannot be linked are kept as `element_id = None` and used only for slide-level checks.
5. **Run checks** (§7). Each check is a pure function `(model, render) → list[Finding]`, unit-tested against fixtures.
6. **Prioritise and describe** (§7.3, §8), then render the report.

Expected speed: tens of seconds for a 20-slide deck, dominated by LibreOffice start-up and conversion. This is to be measured in milestone M0. The report page shows progress while it works (§8).

## 7. Layout detection and issue identification

### 7.1 MVP checks

Thresholds are starting values to be tuned against the demo deck and a corpus of real decks (§11). "Reliability" is how much we trust the check to be right in practice.

| ID | Check | Method | Default severity | Reliability |
|---|---|---|---|---|
| C1 | **Off-slide content** | Element bbox outside slide rect. Flag if > 2% of the element's area is outside, or any rendered text span is outside | visible (minor if < 10% and no text cut) | High. Zero-width or zero-height lines are not checked yet |
| C2 | **Overlap** | Pairwise intersection of **content boxes** on each slide (O(n²); n is small). Magnitude = intersection ÷ content area of the *lower* element. Flag when the upper element is filled or a picture and covers ≥ 5% of a lower element's content; or when two text elements' content boxes intersect. See the content-box rule below the table | visible | High geometrically; intent is ambiguous, so exemptions apply (7.2) |
| C3 | **Text overflow** | Union of rendered spans linked to an element extends beyond its bbox by > 0.1 inch (vertical or horizontal) | visible | Medium (depends on rendering fidelity) → confidence "likely" |
| C4 | **Distorted image** | displayed aspect ÷ native aspect after crop. Flag if it deviates > 5% | visible if > 15%, otherwise minor | High |
| C5 | **Low-resolution image** | effective DPI = native px ÷ displayed inches (per axis, take the minimum). Flag < 72 (visible) or < 110 (minor) | visible or minor | High |
| C6 | **Small text** | Rendered span size (after autofit) < 12 pt → visible; < 18 pt on body text → minor (projection guideline) | visible or minor | High |
| C7 | **Low contrast** | Text colour from the rendered span. Background = median colour of PNG pixels inside the span's bbox, excluding pixels within ΔE < 10 of the text colour. WCAG ratio: flag < 4.5:1, or < 3:1 for ≥ 18 pt or ≥ 14 pt bold | visible | Medium (images behind text are noisy) → "likely" when the background is a picture |
| C8 | **Inconsistent title position** | Collect title-placeholder bboxes on non-title-layout slides. Dominant position = most common within a 0.1-inch tolerance. Flag slides whose title top or left differs by > 0.15 inch. Needs ≥ 3 comparable slides | visible | High |
| C9 | **Mixed fonts** | Count font families across all rendered spans, weighted by character count. Families used for < 10% of characters on ≤ 2 slides are flagged as stray (excluding symbol fonts and code-like monospace) | minor | High |
| C10 | **Empty or stray elements** | Text boxes with no text, zero or near-zero size shapes, elements entirely off-slide | minor (visible if it has an outline or fill) | High |
| C11 | **Hidden content** | Text or picture element whose content box is ≥ 95% covered by an opaque element above it | visible | Medium–high |

**Content-box rule (designer's call, applies to C2, C11 and F6).** Text placeholders and text boxes are often far larger than the text inside them; a body placeholder usually covers most of the slide even when the bullets fill only the top. Measuring overlap against the outline would flag pictures placed in the empty part, which breaks the "few false positives" principle. So overlap is measured against each element's **content box**:

- **Text elements:** the union of their linked rendered spans (§6 step 4), padded by 0.05 inch.
- **Text elements without rendering (fallback):** an *estimated* text extent from the file. Lines are estimated per paragraph as `ceil(chars × 0.5 × size_pt ÷ box_width_pt)` (average glyph width ≈ 0.5 em), and height = Σ lines × size × line spacing (default 1.2), anchored to the frame's vertical anchor and insets. Findings based on estimates are marked "likely".
- **Pictures, filled shapes, tables, charts:** their bbox.

C2 for picture-over-picture and shape-over-picture can run from the model alone (M1). Text-content overlap needs rendered spans or the estimate (M2).

### 7.2 False-positive control (exemptions)

These are deliberate patterns that must not be flagged:

- **Background images:** a picture covering ≥ 90% of the slide that sits at the bottom of the z-order is treated as background. It is excluded from C2 and C11 as the "lower" element; C7 then applies to text over it.
- **Labels on shapes:** text within or on a filled shape that fully contains it (callouts, buttons, diagram boxes). These are excluded from C2.
- **Decorative artwork (M2):** C2 only reports an object covering something that shows content — text, a picture, a table or a chart. Shapes stacked on a plain shape without text (icons, badges, frames) are not reported.
- **Empty placeholders (M2):** an empty placeholder is never shown in a slideshow, whatever its fill, so C10 reports it as minor and removable. Only a non-placeholder empty box with a fill or outline is visible.
- **Text inside its own shape:** an autoshape with text is a single element, never an overlap with itself.
- **Grouped elements:** overlaps between members of the same group are excluded. The group was made deliberately.
- **Deliberate bleed:** an element with no text (a picture or a shape without text) whose bounding box spans ≥ 90% of the slide's width or ≥ 90% of its height (backgrounds, banners, full-width strips) is not reported by C1. Every other element follows the normal C1 rule (more than 2% outside is a finding; visible at ≥ 10% outside, otherwise minor) and keeps its F1 fix. Empty text elements are never reported by C1: they belong to C10 (empty or stray objects). The background exemption above is unchanged.
- **"That's intentional" marking:** the user dismisses a finding.
  - **Within a run (must-have):** the report's "Mark as intentional" button is a form post to the server, which keeps per-run state. The server returns the report with the finding moved into a collapsed "Marked intentional" section, updated counts, and focus placed on a confirmation message ("Marked intentional. 2 visible problems remain.") at the position of the next finding. A marked finding's fix is deselected.
  - **Across runs (should-have):** remembered in a local JSON file keyed by `(file name, slide_id, sorted shape_ids, check_id)` and suppressed on future runs of the same deck, with a count of suppressed findings shown in the summary.

### 7.3 Prioritisation

- Two tiers shown to the user: **"Visible problems"** (an audience will likely notice) and **"Minor polish"**.
- Within a tier, rank by `severity_weight × magnitude × confidence_weight` (definite = 1.0, likely = 0.7). Ties are broken by slide order.
- The summary counts only the visible tier prominently. Minor findings are collapsed under their own heading.
- Hard cap: if a single slide produces > 5 findings from the same check, group them into one finding ("Seven text boxes on this slide overlap each other").

## 8. Communicating findings through screen readers

### 8.1 Spatial language (Describer)

- **Location:** the 3×3 grid of the slide, based on the element's centre: "top left", "top centre", "top right", "middle left", "centre", … "bottom right". Large elements are described by extent: "spans the whole top of the slide", "fills the left half".
- **Relationships:** between two elements, give direction ("to the right of and slightly below the title") and coverage using friendly fractions: < 15% "a small part of"; 15–30% "about a quarter of"; 30–40% "about a third of"; 40–60% "about half of"; 60–90% "most of"; > 90% "all of".
- **Amounts:** relative to the slide, not inches. "Sticks out past the right edge by about a fifth of its width"; "sits noticeably lower than the titles on the other 11 slides".
- **Element names:** never internal names like "Google Shape;123" or "TextBox 6". Use the kind plus the first ~6 words of text (`text box "Revenue grew 12 percent in…"`), alt text or file name for pictures, or "picture 2" as a last resort. The title element is named "the title".
- **Two forms for every finding:** a **short** form (front-loaded, ≤ ~90 characters: "Slide 4: picture covers about a third of the bullet list") and a **full** form (adds what it means for the audience and the measurement).
- Fixed terms throughout: the same word always means the same thing ("covers", "sticks out", "stretched").

### 8.2 Page structure (Presenter, screen-reader HTML)

Plain semantic HTML: no custom widgets, no colour-only or icon-only meaning, `lang` set, unique `<title>` per page.

**Page 1 – Choose a file**

- `<h1>Check slide layout</h1>`, one labelled `<input type="file" accept=".pptx">`, one "Check slides" button. A short paragraph says the file stays on this computer.

**Page 2 – Checking (progress)**

- One `role="status"` region updated at most every 3 s ("Rendering slides… Checking slide 6 of 12"). When finished, load the report and move focus to its `<h1>`.

**Page 3 – Report**

```
<title>deck.pptx – 3 visible problems – Slide Proof</title>
h1  Report for deck.pptx
p   12 slides checked. 3 visible problems on 3 slides, 4 minor. 1 marked intentional.
p   (if applicable) Note: text overflow and contrast checks were skipped because LibreOffice is not installed.

h2  Visible problems (3)
  h3  Slide 4, "Quarterly results": picture covers about a third of the bullet list
      p   The picture "chart.png" in the right half sits on top of the lower third of the
          bullet list "Revenue grew 12 percent…". Your audience will not be able to read
          the last two bullets. Confidence: definite.
      fieldset  legend "Fix for this problem"
          checkbox (unchecked)  "Move the picture below the list and shrink it to fit. Needs your review."
      button  "Mark as intentional"
      details/summary "Layout of slide 4"  → ordered list of all objects, top-to-bottom, left-to-right,
          each with location and size ("Title, top, full width")
  h3  Slide 7, ...
h2  Minor polish (4)
  ...
h2  Apply fixes
  p   2 fixes selected.
  button "Create corrected copy"
```

- **Heading navigation is the main way to move around:** H for the next finding, 2 for the next tier, and the NVDA/JAWS headings list for an overview.
- Checkboxes for **safe** fixes are pre-checked and for **confirm** fixes unchecked. Each label says which kind it is.
- The "Layout of slide N" disclosure gives a text map of the slide so the user can build a mental model.
- No `aria-live` spam, no auto-advancing content, no timeouts.

**Page 4 – Result**

- `h1 Corrected copy created`. Summary: fixes applied, problems resolved, new problems introduced (should be 0), any fix rolled back and why. A download link with the explicit file name. A "Changes made" list with a before/after description per fix. A "Check another file" link.

### 8.3 Screen-reader compatibility

- **Test matrix (must pass):** NVDA (latest) + Firefox, NVDA + Chrome, JAWS (latest; the 40-minute demo mode is enough for testing) + Chrome, JAWS + Edge. Smoke test with Windows Narrator + Edge.
- **Per-release script:** reach every finding by H; operate every control by keyboard alone (Tab, Space, Enter); hear the status updates; land on the report `<h1>` after processing; confirm no unlabelled controls. Plus automated axe-core tests (zero serious or critical violations).

## 9. Safe corrections and export

### 9.1 Fix catalogue (MVP)

| Fix | For | Safety | Algorithm |
|---|---|---|---|
| F1 Pull back on-slide | C1 | **safe** | Translate the minimum distance needed to fit inside the slide with a 0.2-inch margin. If the element is larger than the slide area, scale it down, keeping its proportions, then translate |
| F2 Restore proportions | C4 | **safe** | Fit the native (cropped) aspect ratio inside the current frame: keep the centre and shrink the stretched dimension, so the footprint can only shrink and never covers neighbouring objects. If the frame was already off-slide, apply F1 afterwards |
| F3 Match title position | C8 | **safe** | Set the title's left/top/width/height to the deck's dominant title geometry |
| F4 Remove empty element | C10 (empty text box, no fill or outline) | **safe** | Delete the shape element from the slide XML |
| F5 Use the deck's main font | C9 | confirm | Set the font name of the affected runs to the deck's dominant family; keep size and bold/italic |
| F6 Resolve overlap | C2, C11 | confirm | Search for a placement of the **upper** element (or the smaller one if it isn't a background or label) that (a) stays on the slide, (b) overlaps no other element's **content box** (§7.1), and (c) minimises movement. Candidates: positions on a 0.1-inch grid, and the same positions scaled to 90/80/70% size. Pick the lowest cost = displacement + 2 × size reduction. If nothing qualifies, offer no fix and advise instead |
| F7 Fit text | C3 | confirm | Turn on "shrink text on overflow" (`normAutofit`) for the text frame. If the re-render still overflows, reduce font size in 1-pt steps down to a floor of 14 pt; otherwise give advice only ("too much text for this box; consider splitting the slide") |
| — | C5, C6, C7 | advice only | Explain the problem and what to change; no automatic fix in the MVP |

### 9.2 Workflow

1. The user selects fixes on the report (safe ones pre-selected).
2. "Create corrected copy" → the Fixer applies fixes **in a fixed order** (F4, F5, F3, F2, F1, F7, F6) to an in-memory copy, changing only `a:xfrm` offsets and extents, run font names, `bodyPr` autofit, or deleting shapes. Nothing else in the XML is touched.
3. Save as `<name> (checked).pptx` next to the original in the run folder and offer it for download. **The original is never overwritten.**
4. **Verification:** re-run the whole pipeline (including rendering) on the copy. For each applied fix: if the targeted finding is gone and no new *visible* finding involves the moved elements, mark it "resolved". Otherwise **roll back that fix**, re-save, and report "Couldn't safely fix: …".
5. Show the result page (§8.2) with a plain-language change log, for example: "Slide 9: photo "team.jpg" restored to its natural shape; it is now narrower and still centred."

**Undo:** the original file is the undo. The user can re-run on the corrected copy, or untick fixes and export again.

## 10. Demonstration workflow

### 10.1 Demo deck (generated, with ground truth)

The deck is generated by a script (`tools/make_demo_deck.py`, python-pptx) so it is reproducible and doubles as the main test fixture. The script also writes `expected_findings.json` (ground truth), so precision and recall can be measured.

| Slide | Content | Planted error | Expected |
|---|---|---|---|
| 1 | Title slide "Community Garden Project" | none | no findings |
| 2 | Agenda bullets | Text box sticks out past the right edge by ~20% | C1 visible + F1 |
| 3 | "Results" bullets + chart picture | Picture covers ~35% of the bullet list's rendered text (content box), not just its placeholder outline | C2 visible + F6 (confirm) |
| 4 | "Our team" photo | Photo stretched 1.6× wide; logo at ~50 DPI | C4 visible + F2; C5 visible (advice) |
| 5 | "Budget" | Title moved 0.6 inch lower than other titles; one box in a stray font (Georgia among Calibri) | C8 + F3; C9 minor + F5 |
| 6 | "Timeline" | 14 bullets in a fixed-size box with autofit off | C3 likely + F7 |
| 7 | "Volunteers" | Light grey (#BBBBBB) text on white; white text over a bright photo | C7 visible ×2 (advice) |
| 8 | "Thank you" | Full-slide background photo with text on top; a label on a filled callout shape; an empty text box | **only** C10 minor + F4 (the background and label must **not** be flagged) |

Slides 1 and 8 show that the tool **stays quiet when it should**, which is as important as catching errors.

### 10.2 Live demo script (~7 minutes)

1. Explain the problem: play 20 seconds of NVDA reading slide 3 in PowerPoint. It sounds perfectly fine.
2. Show the slide to the sighted audience. The chart covers the bullets.
3. With NVDA running and the monitor optionally switched off, open Slide Proof and upload the deck. NVDA announces progress, then the report heading.
4. Press H through the findings; open "Layout of slide 3"; mark one finding intentional.
5. Select the overlap fix, create the corrected copy; NVDA reads the result summary and change log.
6. For the sighted audience: open the original and corrected decks side by side (or show the before/after PNGs).
7. Show the precision/recall table from the ground-truth test and results on real-world decks (§11).

## 11. Technical risks, limitations and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **LibreOffice renders differently from PowerPoint** (fonts, autofit, line breaks) | False or missed overflow, contrast and small-text findings | Install metric-compatible fonts; mark render-based findings "likely"; geometry checks do not depend on rendering; future PowerPoint COM backend (§4.3) |
| **Too many false positives** | Users stop trusting the tool or uninstall it | Conservative thresholds; exemptions (§7.2); two tiers; "intentional" marking; measure precision on a corpus of ~20 real public decks and tune before the demo |
| Placeholder inheritance, groups and rotation are handled imperfectly | Wrong positions → wrong findings | Explicit tests for inherited placeholders, nested groups and rotated shapes; rotated → lower confidence |
| Linking spans to shapes is ambiguous (repeated text, overlapping boxes) | Overflow or contrast finding attached to the wrong element | Containment + text matching + z-order; when ambiguous, downgrade to "likely" and name both candidates |
| Charts, SmartArt and tables are opaque | Internal problems not detected | State the limitation in the report ("The contents of charts and diagrams are not checked") |
| Overlap fix makes the layout worse | Harms trust | Confirm-only; verification re-check; automatic rollback; original never modified |
| NVDA and JAWS behave differently | Inconsistent experience | Plain semantic HTML, minimal ARIA, test matrix (§8.3) |
| Speed of rendering large decks | Long waits | Progress status; geometry results first if needed; limit of 100 slides |
| `.ppt`, `.odp` and Google Slides | Unsupported input | Clear message; Google Slides users download as .pptx (documented) |
| **No validation with real users yet** | The design may miss real needs | Assumptions list (§13); community validation plan; design built to change |

**Reliability summary.** Reliable: C1, C2 (geometry), C4, C5, C6, C8, C9, C10; fixes F1–F4. Medium: C3, C7, C11; fixes F5–F7. **Aspirational (not in the MVP):** see §12.2.

## 12. Scope

### 12.1 MVP must-haves

- .pptx intake, model loading (including placeholders, groups and rotation bounding boxes)
- LibreOffice rendering with geometry-only fallback
- Checks C1–C11 with the exemptions in §7.2
- Prioritisation into two tiers
- Describer (spatial language, short and full forms, human element names)
- Screen-reader HTML report with heading structure, per-slide text map, fix selection, and "Mark as intentional" within a run (§7.2)
- Fixes F1–F4 (safe) and F5–F7 (confirm), with corrected-copy export, verification re-check and rollback
- Demo deck generator + ground truth + precision/recall test
- Tested with NVDA + JAWS (§8.3)

### 12.2 Should-have (only if on schedule)

- "Mark as intentional" remembered across runs (in-run marking is a must-have)
- Almost-aligned check (edges within 0–0.05 inch of each other but not equal) as minor polish
- Command-line entry point that prints a text report (developer tool)

### 12.3 Future (aspirational, explicitly out of the prototype)

- Low-vision visual view (zoomed crops + slide overview map), braille-concise view
- Spatial-audio "explore mode" (stereo = horizontal position, pitch = height)
- PowerPoint COM rendering backend for exact fidelity
- .docx layout checks (fake headings, manual spacing, mixed fonts)
- PowerPoint or Google Slides add-in (live mode)
- Image content checks using ML (cropped faces, blurry photos)
- Smarter re-layout (multi-object rearrangement)
- Packaged installer for participants' own computers (PyInstaller + bundled LibreOffice and fonts, launcher that works with a screen reader)

## 13. Assumptions to validate with the community

When the faculty connects the project with blind users:

1. Blind authors make slides often enough, and rely on sighted checking, so this matters to them.
2. The 3×3 grid and fraction language builds a usable mental model.
3. The two-tier ranking matches what users care about.
4. Pre-selecting safe fixes is welcome rather than presumptuous.
5. Users would send a deck checked by the tool without a sighted second look. This is the core success question.

**Validation study (outline):** 5–8 screen-reader users, each given a deck with planted errors. Measure errors found and fixed with and without the tool, time taken, and SUS (System Usability Scale) score, plus a confidence question. Sighted raters blindly compare decks before and after.

**Session setup (on the developer's laptop):**
- Before each session, ask the participant which screen reader they use and their usual speech rate and verbosity, and set the laptop up to match. Allow 10 minutes at the start for them to get used to the laptop and keyboard. Bringing an external keyboard helps.
- If a participant brings one of their own decks, use it only with their consent. Process it on the laptop, which stays offline, and delete the deck and all run files at the end of the session in front of them.

## 14. Implementation roadmap

**Assumptions:** one developer; no fixed deadline, so the goal is the shortest path to a convincing working prototype. Durations are **focused effort weeks** at about 15–20 hours a week. Full-time work would roughly halve the calendar time.

**Strategy: an end-to-end thin slice first, then widen.** With one developer, the biggest danger is building every check before anything works from start to finish. The roadmap therefore reaches a working loop early: upload → find → describe → fix → export → verify. It then adds checks and fixes to that loop. Every milestone ends with something that runs.

| Milestone | Effort | Deliverables | Exit criteria |
|---|---|---|---|
| **M0 De-risk** | 1 wk | Project skeleton, `pytest`, README setup steps; demo deck generator + `expected_findings.json`; spike: LibreOffice → PDF → spans + PNG on this laptop; speed measured | Spans with bboxes, sizes and colours extracted for all 8 demo slides; conversion time for the demo deck and a 30-slide deck recorded |
| **M1 Thin slice** | 2 wks | Loader (placeholders, groups, rotation bounding box); C1 + C4; minimal Describer (grid location, element names, short + full forms); prioritiser (tiers); FastAPI pages 1–4 with real heading structure; F1 + F2; export to a copy; verification re-check + rollback | On the demo deck: slides 2 and 4 are reported, fixed and verified in the browser; **full NVDA + Firefox walkthrough without looking at the screen**; axe shows 0 serious issues. *First thing worth showing anyone.* |
| **M2 Geometry breadth** ✅ done 2026-11-22 | 1 wk | C2 (pictures, shapes, and text via estimated content boxes), C5, C8, C9 (from the model, theme-aware), C10; estimated text extent; exemptions (§7.2); F3, F4; per-slide "Layout of slide N" text map | All planted geometry errors found; slides 1 and 8 produce only the expected C10 |
| **M3 Render checks** | 1.5 wks | Span linker; content boxes from rendered spans; C2 for text content; C3, C6, C7, C11; C9 from rendered spans; geometry-only fallback when LibreOffice is missing | Demo deck precision and recall = 100%; fallback tested by renaming `soffice.exe` |
| **M4 Remaining fixes + intentional** | 1.5 wks | F5, F6, F7; "Mark as intentional" within a run; change log wording; JAWS + Chrome/Edge walkthrough | Every demo fix resolves its finding with 0 new visible findings; JAWS walkthrough passes |
| **M5 Harden + demo-ready** | 1 wk | Run on ~20 real public decks and tune thresholds; describer wording pass; demo script rehearsal; before/after PNG sheet for the sighted audience; validation study materials (§13) | Precision ≥ 80% on the visible tier for the real decks; demo runs end to end twice in a row without intervention |

**Total: about 8 effort weeks.** Checkpoints:
- **After M1 (~3 weeks):** an honest early preview, enough to show faculty progress if they want one.
- **After M3 (~5.5 weeks):** a credible demo, with all problems detected and the simple fixes working.
- **After M5:** ready for the faculty demo and community testing.

**If you need to finish sooner,** cut in this order:
1. Should-haves (§12.2).
2. F7 (keep C3 as advice).
3. F6 (keep C2 as advice).
4. C11.
5. F5.

Never cut the screen-reader walkthroughs or the verification re-check.

**If a second person joins:** the clean split is the presentation layer (pages, Describer wording, screen-reader testing) versus the analysis layer (loader, renderer, checks, fixes). The `Finding` JSON (§5.4) is the contract between them. Freeze it at the end of M1.

## 15. Left to the builder

- Project layout, module names, exact class design
- Exact rasterisation DPI and temporary-file cleanup policy
- Exact wording of messages, within the rules in §8.1 (to be reviewed later with users)
- Choice of real-world decks for the corpus (public, permissively licensed)
- Logging and error-report format
