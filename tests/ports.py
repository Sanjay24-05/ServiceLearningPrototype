"""Pick a free local port that browsers will actually open."""
from __future__ import annotations

import socket

# Ports Chromium/Edge refuse with ERR_UNSAFE_PORT (the ones a random free port can land on).
BROWSER_UNSAFE_PORTS = {1719, 1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566,
                        6665, 6666, 6667, 6668, 6669, 6679, 6697, 10080}


def _random_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def free_browser_port(pick=_random_free_port, tries: int = 50) -> int:
    for _ in range(tries):
        port = pick()
        if port not in BROWSER_UNSAFE_PORTS:
            return port
    raise RuntimeError("no browser-safe free port found")
