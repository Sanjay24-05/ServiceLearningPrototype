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
