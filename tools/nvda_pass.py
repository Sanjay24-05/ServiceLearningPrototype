"""Drive Slide Proof in a visible Edge window while NVDA logs its speech. Prints NVDA's speech per phase.

Usage (from the repo root, NVDA must already be running with speech logging):
    "C:\\Program Files\\NVDA\\nvda.exe" -m -l 12 -f <log>      # -m quiet start, -l 12 = log speech (IO level)
    PYTHONPATH=. .venv/Scripts/python tools/nvda_pass.py <log> tests/output/demo_deck.pptx <runs dir>
    "C:\\Program Files\\NVDA\\nvda.exe" -q                     # quit NVDA afterwards

Keys are sent through the browser (not the OS), so NVDA's own quick-navigation keys (H etc.) are not
exercised; page-load announcements, focus announcements and live status updates are.
"""
import re, socket, sys, threading, time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright
from slideproof.web.app import create_app

LOG = Path(sys.argv[1]); DECK = Path(sys.argv[2]); RUNS = Path(sys.argv[3])
BROWSER_UNSAFE_PORTS = {5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697, 10080}


def free_browser_port() -> int:
    """A free local port that Edge will open (some ports give ERR_UNSAFE_PORT)."""
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in BROWSER_UNSAFE_PORTS:
            return port


port = free_browser_port()
server = uvicorn.Server(uvicorn.Config(create_app(RUNS), host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started: time.sleep(0.1)
BASE = f"http://127.0.0.1:{port}"

def mark(): return LOG.stat().st_size
def spoken(start):
    text = LOG.read_bytes()[start:].decode("utf-8", "replace")
    out = []
    for m in re.finditer(r"Speaking \[(.*)\]", text):
        parts = [a or b for a, b in re.findall(r"""'([^']*)'|"([^"]*)\"""", m.group(1))]
        line = " | ".join(p for p in parts if p not in ("en_US",))
        if line: out.append(line)
    return out
def phase(name, start):
    print(f"\n### {name}"); [print("  ", l) for l in spoken(start)]

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=False, args=["--force-renderer-accessibility", "--start-maximized"])
    pg = b.new_page(no_viewport=True); pg.bring_to_front()
    m = mark(); pg.goto(BASE + "/"); time.sleep(8); phase("1. Start page loads", m)
    m = mark(); pg.keyboard.press("Tab"); time.sleep(2); phase("2. Tab to file field", m)
    pg.set_input_files("#file", str(DECK))
    m = mark(); pg.keyboard.press("Tab"); time.sleep(2); phase("3. Tab to Check slides button", m)
    m = mark(); pg.keyboard.press("Enter"); pg.wait_for_url("**/report", timeout=120000); time.sleep(35)
    phase("4. Progress page, then report page loads (say-all)", m)
    for i in range(4):
        m = mark(); pg.keyboard.press("Tab"); time.sleep(2.5); phase(f"5.{i+1} Tab on report", m)
    m = mark(); pg.keyboard.press("Space"); time.sleep(4); phase("5.5 Space opens the layout map", m)
    m = mark(); pg.get_by_role("button", name="Create corrected copy").focus(); time.sleep(2)
    phase("6. Focus moves to Create corrected copy", m)
    m = mark(); pg.keyboard.press("Enter"); pg.wait_for_url("**/result", timeout=180000); time.sleep(15)
    phase("7. Enter on button: progress page, then result page loads", m)
    for i in range(4):
        m = mark(); pg.keyboard.press("Tab"); time.sleep(2.5); phase(f"8.{i+1} Tab on result", m)
    summary = pg.locator("summary", has_text="Show the changed slides")
    if summary.count():
        m = mark(); summary.focus(); time.sleep(2.5); phase("9. Focus the before/after summary", m)
        m = mark(); pg.keyboard.press("Enter"); time.sleep(3); phase("10. Enter expands it", m)
        print("\n### 11. Image alt text (accessibility tree)")
        for alt in pg.locator("details img").evaluate_all("els => els.map(e => e.alt)"):
            print("  ", alt)
    b.close()
server.should_exit = True
