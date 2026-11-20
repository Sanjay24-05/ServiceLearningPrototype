# Slide Proof M0 + M1 (De-risk and Thin Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working end-to-end loop that a screen-reader user can complete without sight: upload a .pptx, get findings for off-slide content (C1) and distorted images (C4), apply safe fixes (F1, F2), export a corrected copy, and verify it. Build on a de-risked LibreOffice rendering pipeline and a generated demo deck with an answer key.

**Architecture:** This is a local Python package `slideproof`.
- **Analysis pipeline:** the loader (python-pptx) builds a geometry model, and the renderer (LibreOffice → PDF → PyMuPDF) produces per-slide PNGs and text spans. Pure check functions turn these into structured `Finding`s. A prioritiser ranks them into two tiers, and a describer turns them into screen-reader-friendly language.
- **Fixes:** applied to a copy, then the copy is re-analysed for verification, with rollback.
- **Interface:** a FastAPI server bound to 127.0.0.1 serves plain server-rendered semantic HTML.

**Tech Stack:**
- Python 3.11+, python-pptx 1.0.2, PyMuPDF 1.24.10, Pillow 10.4.0
- FastAPI 0.115.0, uvicorn 0.30.6, Jinja2 3.1.4, python-multipart 0.0.9
- pytest 8.3.3, httpx 0.27.2
- playwright 1.47.0 + axe-playwright-python 0.1.4 (accessibility tests)
- LibreOffice 7.6+ (external)

**Spec:** `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md` (sections cited as §N). This plan covers roadmap milestones **M0 and M1** (§14). M2–M5 get their own plans after M1's exit criteria pass.

## Global Constraints

- Runs on the developer's Windows laptop; server binds to `127.0.0.1` only, port `8765` (§5.1a).
- The original upload is **never modified**; output is `<name> (checked).pptx` (§9.2).
- Units: 914,400 EMU = 1 inch; 1 pt = 12,700 EMU (§6).
- Intake limits: `.pptx` only, ≤ 50 MB, ≤ 100 slides; other extensions get "Save as .pptx and try again" (§6).
- LibreOffice call: `soffice --headless --norestore -env:UserInstallation=<file URI of temp profile> --convert-to pdf --outdir <run dir> <deck>`; timeout 120 s (§6).
- If LibreOffice is missing or fails: geometry checks still run and the report says which checks were skipped and why. The tool never fails silently (§6).
- Checks never produce prose; presenters never compute geometry (§5.3).
- Element ids are `f"s{slide_id}-sh{shape_id}"` (§5.4).
- Severity values `"visible" | "minor"`; confidence `"definite" | "likely"`; weights: visible 2, minor 1, definite 1.0, likely 0.7 (§7.3).
- Fix order when applying: `F4, F5, F3, F2, F1, F7, F6` (§9.2). Only `a:xfrm` offsets/extents (in this plan) are changed.
- Safe fixes are pre-checked; confirm fixes are unchecked; each label states which kind (§8.2).
- HTML: semantic elements only, `lang="en"`, unique `<title>` per page, no colour- or icon-only meaning, status updates at most every 3 s, focus moves to report `<h1>` (§8.2).
- Element names never expose internal shape names like "TextBox 6" (§8.1).
- Coverage words: < 15% "a small part of"; 15–30% "about a quarter of"; 30–40% "about a third of"; 40–60% "about half of"; 60–90% "most of"; > 90% "all of" (§8.1).
- Fixed terms: "sticks out", "stretched", "covers" (§8.1).

## Review Focus

1. **Non-16:9 slide sizes (4:3, A4, custom):** every rectangle calculation uses the deck's own slide size. A 4:3 deck with an off-slide box is reported correctly → test in Task 5.
2. **Shapes with no resolvable geometry** (connectors, graphic frames or placeholders whose layout lacks an `xfrm`): the loader skips them and records the skip instead of crashing → test in Task 4.
3. **Bad uploads** (not a zip, renamed `.ppt`, > 50 MB, > 100 slides, corrupt pptx): the user gets a plain-language error page, never a 500 → tests in Task 9.
4. **Unusual file names** (spaces, non-ASCII, e.g. `Café plan.pptx`): the report shows the name correctly and the download is called `Café plan (checked).pptx` → test in Task 9.
5. **LibreOffice missing, failing or timing out:** analysis completes with geometry checks and the report shows the skipped-checks note → test in Task 3 and Task 8.

---

## File Structure

```
pyproject.toml                 package metadata, pytest config (markers)
requirements.txt               pinned runtime + dev deps
README.md                      one-time setup, start command, running tests
.gitignore
slideproof/
  __init__.py
  __main__.py                  startup dependency check, open browser, run uvicorn
  units.py                     EMU constants, Rect geometry
  model.py                     ImageInfo, RunStyle, Element, SlideModel, DeckModel
  loader.py                    load_deck(): python-pptx → DeckModel
  render/
    __init__.py                re-exports render_deck, RenderResult
    soffice.py                 find_soffice(), convert_to_pdf()
    pdf.py                     RenderedSpan, RenderedSlide, read_pdf()
    pipeline.py                RenderResult, render_deck()
  findings.py                  Fix, Finding
  checks/
    __init__.py                CHECKS registry, run_checks()
    offslide.py                C1
    distortion.py              C4
  fixes/
    __init__.py                FIX_ORDER, apply_fixes()
    geometry.py                pull_on_slide(), restore_proportions()
    writer.py                  set_frame() on a python-pptx Presentation
  prioritise.py                Report, prioritise()
  describe/
    __init__.py                Description, describe()
    spatial.py                 grid_location(), portion_phrase(), coverage_phrase()
    names.py                   element_label()
  analysis.py                  Analysis, analyse()
  verify.py                    ExportResult, export_and_verify()
  web/
    __init__.py
    app.py                     create_app(), routes
    runs.py                    Run, RunStore, background jobs
    templates/base.html, index.html, progress.html, report.html, result.html, error.html
    static/progress.js         status polling + focus handling
tools/
  make_demo_deck.py            builds demo deck + expected_findings.json
  spike_render.py              M0 timing/inspection script
tests/
  conftest.py                  fixtures (demo deck, tiny deck builder, soffice marker)
  groundtruth.py               load expected findings, match against findings
  test_units.py, test_demo_deck.py, test_render.py, test_loader.py,
  test_checks.py, test_describe.py, test_prioritise.py, test_fixes.py,
  test_analysis.py, test_web.py, test_a11y.py
docs/testing/nvda-walkthrough.md   manual M1 exit checklist
```

---

### Task 1: Project skeleton and geometry primitives

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md`, `slideproof/__init__.py`, `slideproof/units.py`
- Test: `tests/test_units.py`

**Interfaces:**
- Produces:
  - `EMU_PER_INCH = 914400`, `EMU_PER_PT = 12700`, `inches(v: float) -> int`
  - `@dataclass(frozen=True) class Rect: x: int; y: int; w: int; h: int` with properties `right`, `bottom`, `area`, `center -> tuple[float, float]`; methods `intersect(other: Rect) -> Rect | None`, `contains(other: Rect) -> bool`, `translate(dx: int, dy: int) -> Rect`, `as_list() -> list[int]`, classmethod `from_list(v: list[int]) -> Rect`
  - `rotated_aabb(frame: Rect, degrees: float) -> Rect`: axis-aligned bounding box of `frame` rotated about its centre

- [ ] **Step 1: Initialise the repo and environment**

Run: `git init`, `python -m venv .venv`, `.venv\Scripts\activate`. Write `requirements.txt` with the exact versions in the header. Run `pip install -r requirements.txt` and then `playwright install chromium`. In `pyproject.toml`, register the pytest marker `soffice: needs LibreOffice` and set `testpaths = ["tests"]`. `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `/runs/`, `/tests/output/`.

- [ ] **Step 2: Write the failing tests**

```python
from slideproof.units import Rect, rotated_aabb, inches

def test_inches():
    assert inches(1) == 914400

def test_intersect_and_area():
    a, b = Rect(0, 0, 100, 100), Rect(50, 50, 100, 100)
    assert a.intersect(b) == Rect(50, 50, 50, 50)
    assert a.intersect(Rect(200, 200, 10, 10)) is None
    assert a.area == 10000

def test_contains():
    assert Rect(0, 0, 100, 100).contains(Rect(10, 10, 20, 20))
    assert not Rect(0, 0, 100, 100).contains(Rect(90, 10, 20, 20))

def test_rotated_aabb_90_swaps_dimensions_about_centre():
    assert rotated_aabb(Rect(0, 0, 200, 100), 90) == Rect(50, -50, 100, 200)

def test_rotated_aabb_zero_is_identity():
    assert rotated_aabb(Rect(5, 5, 10, 20), 0) == Rect(5, 5, 10, 20)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_units.py -v`
Expected: FAIL (`ModuleNotFoundError: slideproof.units`)

- [ ] **Step 4: Implement `slideproof/units.py`**

`rotated_aabb`: new width = `|w·cos θ| + |h·sin θ|`, new height = `|w·sin θ| + |h·cos θ|`, same centre, values rounded to int.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_units.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: project skeleton and Rect geometry"
```

---

### Task 2: Demo deck generator and ground truth (M0)

**Files:**
- Create: `tools/make_demo_deck.py`, `tests/conftest.py`, `tests/groundtruth.py`
- Test: `tests/test_demo_deck.py`

**Interfaces:**
- Produces:
  - `build_demo_deck(out_dir: Path) -> tuple[Path, Path]`: writes `demo_deck.pptx` and `expected_findings.json`, returns both paths. Also runnable as `python tools/make_demo_deck.py <out_dir>`.
  - `expected_findings.json`: list of `{"slide": int, "check": "C1".."C11", "shapes": [shape names], "severity": "visible"|"minor", "fix": "F1".."F7"|null}`
  - pytest fixture `demo_deck(tmp_path_factory) -> tuple[Path, Path]` (session scope) in `conftest.py`
  - pytest fixture `tiny_deck(tmp_path) -> Callable[..., Path]`: `tiny_deck(shapes: list[dict], slide_w=inches(13.333), slide_h=inches(7.5)) -> Path`. Each dict has `{"kind": "textbox"|"picture", "name": str, "x","y","w","h" (inches), "text"?: str, "px"?: (w, h), "rotation"?: float}` and builds a one-slide deck.
  - `tests/groundtruth.py`: `load_expected(path, checks: set[str]) -> list[dict]`; `match(findings, deck, expected) -> tuple[list, list, list]` returning (true positives, false positives, missed). Findings map to expected by (slide index, check id, set of shape names via `deck.element(id).name`).

The deck is 16:9 (`12192000 × 6858000` EMU, i.e. 13.333 × 7.5 in), built from python-pptx's default template ("Title Slide" and "Title Only" layouts). Every planted shape gets a stable `shape.name`. Pictures are generated with Pillow into `BytesIO` and get alt text set via `cNvPr.set("descr", ...)`.

| Slide | Layout | Shapes (name: geometry in inches) | Expected rows |
|---|---|---|---|
| 1 | Title Slide | title "Community Garden Project", subtitle "Spring update" | none |
| 2 | Title Only "Agenda" | `agenda-box` textbox x 10.13 y 1.5 w 4.0 h 3.0, 4 bullets | C1 visible F1 (sticks out ≈ 20% on the right) |
| 3 | Title Only "Results" | `results-list` textbox x 0.5 y 1.5 w 7 h 4.5, 5 bullets 24 pt; `results-chart` picture 1000×600 px x 5 y 3.5 w 5 h 3 (alt "Bar chart of harvest results") | C2 visible F6 |
| 4 | Title Only "Our team" | `team-photo` picture 800×600 px x 2.5 y 1.5 w 8 h 3.75 (alt "Team photo"); `logo` picture 100×100 px x 11 y 5.3 w 2 h 2 (alt "Garden logo") | C4 visible F2 (`team-photo`, 1.6× wide); C5 visible null (`logo`, 50 DPI) |
| 5 | Title Only "Budget" | title top moved +0.6 in vs layout; `budget-text` textbox Calibri 24 pt; `budget-note` textbox Georgia 24 pt | C8 visible F3 (title); C9 minor F5 (`budget-note`) |
| 6 | Title Only "Timeline" | `timeline-list` textbox x 0.5 y 1.5 w 6 h 4, 14 bullets 20 pt, `auto_size = MSO_AUTO_SIZE.NONE`, `word_wrap = True` | C3 visible F7 |
| 7 | Title Only "Volunteers" | `grey-text` textbox colour #BBBBBB 28 pt; `bright-photo` picture 800×400 px solid #FFF59D x 6 y 2 w 6 h 3; `photo-caption` textbox white 28 pt on top of `bright-photo` | C7 visible null ×2 (`grey-text`; `photo-caption`) |
| 8 | Title Only "Thank you" | `background` picture full slide, added first (bottom of z-order); `thanks-text` white 40 pt on top; `callout` filled rounded rectangle with text "Join us!"; `stray-box` empty textbox | C10 minor F4 (`stray-box`) only |

- [ ] **Step 1: Write the failing tests**

```python
from pptx import Presentation

def test_demo_deck_has_eight_slides_and_named_shapes(demo_deck):
    deck_path, _ = demo_deck
    prs = Presentation(deck_path)
    assert len(prs.slides) == 8
    names = {sh.name for s in prs.slides for sh in s.shapes}
    assert {"agenda-box", "results-chart", "team-photo", "logo", "stray-box", "background"} <= names

def test_expected_findings_cover_planted_errors(demo_deck):
    import json
    _, gt = demo_deck
    rows = json.loads(gt.read_text())
    assert {r["check"] for r in rows} == {"C1","C2","C3","C4","C5","C7","C8","C9","C10"}
    assert not [r for r in rows if r["slide"] == 1]
    assert [r["check"] for r in rows if r["slide"] == 8] == ["C10"]

def test_team_photo_is_stretched_1_6x(demo_deck):
    prs = Presentation(demo_deck[0])
    pic = next(sh for sh in prs.slides[3].shapes if sh.name == "team-photo")
    px_w, px_h = pic.image.size
    assert round((pic.width / pic.height) / (px_w / px_h), 2) == 1.6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_demo_deck.py -v`
Expected: FAIL (fixture `demo_deck` / module not found)

- [ ] **Step 3: Implement `tools/make_demo_deck.py`, fixtures, `tests/groundtruth.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_demo_deck.py -v`
Expected: 3 passed. Also run `python tools/make_demo_deck.py tests/output`, open the deck in PowerPoint, and confirm by eye that each planted error is visible.

- [ ] **Step 5: Commit**

```bash
git add tools tests
git commit -m "feat: demo deck generator with ground truth"
```

---

### Task 3: Rendering pipeline (M0 de-risk)

**Files:**
- Create: `slideproof/render/__init__.py`, `soffice.py`, `pdf.py`, `pipeline.py`, `tools/spike_render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces:
  - `find_soffice() -> Path | None`. Search order: env `SOFFICE_PATH` (if set and the file exists; if set but missing → `None`), `shutil.which("soffice")`, `C:\Program Files\LibreOffice\program\soffice.exe`, `C:\Program Files (x86)\LibreOffice\program\soffice.exe`.
  - `class RenderError(Exception)`
  - `convert_to_pdf(soffice: Path, pptx: Path, outdir: Path, profile_dir: Path, timeout: int = 120) -> Path`. Raises `RenderError` on non-zero exit, timeout, or missing output.
  - `@dataclass RenderedSpan: text: str; bbox: Rect (EMU); font: str; size_pt: float; rgb: tuple[int, int, int]`
  - `@dataclass RenderedSlide: page_index: int; png_path: Path; spans: list[RenderedSpan]`
  - `read_pdf(pdf: Path, png_dir: Path, slide_w: int, slide_h: int) -> list[RenderedSlide]`. Rasterises with `fitz.Matrix(96/72, 96/72)`. EMU scale = `slide_w / page.rect.width`. Spans come from `page.get_text("dict")` blocks → lines → spans, skipping whitespace-only spans; colour int → `(r, g, b)`.
  - `@dataclass RenderResult: status: Literal["ok", "skipped", "failed"]; reason: str | None; slides: list[RenderedSlide | None]` (one entry per deck slide, in deck order)
  - `render_deck(pptx: Path, run_dir: Path, hidden: list[bool]) -> RenderResult`
    - **Mapping pages to slides:** if the page count equals the number of slides, map 1:1. Else, if it equals the number of non-hidden slides, map pages to non-hidden slides in order and set hidden slides to `None`. Otherwise return `failed` with reason `"page count did not match slide count"`.
    - **Status and reason text:**
      - `skipped` with reason `"LibreOffice is not installed"` when `find_soffice()` is `None`.
      - `failed` with reason `"LibreOffice could not render this file"` for a `RenderError`.
      - `failed` with reason `"LibreOffice took too long"` on timeout.
    - The profile dir is `run_dir / "lo-profile"`, so it never clashes with a running LibreOffice.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from slideproof.render import render_deck
from slideproof.render.soffice import find_soffice

def test_find_soffice_respects_missing_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "nope.exe"))
    assert find_soffice() is None

def test_render_skipped_without_libreoffice(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "nope.exe"))
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "skipped" and r.reason == "LibreOffice is not installed"
    assert r.slides == [None] * 8

@pytest.mark.soffice
def test_render_demo_deck_spans_and_pngs(tmp_path, demo_deck):
    r = render_deck(demo_deck[0], tmp_path, hidden=[False] * 8)
    assert r.status == "ok" and len(r.slides) == 8
    assert all(s.png_path.exists() for s in r.slides)
    agenda = [sp for sp in r.slides[1].spans if sp.text.strip()]
    assert agenda and all(sp.size_pt > 0 for sp in agenda)
    grey = [sp for sp in r.slides[6].spans if sp.rgb == (0xBB, 0xBB, 0xBB)]
    assert grey
```

The `soffice` marker is auto-skipped in `conftest.py` when `find_soffice()` is `None`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL (`ModuleNotFoundError: slideproof.render`)

- [ ] **Step 3: Implement the render package**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_render.py -v`
Expected: 3 passed (the soffice test runs, not skipped, on the dev laptop with LibreOffice installed).

- [ ] **Step 5: Write `tools/spike_render.py` and record M0 timing**

`python tools/spike_render.py <deck.pptx>` prints the conversion time, page count and, per slide, the span count and first 3 spans (text, bbox in inches, font, size, colour). Run it on the demo deck and on a 30-slide deck (make one by duplicating slides). Record both timings and any span oddities in `docs/testing/m0-render-notes.md`.
Expected: the demo deck renders, and the timings are written down. This is the M0 exit criterion (§14).

- [ ] **Step 6: Commit**

```bash
git add slideproof/render tools/spike_render.py tests/test_render.py docs/testing
git commit -m "feat: LibreOffice render pipeline with graceful skip"
```

---

### Task 4: Presentation model and loader

**Files:**
- Create: `slideproof/model.py`, `slideproof/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `Rect`, `rotated_aabb`, `EMU_PER_PT` (Task 1)
- Produces:
  - `@dataclass ImageInfo: px_w: int; px_h: int; crop: tuple[float, float, float, float]  # left, top, right, bottom; alt: str | None; filename: str | None`
  - `@dataclass RunStyle: font: str | None; size_pt: float | None; bold: bool | None; rgb: tuple[int,int,int] | None`
  - `@dataclass Element: id: str; slide_index: int (1-based); slide_id: int; shape_id: int; name: str; kind: Literal["title","body","textbox","picture","shape","table","chart","group","other"]; frame: Rect (unrotated, absolute); bbox: Rect (rotated_aabb of frame); z: int; rotation: float; filled: bool; text: str | None; runs: list[RunStyle]; image: ImageInfo | None; placeholder_type: str | None; group_id: str | None`
  - `@dataclass SlideModel: index: int; slide_id: int; hidden: bool; title_text: str | None; elements: list[Element]; skipped_shapes: list[str]`
  - `@dataclass DeckModel: path: Path; slide_w: int; slide_h: int; slides: list[SlideModel]`, with property `slide_rect -> Rect` and method `element(id: str) -> Element`
  - `class DeckError(Exception)` (message is user-facing)
  - `load_deck(path: Path) -> DeckModel`

Behaviour:
- **Kinds:**
  - title placeholders (`TITLE`, `CENTER_TITLE`) → `"title"`; other text placeholders → `"body"`; non-placeholder text boxes → `"textbox"`
  - `MSO_SHAPE_TYPE.PICTURE` → `"picture"`; autoshapes → `"shape"`; tables / charts → `"table"` / `"chart"`; anything else → `"other"`
  - Groups are not emitted as elements. Their children are emitted with `group_id = f"s{slide_id}-sh{group_shape_id}"`.
- **Geometry:**
  - Placeholders use python-pptx's inherited `left/top/width/height`.
  - Group children: transform with each ancestor group's `a:xfrm` as `abs = off + (child − chOff) × ext / chExt`, composed outward for nested groups.
  - A shape whose geometry is still `None` is skipped and its name appended to `skipped_shapes`.
- **Other fields:**
  - `z` = document order across the flattened slide, starting at 0.
  - `rotation` = `shape.rotation`.
  - `filled` = `True` for pictures, and for shapes whose `fill.type` is solid, gradient, pattern or picture. Reading fill may raise for some shape types; treat that as `False`.
  - `hidden` = slide XML attribute `show="0"`.
  - `title_text` = title placeholder text, or `None`.
  - `ImageInfo.px_w/px_h` come from `shape.image.size`, `crop` from `crop_left/top/right/bottom`, `alt` from `cNvPr` `descr` (empty → `None`), and `filename` from `shape.image.filename`.
- **Errors (`DeckError`):**
  - File is not a valid pptx: `"This file could not be opened as a PowerPoint presentation."`
  - More than 100 slides: `"This presentation has more than 100 slides; the limit is 100."`

- [ ] **Step 1: Write the failing tests**

```python
from slideproof.loader import load_deck, DeckError
from slideproof.units import inches

def test_demo_deck_basic_model(demo_deck):
    d = load_deck(demo_deck[0])
    assert (d.slide_w, d.slide_h) == (12192000, 6858000) and len(d.slides) == 8
    agenda = next(e for e in d.slides[1].elements if e.name == "agenda-box")
    assert agenda.kind == "textbox" and agenda.frame.x == inches(10.13)
    assert agenda.id == f"s{d.slides[1].slide_id}-sh{agenda.shape_id}"

def test_picture_info_and_alt(demo_deck):
    d = load_deck(demo_deck[0])
    photo = next(e for e in d.slides[3].elements if e.name == "team-photo")
    assert photo.kind == "picture" and photo.filled
    assert (photo.image.px_w, photo.image.px_h) == (800, 600)
    assert photo.image.alt == "Team photo"

def test_title_placeholder_inherits_geometry(demo_deck):
    d = load_deck(demo_deck[0])
    title = next(e for e in d.slides[1].elements if e.kind == "title")
    assert title.frame.w > 0 and d.slides[1].title_text == "Agenda"

def test_background_is_lowest_z(demo_deck):
    s8 = load_deck(demo_deck[0]).slides[7]
    assert min(s8.elements, key=lambda e: e.z).name == "background"

def test_rotated_shape_bbox(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "textbox", "name": "r", "x": 1, "y": 1, "w": 4, "h": 2, "text": "x", "rotation": 90}]))
    e = d.slides[0].elements[0]
    assert e.rotation == 90 and (e.bbox.w, e.bbox.h) == (e.frame.h, e.frame.w)

def test_group_children_absolute_coordinates(tmp_path):
    # build: group at (2in,1in) containing a 1in box at child (0,0); chOff=(0,0), chExt=ext
    ...  # assert child frame.x == inches(2) and child.group_id startswith "s"

def test_shape_without_geometry_is_skipped(tmp_path):
    # build a slide with a connector or graphicFrame whose xfrm is removed via lxml
    ...  # assert load succeeds, name in skipped_shapes, not in elements

def test_more_than_100_slides_rejected(tmp_path):
    # build a deck with 101 blank slides via python-pptx
    ...  # pytest.raises(DeckError, match="more than 100 slides")

def test_not_a_pptx(tmp_path):
    p = tmp_path / "x.pptx"; p.write_bytes(b"not a zip")
    import pytest
    with pytest.raises(DeckError, match="could not be opened"):
        load_deck(p)
```

For the two `...` tests, the implementer builds the slide inline with python-pptx (`slide.shapes.add_group_shape()`) or lxml, with the assertions as stated in the comment.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_loader.py -v`
Expected: FAIL (`ModuleNotFoundError: slideproof.loader`)

- [ ] **Step 3: Implement `model.py` and `loader.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_loader.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add slideproof/model.py slideproof/loader.py tests/test_loader.py
git commit -m "feat: presentation model loader with groups, rotation, placeholders"
```

---

### Task 5: Findings, fix geometry, and checks C1 + C4

**Files:**
- Create: `slideproof/findings.py`, `slideproof/fixes/geometry.py`, `slideproof/checks/__init__.py`, `offslide.py`, `distortion.py`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `DeckModel`, `Element` (Task 4); `RenderResult` (Task 3, accepted but unused by C1/C4 in M1)
- Produces:
  - `@dataclass(frozen=True) class Fix: kind: str ("F1".."F7"); safety: Literal["safe","confirm"]; element_id: str; params: dict` with property `fix_id -> f"{kind}:{element_id}"`. For F1/F2, `params = {"frame": [x, y, w, h], "scaled": bool}`.
  - `@dataclass class Finding: check_id: str; slide_index: int; slide_id: int; element_ids: tuple[str, ...]; severity: str; confidence: str; magnitude: float; measurements: dict; fix: Fix | None`, with properties `key -> (check_id, slide_id, element_ids)` and `id -> f"{check_id}-{slide_id}-{'-'.join(element_ids)}"` (safe as an HTML id)
  - `pull_on_slide(frame: Rect, bbox: Rect, slide: Rect, rotated: bool, margin: int = inches(0.2)) -> tuple[Rect, bool] | None`. Returns the new frame and whether it was scaled. Returns `None` if `rotated` and scaling would be needed.
  - `restore_proportions(frame: Rect, native_aspect: float) -> Rect`
  - `CHECKS: list[Callable[[DeckModel, RenderResult | None], list[Finding]]]`; `run_checks(deck, render) -> list[Finding]`
  - `check_offslide(deck, render)`; `check_distortion(deck, render)`

**C1 rules (§7.1, §7.2):**
- `outside = 1 − area(bbox ∩ slide) / area(bbox)`.
- Skip if `outside ≤ 0.02`, or if `outside == 1.0` (entirely off-slide belongs to C10 in M2).
- **Background exemption:** skip a picture with `area(bbox ∩ slide) ≥ 0.9 × slide area` that has the lowest `z` on its slide.
- **Decorative bleed:** for elements with no text whose kind is picture or shape, skip if visible fraction ≥ 0.5; otherwise severity `minor`.
- **Severity:** otherwise `visible` if `outside ≥ 0.10`, else `minor`.
- `confidence = "definite"`, `magnitude = outside`.
- `measurements = {"outside": outside, "edges": {"left"|"right"|"top"|"bottom": fraction of element width/height beyond that edge}}`, only edges that are exceeded.
- **Fix:** F1 `safe` from `pull_on_slide`. If the element has a `group_id`, or `pull_on_slide` returns `None`, set `fix = None`.

**`pull_on_slide` algorithm:**
- Inner area = slide inset by `margin` on every side.
- If `bbox` is larger than the inner area: scale `frame` about its centre by `s = min(inner.w / bbox.w, inner.h / bbox.h)`, keeping proportions, and set `scaled = True`.
- Then translate by the minimal (dx, dy) that puts the (scaled) bbox inside the inner area. The frame moves by the same delta as the bbox.

**C4 rules:**
- Pictures only.
- `native_aspect = (px_w × (1 − cl − cr)) / (px_h × (1 − ct − cb))`; `displayed = frame.w / frame.h`; `ratio = displayed / native_aspect`; `dev = |ratio − 1|`.
- Flag when `dev > 0.05`: severity `visible` if `dev > 0.15`, else `minor`; `confidence = "definite"`; `magnitude = min(dev, 1.0)`.
- `measurements = {"ratio": ratio, "direction": "wide" if ratio > 1 else "tall"}`.
- **Fix:** F2 `safe`. Frame = `restore_proportions(frame, native_aspect)`; if its rotated bbox leaves the slide, pass it through `pull_on_slide` and store the final frame. `fix = None` for grouped elements.

**`restore_proportions` algorithm:** keep the centre and the larger of `w`/`h`; recompute the other from `native_aspect`.

- [ ] **Step 1: Write the failing tests**

```python
from tests.groundtruth import load_expected, match
from slideproof.loader import load_deck
from slideproof.checks import run_checks
from slideproof.fixes.geometry import pull_on_slide, restore_proportions
from slideproof.units import Rect, inches

SLIDE = Rect(0, 0, 12192000, 6858000)

def test_demo_deck_c1_c4_match_ground_truth(demo_deck):
    deck = load_deck(demo_deck[0])
    found = [f for f in run_checks(deck, None) if f.check_id in {"C1", "C4"}]
    tp, fp, missed = match(found, deck, load_expected(demo_deck[1], {"C1", "C4"}))
    assert (len(fp), len(missed)) == (0, 0) and len(tp) == 2

def test_c1_agenda_box_measurements(demo_deck):
    deck = load_deck(demo_deck[0])
    f = next(f for f in run_checks(deck, None) if f.check_id == "C1")
    assert f.severity == "visible" and abs(f.measurements["edges"]["right"] - 0.20) < 0.02
    assert f.fix.kind == "F1" and f.fix.safety == "safe"

def test_c1_on_4_3_slide(tiny_deck):
    deck = load_deck(tiny_deck([{"kind": "textbox", "name": "b", "x": 8, "y": 1, "w": 4, "h": 1, "text": "hi"}],
                               slide_w=inches(10), slide_h=inches(7.5)))
    f = run_checks(deck, None)[0]
    assert f.check_id == "C1" and abs(f.measurements["outside"] - 0.5) < 0.01

def test_c1_ignores_full_bleed_background(demo_deck):
    deck = load_deck(demo_deck[0])
    assert not [f for f in run_checks(deck, None) if f.slide_index == 8 and f.check_id == "C1"]

def test_c4_logo_not_flagged_and_photo_ratio(demo_deck):
    deck = load_deck(demo_deck[0])
    c4 = [f for f in run_checks(deck, None) if f.check_id == "C4"]
    assert len(c4) == 1 and round(c4[0].measurements["ratio"], 1) == 1.6
    assert c4[0].measurements["direction"] == "wide"

def test_pull_on_slide_translates_with_margin():
    new, scaled = pull_on_slide(Rect(inches(10.13), inches(1.5), inches(4), inches(3)),
                                Rect(inches(10.13), inches(1.5), inches(4), inches(3)), SLIDE, rotated=False)
    assert not scaled and new.right == SLIDE.w - inches(0.2) and new.w == inches(4)

def test_pull_on_slide_scales_oversized():
    big = Rect(0, 0, inches(20), inches(5))
    new, scaled = pull_on_slide(big, big, SLIDE, rotated=False)
    assert scaled and new.w == SLIDE.w - 2 * inches(0.2) and abs(new.w / new.h - 4.0) < 0.01

def test_pull_on_slide_rotated_needing_scale_returns_none():
    big = Rect(0, 0, inches(20), inches(5))
    assert pull_on_slide(big, big, SLIDE, rotated=True) is None

def test_restore_proportions_keeps_centre_and_larger_side():
    r = restore_proportions(Rect(0, 0, 1600, 600), 800 / 600)
    assert r.w == 1600 and r.h == 1200 and r.center == (800, 300)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_checks.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement findings, geometry and the two checks; register them in `CHECKS`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_checks.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add slideproof/findings.py slideproof/fixes/geometry.py slideproof/checks tests/test_checks.py
git commit -m "feat: off-slide (C1) and distortion (C4) checks with fix geometry"
```

---

### Task 6: Prioritiser and describer

**Files:**
- Create: `slideproof/prioritise.py`, `slideproof/describe/__init__.py`, `spatial.py`, `names.py`
- Modify: `tests/conftest.py`: add fixture `make_finding() -> Callable[[str, int, str, str, float], Finding]` building a `Finding(check_id, slide_index, slide_id=slide_index, element_ids=(eid,), severity, "definite", magnitude, {}, fix=None)`
- Test: `tests/test_prioritise.py`, `tests/test_describe.py`

**Interfaces:**
- Consumes: `Finding`, `Fix` (Task 5); `DeckModel`, `Element` (Task 4)
- Produces:
  - `@dataclass Report: visible: list[Finding]; minor: list[Finding]; slides_checked: int; slides_with_visible: int`
  - `prioritise(findings: list[Finding], slides_checked: int) -> Report`:
    - Score = `{"visible": 2, "minor": 1}[severity] × magnitude × {"definite": 1.0, "likely": 0.7}[confidence]`, sorted by score descending, then by `slide_index`.
    - Grouping: more than 5 findings with the same `check_id` on the same slide become one finding with `element_ids` = their union (sorted), `magnitude` = max, `severity` = worst, `fix = None`, `measurements = {"grouped": count}`.
  - `grid_location(rect: Rect, slide: Rect) -> str`:
    - If `rect.w ≥ 0.9·slide.w and rect.h ≥ 0.9·slide.h` → `"covering the whole slide"`.
    - Else if `rect.w ≥ 0.9·slide.w` → `"across the whole {top|middle|bottom} of the slide"`.
    - Else if `rect.h ≥ 0.9·slide.h` → `"down the whole {left|centre|right} side of the slide"`.
    - Else `"in the {cell}"`, where cell ∈ `top left, top centre, top right, middle left, centre, middle right, bottom left, bottom centre, bottom right`, using thirds of the slide and the rect's centre.
  - `coverage_phrase(f: float) -> str`: the spec's coverage words (Global Constraints). Boundaries: `<0.15`, `<0.30`, `<0.40`, `<0.60`, `≤0.90`, else "all of".
  - `portion_phrase(f: float) -> str`: `<0.15` "a little", `<0.25` "about a fifth", `<0.30` "about a quarter", `<0.40` "about a third", `<0.60` "about half", `≤0.90` "most", else "almost all".
  - `element_label(el: Element, slide: SlideModel) -> str` (lower case; the describer capitalises at sentence start):
    - title → `"the title"`
    - text kinds → `f'text box "{first 6 words}…"'` (no ellipsis if 6 words or fewer)
    - picture → `f'picture "{alt or filename}"'`; if neither exists, `f"picture {k}"` where k is its 1-based order among the slide's pictures
    - shape with text → `f'shape "{first 6 words}…"'`; without text → `f"shape {k}"`
    - table → `"table"`, chart → `"chart"`, other → `"object"`
  - `@dataclass Description: headline: str; short: str; full: str; fix_label: str | None; change_log: str | None`
  - `describe(finding: Finding, deck: DeckModel) -> Description`

**Exact copy** (`{n}` = slide index; `{Label}` = label with first letter upper-cased; `{loc}` = `grid_location(bbox)`; a hidden slide appends `" (hidden slide)"` after `Slide {n}` in `short` only):

| Check | headline | full |
|---|---|---|
| C1 | `{label} sticks out past the {edges} edge` (plural "edges" when there's more than one, joined with " and ") | `{Label}, {loc}, sticks out past the {edges} edge of the slide by {portion} of its {width\|height}. Part of it will be cut off when presented. Confidence: definite.` (`portion` uses the largest exceeded edge; width for left/right, height for top/bottom) |
| C4 | `{label} is stretched {wider\|taller} than its natural shape` | `{Label}, {loc}, is shown {r:.1f} times as {wide\|tall} as its natural shape, so it looks distorted. Confidence: definite.` (for tall, `r = 1/ratio`) |
| C1 grouped | `{count} objects stick out past the slide edges` | `{count} objects on this slide stick out past the slide edges. Confidence: definite.` |
| C4 grouped | `{count} pictures are stretched out of shape` | `{count} pictures on this slide are stretched out of shape. Confidence: definite.` |

- `short` = `f"Slide {n}: {headline}"`.
- **fix_label:**
  - F1: `"Move it back onto the slide. Safe fix."`, or `"Move it back onto the slide and shrink it to fit. Safe fix."` when scaled
  - F2: `"Restore its natural shape, keeping it centred. Safe fix."`
  - No fix: `None`
- **change_log:**
  - F1: `"Slide {n}: {label} moved back onto the slide."` (`" and shrunk to fit"` inserted before the period when scaled)
  - F2: `"Slide {n}: {label} restored to its natural shape; it is now {change} and still centred."`, where `{change}` compares the fix's new frame with the element's current frame: width changed → "narrower" or "wider"; otherwise height changed → "taller" or "shorter". (`restore_proportions` keeps the larger side, so the demo's wide photo becomes taller.)

- [ ] **Step 1: Write the failing tests**

```python
from slideproof.describe.spatial import grid_location, coverage_phrase, portion_phrase
from slideproof.describe import describe
from slideproof.prioritise import prioritise
from slideproof.units import Rect

S = Rect(0, 0, 900, 900)

def test_grid_cells_and_extent():
    assert grid_location(Rect(0, 0, 100, 100), S) == "in the top left"
    assert grid_location(Rect(400, 400, 100, 100), S) == "in the centre"
    assert grid_location(Rect(0, 0, 900, 100), S) == "across the whole top of the slide"
    assert grid_location(Rect(0, 0, 900, 900), S) == "covering the whole slide"

def test_phrases():
    assert coverage_phrase(0.35) == "about a third of" and coverage_phrase(0.95) == "all of"
    assert portion_phrase(0.20) == "about a fifth" and portion_phrase(0.5) == "about half"

def test_c1_description_demo(demo_deck):
    ...  # load, run_checks, take C1 finding, d = describe(f, deck)
    # assert d.short == 'Slide 2: text box "<first 6 words of agenda text>…" sticks out past the right edge'
    # assert "by about a fifth of its width" in d.full and "agenda-box" not in d.full
    # assert d.fix_label == "Move it back onto the slide. Safe fix."

def test_c4_description_demo(demo_deck):
    ...  # assert d.headline == 'picture "Team photo" is stretched wider than its natural shape'
    # assert "1.6 times as wide" in d.full
    # assert d.change_log.endswith("it is now taller and still centred.")

def test_short_form_under_90_chars_for_demo(demo_deck):
    ...  # every Description.short for C1/C4 on the demo deck has len <= 90

def test_prioritise_orders_by_score_and_groups(make_finding):
    # make_finding(check, slide, eid, severity, magnitude) helper fixture in conftest
    fs = [make_finding("C1", 2, f"e{i}", "visible", 0.3) for i in range(6)] + [make_finding("C4", 1, "x", "minor", 0.9)]
    r = prioritise(fs, slides_checked=3)
    assert len(r.visible) == 1 and r.visible[0].measurements == {"grouped": 6} and r.visible[0].fix is None
    assert [f.check_id for f in r.minor] == ["C4"] and r.slides_with_visible == 1
```

The implementer writes the `...` tests to the assertions in their comments. The agenda text is defined in Task 2's generator, so the expected string is known.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_describe.py tests/test_prioritise.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement the prioritiser and the describer modules**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_describe.py tests/test_prioritise.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add slideproof/prioritise.py slideproof/describe tests
git commit -m "feat: prioritiser and spatial-language describer"
```

---

### Task 7: Fix writer and apply_fixes

**Files:**
- Create: `slideproof/fixes/__init__.py`, `slideproof/fixes/writer.py`
- Test: `tests/test_fixes.py`

**Interfaces:**
- Consumes: `Fix` (Task 5), `Rect`
- Produces:
  - `FIX_ORDER = ["F4", "F5", "F3", "F2", "F1", "F7", "F6"]`
  - `set_frame(prs: Presentation, slide_id: int, shape_id: int, frame: Rect) -> None`: finds the shape with `prs.slides.get(slide_id)` and `shape.shape_id`, then sets `left/top/width/height`. On a placeholder this writes an explicit `xfrm` override. It raises `KeyError` if the shape isn't found.
  - `apply_fixes(src: Path, dst: Path, fixes: list[Fix]) -> list[Fix]`: copies `src` to `dst`, applies the fixes in `FIX_ORDER` (F1/F2 → `set_frame` with `params["frame"]`), saves, and returns the fixes in the order applied. It raises `ValueError` if `dst == src`. In M1 only F1 and F2 exist; any other kind raises `NotImplementedError`.

- [ ] **Step 1: Write the failing tests**

```python
def test_apply_f1_f2_to_copy(demo_deck, tmp_path):
    # load deck, run_checks, collect the two fixes; out = tmp_path / "demo (checked).pptx"
    # applied = apply_fixes(demo_deck[0], out, fixes)
    # assert [f.kind for f in applied] == ["F2", "F1"]           # FIX_ORDER respected
    # reloaded = load_deck(out): agenda-box.frame == Rect.from_list(F1 params["frame"])
    # team-photo frame aspect within 1% of 800/600
    # original file bytes unchanged (compare sha256 before/after)
    ...

def test_apply_refuses_to_overwrite_original(demo_deck):
    import pytest
    with pytest.raises(ValueError):
        apply_fixes(demo_deck[0], demo_deck[0], [])

def test_set_frame_on_inherited_placeholder(demo_deck, tmp_path):
    # move slide 2's title via set_frame; save; reload; title frame equals the new Rect
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fixes.py -v`
Expected: FAIL (`ImportError: apply_fixes`)

- [ ] **Step 3: Implement `writer.py` and `apply_fixes`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fixes.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add slideproof/fixes tests/test_fixes.py
git commit -m "feat: apply safe fixes to a copy"
```

---

### Task 8: Analysis orchestration and verification with rollback

**Files:**
- Create: `slideproof/analysis.py`, `slideproof/verify.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: `load_deck`, `render_deck`, `run_checks`, `prioritise`, `apply_fixes`
- Produces:
  - `@dataclass Analysis: deck: DeckModel; render: RenderResult; findings: list[Finding]; report: Report; skipped_note: str | None`
  - `analyse(pptx: Path, run_dir: Path, progress: Callable[[str], None] = lambda m: None) -> Analysis`
    - Progress messages, in order: `"Reading slides…"`, then `"Rendering slides…"`, then for each slide i, `"Checking slide {i} of {n}…"`.
    - `skipped_note`: `None` when render status is `ok`, otherwise `f"Note: text overflow and contrast checks were skipped because {render.reason}."`, with the reason used exactly as written.
  - `@dataclass ExportResult: output: Path | None; applied: list[Fix]; rolled_back: list[tuple[Fix, str]]; resolved: int; new_visible: int; final: Analysis | None`
  - `export_and_verify(original: Analysis, selected: list[Fix], out: Path, run_dir: Path, progress: Callable[[str], None] = ...) -> ExportResult`

**Verification algorithm:**

```
active = list(selected)
for attempt in range(len(selected) + 1):
    if not active: return ExportResult(None, [], rolled_back, 0, 0, None)
    apply_fixes(original.deck.path, out, active)
    after = analyse(out, run_dir / f"verify{attempt}", progress)
    before_keys = {f.key for f in original.findings}
    after_keys = {f.key for f in after.findings}
    bad = []
    for fx in active:
        target = the original finding whose fix.fix_id == fx.fix_id
        if target.key in after_keys: bad.append((fx, "the problem was still there after the fix"))
        elif any(f.severity == "visible" and f.key not in before_keys and fx.element_id in f.element_ids for f in after.findings):
            bad.append((fx, "it caused a new problem"))
    if not bad:
        resolved = len([f for f in original.findings if f.key not in after_keys])
        new_visible = len([f for f in after.findings if f.severity == "visible" and f.key not in before_keys])
        return ExportResult(out, active, rolled_back, resolved, new_visible, after)
    rolled_back += bad; active = [fx for fx in active if fx not in {b[0] for b in bad}]
```

Progress during export: `"Applying fixes…"`, then the analysis messages prefixed with `"Checking the corrected copy: "`.

- [ ] **Step 1: Write the failing tests**

```python
def test_analyse_demo_without_libreoffice(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    msgs = []
    a = analyse(demo_deck[0], tmp_path, msgs.append)
    assert a.render.status == "skipped"
    assert a.skipped_note == "Note: text overflow and contrast checks were skipped because LibreOffice is not installed."
    assert msgs[:2] == ["Reading slides…", "Rendering slides…"] and msgs[-1] == "Checking slide 8 of 8…"
    assert {f.check_id for f in a.report.visible} == {"C1", "C4"}

def test_export_resolves_both_and_introduces_nothing(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    a = analyse(demo_deck[0], tmp_path / "a")
    fixes = [f.fix for f in a.findings if f.fix]
    r = export_and_verify(a, fixes, tmp_path / "demo (checked).pptx", tmp_path / "v")
    assert r.output.exists() and r.resolved == 2 and r.new_visible == 0 and not r.rolled_back

def test_bad_fix_is_rolled_back(monkeypatch, tmp_path, demo_deck):
    # take F1 for agenda-box and replace params["frame"] with a frame still 30% off the slide
    # result: r.rolled_back[0][1] == "the problem was still there after the fix", F2 still applied
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement `analysis.py` and `verify.py`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_analysis.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add slideproof/analysis.py slideproof/verify.py tests/test_analysis.py
git commit -m "feat: analysis pipeline and export verification with rollback"
```

---

### Task 9: Web interface (pages 1–4) and startup

**Files:**
- Create: `slideproof/web/__init__.py`, `app.py`, `runs.py`, `templates/*.html`, `static/progress.js`, `slideproof/__main__.py`
- Modify: `README.md` (setup and start steps from §5.1a)
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `analyse`, `export_and_verify`, `describe`, `Analysis`, `ExportResult`, `find_soffice`
- Produces:
  - `create_app(runs_root: Path) -> FastAPI`
  - `@dataclass Run: id: str; filename: str; dir: Path; state: Literal["working","done","error"]; message: str; next_url: str | None; analysis: Analysis | None; export: ExportResult | None; error: str | None`
  - `class RunStore: create(filename) -> Run; get(run_id) -> Run` (raises `KeyError`); `start(run, fn)` runs `fn` in a daemon thread, with a `threading.Lock` around state changes
  - `startup_check() -> list[str]`: plain-language problems, e.g. `"LibreOffice was not found. Text overflow and contrast checks will be skipped. Install LibreOffice 7.6 or later, or set SOFFICE_PATH."` and `"The Carlito font is not installed; text measurements may be less accurate."`. Font files are looked for in `C:\Windows\Fonts` and `%LOCALAPPDATA%\Microsoft\Windows\Fonts` by file name prefix: `Carlito`, `Caladea`, `LiberationSans`, `LiberationSerif`.

**Routes:**

| Method + path | Behaviour |
|---|---|
| `GET /` | index page; shows `startup_check()` items in a list under `h2 "Before you start"` if any |
| `POST /check` (multipart `file`) | Validate: name ends `.pptx` (case-insensitive) else error page "Save as .pptx and try again."; size ≤ 50 MB else "This file is larger than 50 MB." Save as `<run dir>/original/<filename>`. Start `analyse`. Return 303 → `/runs/{id}/progress` |
| `GET /runs/{id}/progress` | progress page |
| `GET /runs/{id}/status` | JSON `{"state", "message", "next"}` |
| `GET /runs/{id}/report` | report page (Page 3) |
| `POST /runs/{id}/export` (form `fix` repeated = fix_ids) | No fixes selected → result page saying "No fixes were selected, so no copy was made." Otherwise start `export_and_verify` writing `<run dir>/output/<stem> (checked).pptx`, then 303 → progress (next = result) |
| `GET /runs/{id}/result` | result page (Page 4) |
| `GET /runs/{id}/download` | `FileResponse` of the output with `filename="<stem> (checked).pptx"` (RFC 5987 encoding handles non-ASCII) |
| unknown run id | 404 error page "This check has expired. Check the file again." with a link to `/` |

A `DeckError` from analysis sets `state="error"`, and the progress page shows the message in `role="alert"` with a link "Check another file".

**Templates** (all extend `base.html`: `<html lang="en">`, `<main>`, no navigation chrome):
- **index.html:**
  - `<title>Check slide layout – Slide Proof</title>`, `<h1>Check slide layout</h1>`
  - `<p>Your file stays on this computer. Nothing is uploaded to the internet.</p>`
  - `<label for="file">PowerPoint file (.pptx)</label><input id="file" name="file" type="file" accept=".pptx" required>`
  - `<button>Check slides</button>`
- **progress.html:**
  - `<title>Checking {filename} – Slide Proof</title>`, `<h1>Checking {filename}</h1>`
  - `<p role="status" id="status">{message}</p>`
  - `progress.js` polls `/status` every 1.5 s and updates `#status` only when the message changed and ≥ 3 s have passed since the last update. On `done` it does `location.replace(next)`; on `error` it inserts `<p role="alert">` and a link.
  - `<noscript>` link "Show the report when ready".
- **report.html:**
  - Follows §8.2 exactly for M1 parts. Title: `{filename} – {v} visible problem(s) – Slide Proof`.
  - `<h1 tabindex="-1" id="top">Report for {filename}</h1>`, focused on load by a 3-line inline script.
  - Summary sentence:
    - `"{n} slides checked. {v} visible problem(s) on {s} slide(s), {m} minor."` with correct singular and plural forms.
    - When v = 0 and m = 0: `"{n} slides checked. No problems found."`
  - `skipped_note` paragraph if present.
  - `<h2>Visible problems ({v})</h2>` and `<h2>Minor polish ({m})</h2>` (omit an h2 when its count is 0).
  - Per finding: `<section aria-labelledby="{finding.id}">` containing:
    - `<h3 id="{finding.id}">Slide {n}, "{title_text}": {headline}</h3>`; when a slide has no title, `Slide {n}: {headline}`.
    - `<p>{full}</p>`
    - With a fix: `<fieldset><legend>Fix for this problem</legend><input type="checkbox" name="fix" value="{fix_id}" id="fix-{finding.id}" {checked if safe}><label for="fix-{finding.id}">{fix_label}</label></fieldset>`
    - Without one: `<p>No automatic fix for this one.</p>`
  - All findings sit inside one `<form method="post" action="/runs/{id}/export">`.
  - Ends with `<h2>Apply fixes</h2><p>Selected fixes are applied to a copy. Your original file is not changed.</p><button>Create corrected copy</button>`.
- **result.html:**
  - `<h1 tabindex="-1">Corrected copy created</h1>` (focused on load).
  - `<p>{a} fix(es) applied. {resolved} problem(s) resolved. {new_visible} new problem(s).</p>`
  - If any fixes were rolled back: `<h2>Fixes that could not be applied safely</h2><ul><li>Couldn't safely fix: {headline}. Reason: {reason}.</li></ul>`
  - `<h2>Changes made</h2><ul>` with one `change_log` item per applied fix.
  - `<p><a href="/runs/{id}/download">Download {stem} (checked).pptx</a></p><p><a href="/">Check another file</a></p>`.

**`__main__.py`:** prints `startup_check()` items, starts uvicorn with `create_app(Path(tempfile.gettempdir()) / "slideproof")` on `127.0.0.1:8765`, and opens `http://127.0.0.1:8765/` with `webbrowser.open` after 1 s using `threading.Timer`.

- [ ] **Step 1: Write the failing tests** (FastAPI `TestClient`; `SOFFICE_PATH` set to a missing file; a helper `wait_done(client, run_id)` polls `/status` until it isn't `working`, with a 30 s cap)

```python
def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "<h1>Check slide layout</h1>" in r.text and 'lang="en"' in r.text

def test_full_flow_demo_deck(client, demo_deck):
    r = client.post("/check", files={"file": ("demo.pptx", demo_deck[0].read_bytes())}, follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].split("/")[2]
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert "Report for demo.pptx" in rep and "Visible problems (2)" in rep
    assert len(re.findall(r'type="checkbox"[^>]*\schecked', rep)) == 2
    assert "LibreOffice is not installed" in rep
    fixes = re.findall(r'value="(F\d:[^"]+)"', rep)
    r = client.post(f"/runs/{run_id}/export", data={"fix": fixes}, follow_redirects=False)
    wait_done(client, run_id)
    res = client.get(f"/runs/{run_id}/result").text
    assert "2 fixes applied. 2 problems resolved. 0 new problems." in res
    d = client.get(f"/runs/{run_id}/download")
    assert d.status_code == 200
    assert 'filename="demo (checked).pptx"' in d.headers["content-disposition"]

def test_wrong_extension_error(client):
    r = client.post("/check", files={"file": ("old.ppt", b"x")})
    assert r.status_code == 400 and "Save as .pptx and try again." in r.text

def test_corrupt_pptx_shows_error_not_500(client):
    # post b"not a zip" as bad.pptx, wait_done; status state == "error" and message contains "could not be opened"
    ...

def test_too_large_upload(client):
    # post 50 MB + 1 byte named big.pptx → 400 and "larger than 50 MB"
    ...

def test_unicode_filename_roundtrip(client, demo_deck):
    # upload as "Café plan.pptx", full flow; report contains "Report for Café plan.pptx";
    # content-disposition contains "filename*=utf-8''Caf%C3%A9%20plan%20%28checked%29.pptx"
    ...

def test_unknown_run_404(client):
    r = client.get("/runs/nope/report")
    assert r.status_code == 404 and "Check the file again." in r.text

def test_no_fixes_selected(client, demo_deck):
    # full flow up to the report, then POST export with no fix → page contains "No fixes were selected, so no copy was made."
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_web.py -v`
Expected: FAIL (`ModuleNotFoundError: slideproof.web`)

- [ ] **Step 3: Implement runs, app, templates, progress.js, `__main__.py`; update README**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_web.py -v`
Expected: all passed

- [ ] **Step 5: Manual smoke test**

Run: `python -m slideproof`. The browser opens at `http://127.0.0.1:8765/`. Upload the demo deck and confirm the report shows 2 visible problems, then create the corrected copy and download it. Open both decks in PowerPoint and confirm by eye that slide 2's box is back on the slide and slide 4's photo is no longer stretched.

- [ ] **Step 6: Commit**

```bash
git add slideproof/web slideproof/__main__.py README.md tests/test_web.py
git commit -m "feat: screen-reader-first web interface for check, report, export"
```

---

### Task 10: Accessibility verification (M1 exit)

**Files:**
- Create: `tests/test_a11y.py`, `docs/testing/nvda-walkthrough.md`

**Interfaces:**
- Consumes: `create_app` (Task 9)

- [ ] **Step 1: Write the axe test**

Run uvicorn with `create_app` in a background thread on a free port, with `SOFFICE_PATH` set to a missing path for speed. Use Playwright Chromium to:
1. Open `/` and run axe.
2. Upload the demo deck with `set_input_files` and submit.
3. Wait for the URL to end with `/report`.
4. Assert `document.activeElement.id == "top"`.
5. Run axe.
6. Submit the form and wait for `/result`.
7. Run axe.

For each page, assert there are no violations with `impact in {"serious", "critical"}` (using `axe_playwright_python.sync_playwright.Axe().run(page)`).

```python
def test_pages_have_no_serious_axe_violations(live_server, demo_deck): ...
def test_report_focuses_h1_on_load(live_server, demo_deck): ...
def test_report_heading_outline(live_server, demo_deck):
    # headings in order: h1 "Report for demo.pptx", h2 "Visible problems (2)", h3 starting "Slide 2" , h3 starting "Slide 4", h2 "Apply fixes"
    ...
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_a11y.py -v`
Expected: 3 passed (fix any violations in templates before moving on)

- [ ] **Step 3: Write `docs/testing/nvda-walkthrough.md` and perform it**

Checklist, performed with NVDA + Firefox with the monitor off or covered. Record pass or fail and notes for each item:
1. Start `python -m slideproof`; NVDA reads the page title "Check slide layout – Slide Proof".
2. Tab to the file field and hear "PowerPoint file (.pptx)". Choose the demo deck, then activate "Check slides".
3. Hear the status updates no more often than every 3 s, then land on "Report for demo.pptx, heading level 1".
4. Press H: hear the slide 2 finding heading. Press H again: the slide 4 finding heading.
5. Press Insert+F7 (Elements list → Headings): the outline matches the report structure.
6. Tab to each fix checkbox: hear the label including "Safe fix." and "checked".
7. Activate "Create corrected copy"; land on "Corrected copy created". Hear "2 fixes applied. 2 problems resolved. 0 new problems."
8. Navigate the "Changes made" list and activate the download link.
9. Repeat steps 1–8 with NVDA + Chrome.

Exit criterion (§14 M1): every item passes in both browsers.

- [ ] **Step 4: Commit**

```bash
git add tests/test_a11y.py docs/testing/nvda-walkthrough.md
git commit -m "test: axe checks and NVDA walkthrough for M1"
```

---

## After this plan

M1 is done when the full test suite passes (`python -m pytest -v`) and the NVDA walkthrough passes in both browsers. The next plans, written then using M0's timing notes:
- **M2:** C2 (pictures and shapes), C5, C8, C9, C10; estimated text extent; exemptions; F3, F4; slide text map
- **M3:** span linker, content boxes, C2 for text, C3, C6, C7, C11
- **M4:** F5–F7, "Mark as intentional", JAWS
- **M5:** corpus tuning and demo readiness
