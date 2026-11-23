import pytest

from slideproof.prioritise import prioritise


def test_prioritise_orders_by_score_and_groups(make_finding):
    fs = [make_finding("C1", 2, f"e{i}", "visible", 0.3) for i in range(6)] + [make_finding("C4", 1, "x", "minor", 0.9)]
    r = prioritise(fs, slides_checked=3)
    assert len(r.visible) == 1 and r.visible[0].measurements == {"grouped": 6} and r.visible[0].fix is None
    assert [f.check_id for f in r.minor] == ["C4"] and r.slides_with_visible == 1
    assert r.slides_checked == 3


def test_five_findings_not_grouped_and_sorted(make_finding):
    fs = [make_finding("C1", 2, f"e{i}", "visible", 0.1 * (i + 1)) for i in range(5)]
    r = prioritise(fs, slides_checked=2)
    assert len(r.visible) == 5
    assert [f.magnitude for f in r.visible] == sorted((f.magnitude for f in fs), reverse=True)


def test_minor_members_never_promoted_by_a_group(make_finding):
    # Six minor footer C7s and one visible C7 on a slide: the footers stay minor.
    fs = [make_finding("C7", 3, f"foot{i}", "minor", 0.4) for i in range(6)]
    fs.append(make_finding("C7", 3, "body", "visible", 0.5))
    r = prioritise(fs, slides_checked=3)
    assert [(f.element_ids, f.severity) for f in r.visible] == [(("body",), "visible")]
    (g,) = r.minor
    assert g.measurements == {"grouped": 6} and g.severity == "minor"
    assert set(g.element_ids) == {f"foot{i}" for i in range(6)}


@pytest.mark.parametrize("confs, expected", [
    (["definite"] * 6, "definite"),
    (["definite"] * 5 + ["likely"], "likely"),
    (["likely"] + ["definite"] * 5, "likely"),
])
def test_group_confidence_is_likely_if_any_member_is(make_finding, confs, expected):
    from dataclasses import replace
    fs = [replace(make_finding("C7", 2, f"e{i}", "visible", 0.3), confidence=c)
          for i, c in enumerate(confs)]
    (g,) = prioritise(fs, slides_checked=2).visible
    assert g.confidence == expected
