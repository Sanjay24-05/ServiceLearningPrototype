# M0 render notes

Measured 2026-11-21 on the development laptop (Windows 11) with LibreOffice 26.8.3 (typical install, found at `C:\Program Files\LibreOffice\program\soffice.exe`). Each run uses a fresh, isolated LibreOffice profile, as the pipeline does in production.

## Demo deck (8 slides)

| Run | LibreOffice → PDF | PDF → spans + PNGs | Pages |
|---|---|---|---|
| First ever run (LibreOffice first-start setup) | 21.2 s | 0.51 s | 8 / 8 |
| Later runs | 9.8 s | 0.47 s | 8 / 8 |

- Spans come out with correct text, positions, font names, sizes and colours. For example, slide 7's grey text reads `rgb=(187, 187, 187)` (#BBBBBB) and slide 5's stray box reads `font=Georgia`.
- Slide 2's agenda text spans start at x = 10.23 in, past the right part of the slide, as planted.

## 30-slide deck

| LibreOffice → PDF | PDF → spans + PNGs | Pages |
|---|---|---|
| 10.8 s | 1.57 s | 30 / 30 |

## End-to-end with real rendering (demo deck)

- `analyse()`: 11.7 s (render status `ok`, no skipped-checks note). It finds the same 2 visible problems as without LibreOffice.
- `export_and_verify()` with both safe fixes: 9.8 s, 2 applied, 2 resolved, 0 new problems, nothing rolled back.

## Conclusions

- Conversion time is dominated by LibreOffice start-up (about 10 s) and grows only slightly with slide count (8 → 30 slides: +1 s). Reading the PDF scales linearly (about 50 ms per slide).
- A user waits about 12 s for the report and about 10 s for the corrected copy. That is acceptable, and the progress page covers the wait.
- Every verify attempt re-renders, so a rollback costs another ~10 s. M1 checks don't use the render yet (final-review Minor 11). Skipping the render in verify until M3, or reusing one profile per run, would roughly halve export time.
