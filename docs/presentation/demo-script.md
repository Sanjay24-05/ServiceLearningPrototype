# Slide Proof: 10-minute demo script

**Files**

| File | Use |
|---|---|
| `slide_proof_talk.pptx` | The six slides; what to say is also in the notes |
| `demo_deck.pptx` | Opened in PowerPoint for the opening (made in step 1) |
| `school_logo_deck.pptx` | The AI part |
| `backup-demo.webm` | Silent, captioned slideshow-style video of the live part (3 min 45 s). Captions: NVDA's logged words from a real run on 2026-11-25, without page-loading noise. Screens were retaken afterwards. Words: `backup-demo.txt` |
| `backup-demo-ai.webm` | Only the AI part, for use if that section fails |
| `before-after.png`, `demo-slide-3.png` | Pictures to show if something fails |

## Before you present

1. In the project folder, with the virtual environment active, make the demo deck:
   `python tools/make_demo_deck.py tests/output`
2. Start the tool: `python -m slideproof`. It opens http://127.0.0.1:8765/.
3. **Warm up. Do not skip this.** Run "Try the demo presentation" and create its corrected copy, then check the logo deck. One cold first run took 48 seconds; warm ones took about 10.
4. Turn on Do Not Disturb. Plug in. Check the sound reaches the room speakers.
5. Start NVDA. Slow the voice down so listeners can follow (NVDA menu, Preferences, Settings, Speech).
6. Open the talk deck, `tests/output/demo_deck.pptx` at slide 3, the start page, and `backup-demo.webm`, paused.
7. **Rehearse the opening.** NVDA reading slide 3 in PowerPoint has not been tested for this script. If it doesn't read clearly, skip it and read the five bullets aloud yourself. Read the text only: NVDA can announce "covers…" or "behind…" when you select a whole shape, so press Escape and select shapes in rehearsal to hear what it says.
8. **Rehearse the keys.** H, 2 and Tab from the start page were not tested with NVDA; the recording moved focus by script.

NVDA key = Insert (or Caps Lock on the laptop layout). Ctrl stops the voice at any time.

## The ten minutes

### 0:00 It sounds fine (talk slide 1, then PowerPoint, then talk slide 2)

Say: "Listen to this slide. Tell me what's wrong with it."

Do: in PowerPoint, slide 3 of the demo deck, click the text of the bullets and press NVDA+Down Arrow to read it (NVDA+A on the laptop layout). Keep the screen hidden from the room if you can.

Say: "The words sound fine." Show talk slide 2. "The green block stands in for a chart. It covers the ends of three bullets. Reading the text gives no hint. NVDA can report that shapes overlap, in points, if you select them one by one. But it doesn't check the whole deck, or say what the audience loses. That's the gap."

If it fails: read the bullets aloud, then show talk slide 2.

### 1:30 Who it's for (talk slide 3)

Say: "Slide Proof is for blind people who make their own slides. Today they'd ask a sighted person to look. This lets them check alone, before they present. Nothing leaves the computer, and the original file is never changed."

### 2:30 Live (browser)

| Do | NVDA says (wording may shift slightly) |
|---|---|
| Tab to "Try the demo presentation", press Enter. About 10 seconds | "Reading slides… Rendering slides…" |
| Let the report load | "8 slides checked. 8 visible problems on 6 slides, 2 minor." |
| Press Ctrl to stop it, then Tab | "Slide 4, "Our team": picture "Team photo" is stretched wider than its natural shape… Safe fix, check box, checked" |
| Press H a few times | The next findings |
| Press 2 until you hear "Apply fixes", Tab once to "Create corrected copy", press Enter. About 10 seconds | "4 fixes applied. 4 problems resolved. 0 new problems among the problems this version checks." |

Say while it works: "It's fixing a copy and then checking that copy again. If a fix doesn't work, or causes a new visible problem for that object, it's undone. Any other new visible problem is counted in the result."

Say: "It found ten problems and fixed four. The covered bullets on slide 3 are reported but not fixed yet; that fix is next."

If it fails: play `backup-demo.webm`.

### 5:30 Before and after (browser)

Do: Tab to "Show the changed slides", press Enter. Scroll for the room.

Say: "These pictures are for a sighted helper. Each one also says in words what changed."

If it fails: show `before-after.png`.

### 6:30 Mistake or on purpose? (talk slide 4, then browser)

Say: "Some things run off the slide on purpose, like a logo. Reporting every one of those would bury the real mistakes. So a small model judges them."

Do: "Check another file", choose `school_logo_deck.pptx`, "Check slides". About 10 seconds.

Say: "The same logo runs off all six slides. The model says all six are probably design. The photo running off slide 4 stays a visible problem." Press 2 until you hear "Probably intentional". "They're still listed, with the reason and how sure it is, and the fix isn't ticked."

**Say this too:** "I made this deck to show how the model behaves. It isn't a test of its accuracy. That's the next slide."

If it fails: play `backup-demo-ai.webm`.

### 8:00 What we measured (talk slide 5)

Say: "We used 120 synthetic decks, in five rounds. Each round tested on decks held out of that round's training. 97.6% of planted mistakes stayed in the main lists. It recognised 94.3% of deliberate designs. Those figures are mildly optimistic, because we picked the settings on the same predictions. It's untested on real-world decks, and no blind user has tested it yet."

### 9:00 What comes next (talk slide 6)

Say: "Next are the remaining fixes, JAWS, and testing with blind users. Can you introduce us to blind students or staff who make slides?"

If the talk deck fails at any point: read the "Say" lines; they carry the whole talk.

## Shorter or longer

- **7 minutes:** skip pressing H, skip "Show the changed slides" (show `before-after.png` for 20 seconds), and make "Who it's for" one sentence.
- **15 minutes:** add the "How Slide Proof works" page, open one "Layout of slide 4", and leave 4 minutes for questions.

## Recording NVDA's voice yourself (optional)

1. Turn sound on and start NVDA.
2. Open Snipping Tool, choose record (the video camera), then New, and select the browser area.
3. Turn on system audio in the recording bar. If your version has no such button, update Snipping Tool from the Microsoft Store.
4. Start, follow the 2:30 to 6:30 sections, then stop and save.

NVDA may read the Snipping Tool window itself, so wait for it to finish before starting.

## Questions you may get

- **Why not use a large AI model?** Slides would leave the computer, it can invent things, and the question here is about shapes and positions. A small model is private, fast and gives the same answer every time. It also says why.
- **Why synthetic data?** We have no labelled set of real mistakes. Real slides are also personal. It means our figures show agreement with our own generator, not field accuracy.
- **What if the model is wrong?** In testing, among the findings the app judges, 14 of 593 planted mistakes were moved. Nothing is hidden: a moved finding is still listed and counted, with its fix unticked. Text that sticks out is never moved. A picture or shape covering text is judged, so it could be moved by mistake.
- **Where is the AI, and where isn't it?** The eleven checks are rules. The AI only judges things that stick out or overlap.
- **Doesn't PowerPoint have a checker?** It has an accessibility checker, aimed at making a file accessible to its readers. We look for layout problems the audience would see. We haven't run a side-by-side comparison.
- **How accurate are the checks?** On our own demo deck, every planted problem is found and nothing extra. That deck was built for testing, so it's a sanity check.
- **Is it the same as PowerPoint's rendering?** No. LibreOffice draws the slides, so fonts and line breaks can differ. Findings that depend on this say "likely".
- **Doesn't NVDA already report overlaps?** In PowerPoint, yes: select a shape and it gives distances to other shapes and the slide edge. That's one shape at a time, in points. Slide Proof checks every slide at once, reports what the audience would see, and can fix some of it.
- **What isn't checked?** Among other things, text inside charts and diagrams, text overflowing upward, and see-through overlays (treated as solid).
- **Has a blind person used it?** No. We ran it with NVDA, partly by script. That's why we're asking for introductions.
