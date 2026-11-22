from pptx import Presentation
from pptx.util import Inches

from slideproof.checks.fonts import check_fonts
from slideproof.describe import describe
from slideproof.loader import load_deck


def _deck(tmp_path, boxes):
    """boxes: list of (slide_no, text, font_name_or_None)."""
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slides = {}
    for n, text, font in boxes:
        s = slides.get(n) or slides.setdefault(n, prs.slides.add_slide(blank))
        tf = s.shapes.add_textbox(Inches(1), Inches(1 + len(s.shapes)), Inches(6), Inches(1)).text_frame
        tf.text = text
        if font:
            tf.paragraphs[0].runs[0].font.name = font
    p = tmp_path / "f.pptx"; prs.save(p)
    return load_deck(p)


LONG = "This sentence is long enough to dominate the character count of the deck. " * 3


def test_demo_budget_note_font(demo_deck):
    d = load_deck(demo_deck[0])
    fs = check_fonts(d, None)
    assert [d.element(f.element_ids[0]).name for f in fs] == ["budget-note"]
    f = fs[0]
    assert f.severity == "minor" and f.fix is None and f.measurements["font"] == "Georgia"
    assert describe(f, d).headline.endswith("uses Georgia, a font used almost nowhere else")
    assert "mainly uses the theme font" in describe(f, d).full


def test_theme_font_never_stray(tmp_path):
    # Mostly an explicit font; a little theme-font text must not be called stray (Review Focus 4).
    d = _deck(tmp_path, [(1, LONG, "Arial"), (2, LONG, "Arial"), (3, "Small note", None)])
    assert check_fonts(d, None) == []


def test_explicit_theme_font_counts_as_theme(tmp_path):
    # "Calibri" is the default template's theme font: setting it explicitly is not a stray font.
    d = _deck(tmp_path, [(1, LONG, None), (2, LONG, None), (3, "Small note", "Calibri")])
    assert check_fonts(d, None) == []


def test_symbol_font_ignored(tmp_path):
    d = _deck(tmp_path, [(1, LONG, None), (2, LONG, None), (3, "x", "Wingdings")])
    assert check_fonts(d, None) == []


def test_stray_font_flagged(tmp_path):
    d = _deck(tmp_path, [(1, LONG, None), (2, LONG, None), (3, "Pasted from elsewhere", "Comic Sans MS")])
    fs = check_fonts(d, None)
    assert len(fs) == 1 and fs[0].measurements["font"] == "Comic Sans MS"


def test_theme_font_reference_is_theme(tmp_path):
    # Review issue 5: "+mn-lt" / "+mj-lt" mean "the theme's body/heading font".
    d = _deck(tmp_path, [(1, LONG, None), (2, LONG, None), (3, "Pasted note", "+mn-lt")])
    assert check_fonts(d, None) == []
