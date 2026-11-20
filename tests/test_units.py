from slideproof.units import Rect, rotated_aabb, inches

def test_inches():
    assert inches(1) == 914400

def test_intersect_and_area():
    a, b = Rect(0, 0, 100, 100), Rect(50, 50, 100, 100)
    assert a.intersect(b) == Rect(50, 50, 50, 50)
    assert a.intersect(Rect(200, 200, 10, 10)) is None
    assert a.area == 10000

def test_contains():
    assert Rect(0, 0, 100, 100).contains(Rect(10, 10, 20, 20))
    assert not Rect(0, 0, 100, 100).contains(Rect(90, 10, 20, 20))

def test_rotated_aabb_90_swaps_dimensions_about_centre():
    assert rotated_aabb(Rect(0, 0, 200, 100), 90) == Rect(50, -50, 100, 200)

def test_rotated_aabb_zero_is_identity():
    assert rotated_aabb(Rect(5, 5, 10, 20), 0) == Rect(5, 5, 10, 20)
