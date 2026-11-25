# Slide Proof faculty presentation: short design

Approved in conversation on 2026-11-24.

**Intent.** Show faculty that Slide Proof solves a real problem for blind presenters, that its AI part helps them, and that the evidence is stated honestly. The developer presents. Assumed slot: 10 minutes (trims to 7, stretches to 15); the real slot and criteria are not known yet.

**Approaches.**
1. Live demo with a recorded backup: most convincing, and the recording covers rendering or audio trouble. **Picked.**
2. Recording-led: safe, but looks less like a working tool.
3. Slides-led: detailed on AI, but hides the user's experience.

**Running order.**

| Time | What happens |
|---|---|
| 0:00 | NVDA reads demo slide 3 in PowerPoint and it sounds fine; then the slide is shown: the chart covers the bullets |
| 1:30 | Who it is for, and why independence matters |
| 2:30 | Live: "Try the demo presentation", NVDA reads the report, create the corrected copy |
| 5:30 | Before/after pictures |
| 6:30 | AI: the school-logo deck |
| 8:00 | Model results and their limits |
| 9:00 | Next steps; the request: introductions to blind testers |

**Deliverables.** A script with keystrokes, fallbacks and Q&A; a six-slide .pptx that Slide Proof itself passes; a separate logo deck; a captioned backup video; a corrected main spec §10.2.

**Logo deck, measured in a spike (LibreOffice 26.8.3).** Six slides with the same logo off the top-left corner, plus one trip photo off the right of slide 4. All 6 logos moved to "Probably intentional" (p ≈ 0.998); the photo stayed visible (p = 0.0001). The deck was designed to fit what the model learned, so it illustrates behaviour and is not evidence of accuracy. The script says so.

**Wording rules.**
- Quote only measured numbers, always with "synthetic decks" and "decks the model never saw in training".
- Say that no blind user has tested it yet.
- Do not demonstrate features that do not exist: "Mark as intentional", font fix (F5), overlap fix (F6), text fit (F7).
- Do not claim the Yellow Idea half-donut is moved.

**Non-goals.** New app features; changes to the demo deck, its answer key, or the model.

**Constraints.** PowerPoint is installed. There is no ffmpeg and no Python audio-capture package, so the generated video is silent with captions. The presenter records NVDA's voice with Windows Snipping Tool, following written steps. Nothing is installed.

**Left to the builder.** Slide styling, and the exact file layout inside `docs/presentation/`.
