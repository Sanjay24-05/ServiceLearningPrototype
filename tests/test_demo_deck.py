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
