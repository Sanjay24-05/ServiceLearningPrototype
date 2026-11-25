# Faculty Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything needed to present Slide Proof live in 10 minutes, with a backup recording.

**Architecture:** Two small deck builders (logo deck, talk deck) with tests; a recorder that screenshots a real NVDA run and encodes a captioned WebM inside Edge with MediaRecorder; the rest is documentation.

**Tech Stack:** Python 3.12 venv, python-pptx 1.0.2, Pillow, Playwright (channel="msedge"), NVDA.

**Spec:** docs/superpowers/specs/2026-11-24-presentation-design.md

## Global Constraints

- No new dependencies or installs; never disable TLS verification.
- Do not change `slideproof/`, the demo deck, its answer key or the model.
- Model numbers, verbatim: 97.6% of planted mistakes kept in the main lists; 94.3% of deliberate designs recognised; 120 synthetic decks; threshold 80%; grouped 5-fold on decks the model never saw; threshold and family chosen on those same predictions, so mildly optimistic.
- Always say: "No blind user has tested it yet."
- Never demonstrate: Mark as intentional, F5, F6, F7, the Yellow Idea half-donut.
- Commit by explicit path, on green.

## Review Focus

1. NVDA not running or log missing: the recorder exits with a one-line message, not a traceback. → Task 3
2. LibreOffice cold start (a first run took 48 s, a warm one 12 s): the script has a warm-up step. → Task 4
3. Logo deck without rendering: logos still move, photo stays. → Task 1
4. Low-resolution projector: talk-deck text is never below 24 pt. → Task 2
5. Live demo fails midway: each script section names its fallback file. → Task 4

### Task 1: School-logo deck

**Files:** Create `tools/make_logo_deck.py`, `docs/presentation/school_logo_deck.pptx`. Test: `tests/test_presentation_decks.py`.

**Interfaces:** Produces `build_logo_deck(out: Path) -> Path` (writes exactly `out`). Uses `add_picture`, `SLIDE_W`, `SLIDE_H`, `_layout` from `slideproof.demo_deck`.

**Content:** six "Title Only" slides titled Welcome, Our school, Our clubs, Class trip, Volunteering, Thank you. Each has `school-logo` at (-0.5, -0.5) in, 1.6 × 1.6 in, alt "School logo". Slide 4 also has `trip-photo` at (11.2, 3.0) in, 4.0 × 2.67 in, alt "Class trip photo".

- [ ] **Step 1: Failing test**, parametrised over no rendering and (soffice-marked) rendering:

```python
assert sorted(f.slide_index for f in report.intentional) == [1, 2, 3, 4, 5, 6]
assert [(f.check_id, f.slide_index) for f in report.visible] == [("C1", 4)]
```

- [ ] **Step 2:** Run it. Expected: import error.
- [ ] **Step 3:** Implement; save the deck to `docs/presentation/`.
- [ ] **Step 4:** Run. Expected: pass. If a logo picture trips C4 or C5, change the picture's pixels, not the checks.
- [ ] **Step 5:** Commit `feat: school-logo deck for the AI part of the demo`.

### Task 2: Six-slide talk deck

**Files:** Create `tools/make_talk_deck.py`, `docs/presentation/demo-slide-3.png`, `docs/presentation/slide_proof_talk.pptx`. Test: `tests/test_presentation_decks.py`.

**Interfaces:** Produces `build_talk_deck(out: Path) -> Path`.

**Slides:**
1. "Slide Proof": "Checking slide layouts without sight"
2. "It sounds fine. It isn't.": picture of demo slide 3 rendered
3. "Who it is for": blind presenters using NVDA or JAWS; check your own slides, alone, before you present; files stay on your computer
4. "Mistake or on purpose?": a small on-device model, 21 features, never hides anything, explains its reason
5. "What we measured": 97.6% and 94.3% with their meanings; "120 synthetic decks, each tested while held out; mildly optimistic"; "Untested on real-world decks. No blind user has tested it yet."
6. "What comes next": remaining fixes, JAWS, testing with blind users; "Can you introduce us to testers?"

- [ ] **Step 1: Failing tests:** 6 slides with those exact titles; every run ≥ 24 pt; every picture has alt text; every slide has speaker notes; (soffice) `analyse(...)` gives `report.visible == [] and report.minor == []`.
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Implement. Slide 2's picture is `demo-slide-3.png`, rendered once from the demo deck with `render_deck` and committed.
- [ ] **Step 4:** Run. Expected: pass. Look at every rendered slide.
- [ ] **Step 5:** Commit `feat: six-slide talk deck`.

### Task 3: Captioned backup recording

**Files:** Create `tools/nvda_log.py`, `tools/record_demo.py`, `docs/presentation/backup-demo.webm`. Modify `tools/nvda_pass.py` (import `spoken`). Test: `tests/test_nvda_log.py`.

**Interfaces:**
- `spoken(text: str) -> list[str]` in `nvda_log.py`: the parsing part of `nvda_pass.py`'s `spoken(start)`; each script keeps its own file reading.
- `record_demo.py <nvda log> <out.webm>`: visible Edge. Demo deck via the "Try the demo presentation" button, through the result and opened before/after, then `school_logo_deck.pptx` to its "Probably intentional" section. One frame per step: a page screenshot plus that step's `spoken()` lines as a caption band. Each frame shows `max(4, 0.35 × caption words)` seconds. Frames are drawn to a 1280×720 canvas and encoded in Edge with `canvas.captureStream()` and `MediaRecorder("video/webm")`.

- [ ] **Step 1: Failing tests:** `spoken()` on a sample log with single- and double-quoted parts drops `en_US` and joins with ` | `; a missing log exits with code 2 and prints `NVDA log not found: <path>. Start NVDA with logging first (see tools/nvda_pass.py).`
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tests pass. Run against real NVDA (tell the user first; it speaks aloud; quit with `nvda.exe -q` and confirm the process is gone). Play the WebM in Edge and look at frames: captions match the log, and no personal data shows.
- [ ] **Step 5:** Commit `feat: captioned backup recording of the demo`.

### Task 4: Script, Q&A, spec, rehearsal

**Files:** Create `docs/presentation/demo-script.md`. Modify main spec §10.2.

- [ ] **Step 1:** Write the script: setup checklist (warm-up run of both decks, NVDA voice and speed, notifications off, files open); the seven timed sections, each with spoken words, exact keys, what NVDA should say, and the fallback file; 7- and 15-minute variants; Snipping Tool steps to record NVDA's voice; Q&A (why not an LLM, why synthetic data, what if the model is wrong, PowerPoint's own checker, privacy, LibreOffice versus PowerPoint, what is not checked). State that the logo deck was built to illustrate the behaviour.
- [ ] **Step 2:** Rewrite main spec §10.2 to match, removing unsupported steps.
- [ ] **Step 3:** Time both live runs warm with rendering; put the measured waits in the script. Confirm every quoted NVDA line appears in Task 3's log.
- [ ] **Step 4:** List NVDA reading slide 3 in PowerPoint as a presenter rehearsal step with exact keys. It is not verified here, so the script must say so.
- [ ] **Step 5:** Run the full suite. Expected: all pass. Commit `docs: demo script, Q&A and spec §10.2`.
