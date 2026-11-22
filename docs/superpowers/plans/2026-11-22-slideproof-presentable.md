# Slide Proof "P Presentable" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the prototype presentable to a mixed sighted and blind audience. That means a clean, high-contrast visual design, a one-click demo presentation, and a "How Slide Proof works" page, all without changing what a screen reader hears beyond the new controls.

**Architecture:**
- One small stylesheet served from the existing `/static` mount, linked from `base.html`, plus a footer that links the new page.
- The demo button posts to a new `/demo` route. That route generates the bundled demo deck (the builder moves from `tools/` into the package) and runs it through the same job as an upload.
- The "How it works" page is a server-rendered template fed by `describe/coverage.py`, so its list of checks never drifts from the report's.

**Tech Stack:** existing (FastAPI + Jinja2, plain CSS, pytest, Playwright with Edge, axe).

**Spec:** `docs/superpowers/specs/2026-11-22-intent-model-and-polish-design.md` §6 items 1, 2, 4 and §7 (roadmap); the main spec `docs/superpowers/specs/2026-11-20-slide-layout-checker-design.md` §8.2 (page structure) and §14.

**Base branch:** `ai-design` (93d258c). Work on a new branch `presentable` cut from it.

## Global Constraints

- Screen-reader structure stays as it is: headings, landmarks, form controls and their order. Only the new demo button, the footer and the new page add to it. The transcript tests (`tests/test_transcript.py`) and axe tests (`tests/test_a11y.py`) are the guard; the transcript diffs may only add those items.
- Contrast meets WCAG AA (axe `color-contrast` passes in light and dark mode). Focus is always visible. No meaning is carried by colour alone.
- Plain CSS, one file, no framework, no web fonts, no external requests (the files stay on this computer).
- Base font 18 px; reading width at most 46 rem; dark mode via `prefers-color-scheme: dark`.
- Exact copy:
  - **Demo button:** "Try the demo presentation"
  - **Footer link:** "How Slide Proof works"
  - **Page:** `<title>How Slide Proof works – Slide Proof</title>`, `<h1>How Slide Proof works</h1>`

## Review Focus

1. **Pressing "Try the demo presentation" twice quickly, or on a fresh install with no demo deck yet:** each press starts its own run and never fails because of a missing or half-written file. → test in Task 2.
2. **Dark mode:** axe contrast must pass with `prefers-color-scheme: dark` emulated, not only in light mode. → test in Task 1.
3. **The footer link on every page, including the error page and the progress page,** so a screen-reader user can always reach the explanation. → test in Task 1.
4. **The demo deck CLI** (`python tools/make_demo_deck.py <dir>`) and the test fixture still work after the builder moves into the package. → test in Task 2.
5. **Keyboard focus is visible on every control** (buttons, links, checkboxes, summaries) in both colour schemes. → test in Task 1.

---

## File Structure

```
slideproof/
  demo_deck.py                 (moved from tools/make_demo_deck.py: build_demo_deck())
  web/
    static/style.css           (new)
    templates/base.html        stylesheet link + footer
    templates/index.html       demo button form
    templates/about.html       (new)
    app.py                     POST /demo, GET /about
tools/make_demo_deck.py        thin CLI wrapper around slideproof.demo_deck
tests/test_presentable.py      (new)
tests/test_a11y.py             dark-mode and focus checks, about page in axe pass
tests/transcripts/*.txt        regenerated (only additions)
docs/superpowers/specs/...     roadmap rows (main spec §14), design status
```

---

### Task 1: Stylesheet, footer and visible focus

**Files:**
- Create: `slideproof/web/static/style.css`
- Modify: `slideproof/web/templates/base.html`
- Test: `tests/test_presentable.py`, `tests/test_a11y.py`

**Interfaces:**
- Produces:
  - `base.html` links `/static/style.css`;
  - `base.html` ends with `<footer><p><a href="/about">How Slide Proof works</a></p></footer>` after `</main>`. The `/about` route arrives in Task 3; this link may 404 until then.

**The stylesheet decides:**
- CSS custom properties for light and dark colours; base font 18 px with a system font stack; `main` max-width 46 rem, centred.
- Each `section` (finding) styled as a card: border, padding, radius.
- Buttons styled with a minimum height of 44 px.
- `:focus-visible` outline 3 px solid in an accent colour, offset 2 px, on all interactive elements and `summary`.
- `details > summary` uses `cursor: pointer`.
- The progress `role=status` paragraph is styled; no animation.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_presentable.py
def test_pages_link_stylesheet_and_footer(client, demo_deck):   # client/upload/wait_done from test_web helpers
    for html in (client.get("/").text,
                 client.get("/runs/nope/report").text):                   # error page
        assert '<link rel="stylesheet" href="/static/style.css">' in html
        assert '<footer><p><a href="/about">How Slide Proof works</a></p></footer>' in html
    # progress page also has it: upload demo, fetch /runs/{id}/progress, same assertions

def test_stylesheet_served(client):
    r = client.get("/static/style.css")
    assert r.status_code == 200 and "prefers-color-scheme: dark" in r.text and ":focus-visible" in r.text
```

```python
# tests/test_a11y.py (add)
def test_report_contrast_dark_mode(live_server, demo_deck, page):
    page.emulate_media(color_scheme="dark")
    reach_report(page, live_server, demo_deck[0])
    assert_no_serious(page, "report (dark)")

def test_focus_outline_visible(live_server, page):
    page.goto(live_server + "/")
    page.keyboard.press("Tab")
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    assert outline not in ("none", "")
```

Move the shared `client`, `upload` and `wait_done` helpers from `tests/test_web.py` into `tests/conftest.py`, so `test_presentable.py` can use them. `assert_no_serious` and `reach_report` already exist in `test_a11y.py`.

- [ ] **Step 2: Run** `python -m pytest tests/test_presentable.py tests/test_a11y.py -v`. Expected: the new tests FAIL (no stylesheet, no footer, no outline).
- [ ] **Step 3: Implement** `style.css` and the `base.html` changes.
- [ ] **Step 4: Regenerate transcripts** with `UPDATE_TRANSCRIPTS=1 python -m pytest tests/test_transcript.py`. Read the diff: it may only add the footer link line (`link: How Slide Proof works`) to each page.
- [ ] **Step 5: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat: presentable stylesheet, footer link, visible focus and dark mode`.

---

### Task 2: "Try the demo presentation"

**Files:**
- Create: `slideproof/demo_deck.py` (move the body of `tools/make_demo_deck.py`)
- Modify: `tools/make_demo_deck.py` (now a thin CLI: `from slideproof.demo_deck import build_demo_deck`, same `argv[1]` usage and output), `tests/conftest.py` (import from `slideproof.demo_deck`), `slideproof/web/app.py`, `slideproof/web/templates/index.html`
- Test: `tests/test_presentable.py`, `tests/test_demo_deck.py`

**Interfaces:**
- Produces:
  - `slideproof.demo_deck.build_demo_deck(out_dir: Path) -> tuple[Path, Path]`, unchanged signature.
  - `POST /demo`: creates a run named `demo_deck.pptx` and builds the deck **directly into that run's `original/` folder**. A per-run build means two quick presses never share a half-written file. It starts the same analysis job as `/check` and returns a 303 redirect to `/runs/{id}/progress`. If building fails, it returns the error page (400) with "The demo presentation could not be created." The `/check` job body becomes a shared helper, `_start_analysis(run, path)`, used by both routes.
- `index.html`: after the upload form, a second form `<form method="post" action="/demo"><button>Try the demo presentation</button></form>`, introduced by `<h2>No file to hand?</h2>`.

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_button_runs_demo(client):
    r = client.post("/demo", follow_redirects=False)
    assert r.status_code == 303
    run_id = r.headers["location"].split("/")[2]
    wait_done(client, run_id)
    rep = client.get(f"/runs/{run_id}/report").text
    assert "Report for demo_deck.pptx" in rep and "Visible problems (5)" in rep

def test_demo_button_twice_gives_two_runs(client):
    a = client.post("/demo", follow_redirects=False).headers["location"]
    b = client.post("/demo", follow_redirects=False).headers["location"]
    assert a != b
    for loc in (a, b):
        wait_done(client, loc.split("/")[2])
        assert "Report for demo_deck.pptx" in client.get(loc.replace("progress", "report")).text

def test_demo_build_failure_shows_error(client, monkeypatch):
    import slideproof.web.app as app_mod
    monkeypatch.setattr(app_mod, "build_demo_deck", lambda d: (_ for _ in ()).throw(OSError("disk")))
    r = client.post("/demo")
    assert r.status_code == 400 and "The demo presentation could not be created." in r.text

def test_index_has_demo_button(client):
    assert '<button>Try the demo presentation</button>' in client.get("/").text

# tests/test_demo_deck.py (add)
def test_cli_wrapper_still_builds(tmp_path):
    import subprocess, sys
    subprocess.run([sys.executable, "tools/make_demo_deck.py", str(tmp_path)], check=True)
    assert (tmp_path / "demo_deck.pptx").exists() and (tmp_path / "expected_findings.json").exists()
```

- [ ] **Step 2: Run.** Expected: FAIL (404 on `/demo`, no button).
- [ ] **Step 3: Implement** the move, the wrapper, the route and the button. Make sure the deck builder imports nothing from `tests/`.
- [ ] **Step 4: Regenerate transcripts.** The index transcript may only add `heading level 2: No file to hand?` and `button: Try the demo presentation`.
- [ ] **Step 5: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat: one-click demo presentation`.

---

### Task 3: "How Slide Proof works" page

**Files:**
- Create: `slideproof/web/templates/about.html`
- Modify: `slideproof/web/app.py` (`GET /about`), `slideproof/describe/coverage.py` (only if a helper is needed to expose the lists)
- Test: `tests/test_presentable.py`, `tests/test_a11y.py`, `tests/test_transcript.py` (new golden `about.txt`)

**Interfaces:**
- Consumes: `CHECKS_RUN` and `NOT_CHECKED_YET` from `slideproof.describe.coverage`.
- Produces: `GET /about` → `about.html`, structured as below. The AI track will later add two sections, "What 'Probably intentional' means" and "How accurate the model is", between the second and third h2.

```
<title>How Slide Proof works – Slide Proof</title>
h1  How Slide Proof works
p   Slide Proof checks how your slides will look to a sighted audience and tells you, in words,
    what a sighted person would notice. It can also fix some problems for you, on a copy.
h2  What it checks
ul  one <li> per CHECKS_RUN item, first letter capitalised
p   Not checked yet: {NOT_CHECKED_YET joined with commas and "and"}.
h2  How fixes work
p   Fixes are only applied to a copy of your file, never the original. After fixing, Slide Proof
    checks the copy again and undoes any fix that did not work or caused a new problem.
h2  Your privacy
p   Your file stays on this computer. Nothing is uploaded to the internet, and files from earlier
    sessions are deleted each time Slide Proof starts.
h2  What it cannot do yet
ul  It does not check text overflow, contrast or text size yet.
    It does not look inside charts and diagrams.
    Its judgement of overlap uses an estimate of where text sits; a later version will use the
    rendered slide.
p   <a href="/">Check a presentation</a>
```

- [ ] **Step 1: Write the failing tests**

```python
def test_about_page(client):
    html = client.get("/about").text
    assert "<title>How Slide Proof works – Slide Proof</title>" in html
    assert "<h1>How Slide Proof works</h1>" in html
    for h2 in ("What it checks", "How fixes work", "Your privacy", "What it cannot do yet"):
        assert f"<h2>{h2}</h2>" in html
    assert "<li>Overlapping objects</li>" in html
    assert "Not checked yet: text overflow, contrast and text size." in html
```

Add `/about` to the axe pass in `test_a11y.py` (light and dark), and add an `about.txt` golden transcript in `test_transcript.py`, generated with `UPDATE_TRANSCRIPTS=1` and read before committing.

- [ ] **Step 2: Run.** Expected: FAIL (404).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: How Slide Proof works page`.

---

### Task 4: Roadmap and docs

**Files:**
- Modify:
  - main spec §14: insert rows **P Presentable** (✅ when merged) and **AI Intent model** between M2 and M3, copied from the design §7;
  - design doc status → "Approved 2026-11-22";
  - `docs/testing/nvda-walkthrough.md`: add one step, "Activate 'Try the demo presentation' (instead of choosing a file) → lands on the progress page", and note the footer link.

- [ ] **Step 1: Edit the docs.**
- [ ] **Step 2: Run** `python -m pytest -q`. Expected: all pass (docs only).
- [ ] **Step 3: Commit** `docs: roadmap gains Presentable and AI milestones; walkthrough covers demo button`.

**After the plan (controller):** run `tools/nvda_pass.py` once using the demo button flow, take two screenshots (light and dark report page) for the presentation, then push the branch.
