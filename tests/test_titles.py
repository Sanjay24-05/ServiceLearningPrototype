from pptx import Presentation
from pptx.util import Inches

from slideproof.analysis import analyse
from slideproof.checks.titles import check_titles
from slideproof.describe import describe
from slideproof.loader import load_deck
from slideproof.verify import export_and_verify


def test_demo_slide5_title(demo_deck):
    d = load_deck(demo_deck[0])
    fs = check_titles(d, None)
    assert [(f.slide_index, d.element(f.element_ids[0]).name) for f in fs] == [(5, "slide-title")]
    f = fs[0]
    assert f.severity == "visible" and f.fix.kind == "F3" and f.fix.safety == "safe"
    desc = describe(f, d)
    assert desc.headline == "the title sits noticeably lower than on the other 6 slides"
    assert desc.fix_label == "Move the title to the same position as on the other slides. Safe fix."
    assert desc.change_log == "Slide 5: the title moved to the same position as on the other slides."


def test_title_slide_excluded(demo_deck):
    d = load_deck(demo_deck[0])
    assert all(f.slide_index != 1 for f in check_titles(d, None))


def test_no_dominant_position_silent(tmp_path):
    prs = Presentation()
    layout = next(l for l in prs.slide_layouts if l.name == "Title Only")
    for i in range(4):
        s = prs.slides.add_slide(layout)
        s.shapes.title.text = f"T{i}"
        s.shapes.title.top = Inches(0.3 + 0.8 * i)
    p = tmp_path / "t.pptx"; prs.save(p)
    assert check_titles(load_deck(p), None) == []


def test_fewer_than_three_titles_silent(tmp_path):
    prs = Presentation()
    layout = next(l for l in prs.slide_layouts if l.name == "Title Only")
    for i in range(2):
        s = prs.slides.add_slide(layout)
        s.shapes.title.text = f"T{i}"
    prs.slides[1].shapes.title.top = Inches(3)
    p = tmp_path / "t.pptx"; prs.save(p)
    assert check_titles(load_deck(p), None) == []


def test_f3_resolves(monkeypatch, demo_deck, tmp_path):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    a = analyse(demo_deck[0], tmp_path / "a")
    f3 = [f.fix for f in a.findings if f.fix and f.fix.kind == "F3"]
    r = export_and_verify(a, f3, tmp_path / "c.pptx", tmp_path / "v")
    assert r.resolved == 1 and r.new_visible == 0 and not r.rolled_back


def _layout(prs, name):
    return next(l for l in prs.slide_layouts if l.name == name)


def test_mixed_layouts_not_compared(tmp_path):
    # Review issue 1: section headers and caption slides have their own title position.
    prs = Presentation()
    for name in ["Title and Content"] * 5 + ["Section Header"] * 2 + ["Picture with Caption"]:
        s = prs.slides.add_slide(_layout(prs, name))
        s.shapes.title.text = name
    p = tmp_path / "mixed.pptx"; prs.save(p)
    assert check_titles(load_deck(p), None) == []


def test_moved_title_found_within_its_layout(tmp_path):
    prs = Presentation()
    for i in range(5):
        s = prs.slides.add_slide(_layout(prs, "Title and Content"))
        s.shapes.title.text = f"T{i}"
    s = prs.slides.add_slide(_layout(prs, "Section Header"))
    s.shapes.title.text = "Part two"
    prs.slides[2].shapes.title.top = prs.slides[2].shapes.title.top + Inches(0.6)
    p = tmp_path / "moved.pptx"; prs.save(p)
    assert [f.slide_index for f in check_titles(load_deck(p), None)] == [3]


def test_offslide_title_is_not_moved(tmp_path):
    # Review issue 3: a title parked off the slide keeps it for screen readers; never "fix" it.
    from slideproof.checks import run_checks
    prs = Presentation()
    for i in range(4):
        s = prs.slides.add_slide(_layout(prs, "Title Only"))
        s.shapes.title.text = f"T{i}"
    prs.slides[1].shapes.title.top = -Inches(2)
    p = tmp_path / "hidden.pptx"; prs.save(p)
    d = load_deck(p)
    assert check_titles(d, None) == []
    c10 = [f for f in run_checks(d, None) if f.check_id == "C10"]
    assert len(c10) == 1 and c10[0].fix is None and c10[0].severity == "minor"
    assert describe(c10[0], d).headline == "the title is placed off the slide"
    assert "screen readers still read it" in describe(c10[0], d).full
