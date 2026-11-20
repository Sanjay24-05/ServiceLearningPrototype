# Slide Proof

Local tool that checks .pptx slide layouts for blind screen-reader users
(NVDA/JAWS). Your files stay on this computer.

## Setup (Windows)

1. Install Python 3.12 and create a virtual environment:
   `py -3.12 -m venv .venv`, then `.venv\Scripts\activate`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Install LibreOffice 7.6 or later (it renders slides for the overflow and
   contrast checks). If it is installed somewhere unusual, set the
   `SOFFICE_PATH` environment variable to the full path of `soffice.exe`.
   Without LibreOffice those checks are skipped.
4. Install the fonts Carlito, Caladea, Liberation Sans and Liberation Serif
   so text measurements match PowerPoint.

## Start

`python -m slideproof` starts the tool at http://127.0.0.1:8765/ and opens it
in your browser.

## Test

`python -m pytest`
