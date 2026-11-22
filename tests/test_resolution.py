from slideproof.checks.resolution import check_resolution
from slideproof.describe import describe
from slideproof.loader import load_deck


def test_demo_logo_low_resolution(demo_deck):
    d = load_deck(demo_deck[0])
    fs = check_resolution(d, None)
    assert [d.element(f.element_ids[0]).name for f in fs] == ["logo"]
    f = fs[0]
    assert f.severity == "visible" and f.confidence == "definite" and f.fix is None
    assert f.measurements["dpi"] == 50
    assert describe(f, d).headline == 'picture "Garden logo" is low resolution'
    assert "has about 50 pixels per inch" in describe(f, d).full


def test_minor_band(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 8.5, "h": 6.375,
                              "px": (800, 600)}]))
    fs = check_resolution(d, None)
    assert [f.severity for f in fs] == ["minor"] and fs[0].measurements["dpi"] == 94


def test_sharp_picture_not_flagged(tiny_deck):
    d = load_deck(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 4, "h": 3,
                              "px": (800, 600)}]))
    assert check_resolution(d, None) == []


def test_vector_picture_not_low_resolution(tiny_deck):
    # Review issue 4: EMF/WMF/SVG pictures have no pixel resolution problem.
    d = load_deck(tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 6, "h": 4.5,
                              "px": (100, 75)}]))
    d.slides[0].elements[0].image.vector = True
    assert check_resolution(d, None) == []


def test_svg_picture_loaded_as_vector(tiny_deck, tmp_path):
    from pptx import Presentation
    from pptx.oxml.ns import qn
    path = tiny_deck([{"kind": "picture", "name": "p", "x": 1, "y": 1, "w": 6, "h": 4.5, "px": (100, 75)}])
    prs = Presentation(path)
    blip = prs.slides[0].shapes[0]._element.blipFill.find(qn("a:blip"))
    ext_lst = blip.makeelement(qn("a:extLst"), {})
    ext = ext_lst.makeelement(qn("a:ext"), {"uri": "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"})
    ext_lst.append(ext); blip.append(ext_lst)
    out = tmp_path / "svg.pptx"; prs.save(out)
    assert load_deck(out).slides[0].elements[0].image.vector is True
