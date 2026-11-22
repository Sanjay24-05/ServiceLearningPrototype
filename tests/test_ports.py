from tests.ports import free_browser_port


def test_skips_browser_unsafe_ports():
    picks = iter([6668, 10080, 50123])
    assert free_browser_port(lambda: next(picks)) == 50123
