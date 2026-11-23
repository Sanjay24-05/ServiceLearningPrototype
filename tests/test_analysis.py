import dataclasses

from slideproof.analysis import analyse
from slideproof.verify import export_and_verify


def test_analyse_demo_without_libreoffice(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    msgs = []
    a = analyse(demo_deck[0], tmp_path, msgs.append)
    assert a.render.status == "skipped"
    assert a.skipped_note == ("Note: text overflow, contrast and text size checks were skipped "
                             "because LibreOffice is not installed.")
    assert msgs[:2] == ["Reading slides…", "Rendering slides…"] and msgs[-1] == "Checking slide 8 of 8…"
    assert {f.check_id for f in a.report.visible} == {"C1", "C2", "C4", "C5", "C8"}
    assert {f.check_id for f in a.report.minor} == {"C9", "C10"}


def test_export_resolves_both_and_introduces_nothing(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    a = analyse(demo_deck[0], tmp_path / "a")
    fixes = [f.fix for f in a.findings if f.fix]
    r = export_and_verify(a, fixes, tmp_path / "demo (checked).pptx", tmp_path / "v")
    assert r.output.exists() and r.resolved == 4 and r.new_visible == 0 and not r.rolled_back


def test_bad_fix_is_rolled_back(monkeypatch, tmp_path, demo_deck):
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "missing.exe"))
    a = analyse(demo_deck[0], tmp_path / "a")
    f1 = next(f for f in a.findings if f.fix and f.fix.kind == "F1")
    assert f1.fix.fix_id.endswith(":" + f1.fix.element_id)
    sw, sh = a.deck.slide_w, a.deck.slide_h
    # frame hanging 30% off the right edge of the slide
    bad_fix = dataclasses.replace(
        f1.fix, params={"frame": [round(sw * 0.7), 0, round(sw * 0.5), round(sh * 0.2)],
                        "scaled": False})
    findings = [dataclasses.replace(f, fix=bad_fix) if f is f1 else f
                for f in a.findings]
    a2 = dataclasses.replace(a, findings=findings)
    fixes = [f.fix for f in a2.findings if f.fix]
    out = tmp_path / "demo (checked).pptx"
    r = export_and_verify(a2, fixes, out, tmp_path / "v")
    assert [fx.fix_id for fx, _ in r.rolled_back] == [bad_fix.fix_id]
    assert r.rolled_back[0][1] == "the problem was still there after the fix"
    assert r.output == out and out.exists()
    assert any(fx.kind != "F1" for fx in r.applied) and bad_fix not in r.applied
