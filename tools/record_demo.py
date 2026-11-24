"""Make a silent, captioned backup video of the demo from a real NVDA run.

Start NVDA with speech logging first (see tools/nvda_pass.py), then, from the repo root:
    .venv/Scripts/python tools/record_demo.py <nvda log> docs/presentation/backup-demo.webm
Leave the mouse and keyboard alone while it runs: whatever NVDA says becomes a caption. Sound can
be muted. The captions are what NVDA logged; what was said is also saved next to the video as .txt.
"""
from __future__ import annotations

import base64
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.nvda_log import spoken  # noqa: E402

MAX_CAPTION = 620

# Draws every frame on a canvas in real time while Edge's MediaRecorder encodes it.
ENCODE_JS = """async (frames) => {
  const c = document.createElement('canvas'); c.width = 1280; c.height = 720;
  document.body.appendChild(c);
  const g = c.getContext('2d');
  const rec = new MediaRecorder(c.captureStream(10), {mimeType: 'video/webm', videoBitsPerSecond: 2500000});
  const chunks = []; rec.ondataavailable = e => chunks.push(e.data);
  const stopped = new Promise(r => rec.onstop = r);
  const draw = (img, f) => {
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, 1280, 720);
    const k = Math.min(1280 / img.width, 520 / img.height);
    g.drawImage(img, (1280 - img.width * k) / 2, 0, img.width * k, img.height * k);
    g.fillStyle = '#1b1b1b'; g.fillRect(0, 520, 1280, 200);
    g.fillStyle = '#ffc107'; g.font = 'bold 18px Segoe UI'; g.fillText(f.step, 24, 546);
    g.fillStyle = '#ffffff'; g.font = '20px Segoe UI';
    let line = '', y = 574;
    for (const w of f.caption.split(' ')) {
      if (g.measureText(line + w).width > 1230) { g.fillText(line, 24, y); line = ''; y += 25; }
      line += w + ' ';
    }
    g.fillText(line, 24, y);
  };
  rec.start(1000);
  for (const f of frames) {
    const img = new Image(); img.src = f.png; await img.decode();
    const end = performance.now() + f.seconds * 1000;
    while (performance.now() < end) { draw(img, f); await new Promise(r => setTimeout(r, 100)); }
  }
  rec.stop(); await stopped;
  const buf = new Uint8Array(await new Blob(chunks).arrayBuffer());
  let s = ''; for (let i = 0; i < buf.length; i += 32768) s += String.fromCharCode(...buf.subarray(i, i + 32768));
  return btoa(s);
}"""


def caption(lines: list[str]) -> str:
    """What NVDA said, without the browser window's own title; shortened to fit the band."""
    kept = [l.replace(" | ", ", ").strip() for l in lines if "Microsoft" not in l]
    text = " … ".join(kept)
    return text if len(text) <= MAX_CAPTION else text[:MAX_CAPTION - 1].rstrip() + "…"


def seconds_for(text: str) -> float:
    return max(4, round(0.35 * len(text.split()), 2))


def encode(page, frames: list[dict], out: Path) -> None:
    page.set_default_timeout(0)
    page.goto("about:blank")
    out.write_bytes(base64.b64decode(page.evaluate(ENCODE_JS, frames)))


def run(log: Path, out: Path) -> None:
    import uvicorn
    from playwright.sync_api import sync_playwright
    from slideproof.web.app import create_app
    from tests.ports import free_browser_port

    port = free_browser_port()
    server = uvicorn.Server(uvicorn.Config(
        create_app(Path(tempfile.mkdtemp(prefix="slideproof-rec-"))),
        host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    base = f"http://127.0.0.1:{port}"
    frames: list[dict] = []
    words: list[str] = []

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=False,
                              args=["--force-renderer-accessibility"])
        pg = b.new_page(viewport={"width": 1000, "height": 406}, device_scale_factor=1.28)
        pg.bring_to_front()

        def step(name, action, wait):
            start = log.stat().st_size
            action()
            time.sleep(wait)
            lines = spoken(log.read_bytes()[start:].decode("utf-8", "replace"))
            text = caption(lines)
            png = "data:image/png;base64," + base64.b64encode(pg.screenshot()).decode()
            frames.append({"step": name, "caption": text or "(NVDA is silent)", "png": png,
                           "seconds": seconds_for(text)})
            words.extend([f"### {name}", *lines, ""])

        def press_and_wait(key, url):
            pg.keyboard.press(key)
            pg.wait_for_url(url, timeout=240000)

        tab = lambda: pg.keyboard.press("Tab")  # noqa: E731
        step("Start page", lambda: pg.goto(base + "/"), 8)
        step("Focus: Try the demo presentation",
             lambda: pg.get_by_role("button", name="Try the demo presentation").focus(), 2.5)
        step("Enter: checking, then the report", lambda: press_and_wait("Enter", "**/report"), 35)
        step("Tab: first finding and its fix", tab, 5)
        step("Focus: Create corrected copy",
             lambda: pg.get_by_role("button", name="Create corrected copy").focus(), 2.5)
        step("Enter: fixing, re-checking, result", lambda: press_and_wait("Enter", "**/result"), 18)
        step("Tab: Show the changed slides", tab, 3)
        step("Enter: the before and after pictures", lambda: pg.keyboard.press("Enter"), 3)
        for i, img in enumerate(pg.locator("details img").all(), 1):
            img.scroll_into_view_if_needed()
            time.sleep(0.5)
            alt = img.get_attribute("alt")
            png = "data:image/png;base64," + base64.b64encode(pg.screenshot()).decode()
            frames.append({"step": f"Picture {i}: its description (from the page, not spoken here)",
                           "caption": alt, "png": png, "seconds": seconds_for(alt)})
        step("The AI part: choose the school-logo deck", lambda: pg.goto(base + "/"), 6)
        pg.set_input_files("#file", str(ROOT / "docs" / "presentation" / "school_logo_deck.pptx"))
        pg.get_by_role("button", name="Check slides").focus()
        step("Enter: checking, then the report", lambda: press_and_wait("Enter", "**/report"), 35)
        step("The real mistake stays a visible problem", tab, 5)

        def show_intentional():
            h = pg.get_by_role("heading", name="Probably intentional")
            h.scroll_into_view_if_needed()
            h.evaluate("e => e.scrollIntoView()")
            section = pg.locator("h2:has-text('Probably intentional') ~ section").first
            section.locator("input[type=checkbox]").focus()
            h.evaluate("e => e.scrollIntoView()")

        step("The six logos: Probably intentional, fixes not ticked", show_intentional, 5)
        encode(pg, frames, out)
        b.close()
    server.should_exit = True
    out.with_suffix(".txt").write_text("\n".join(words), encoding="utf-8")
    print(f"{out} ({out.stat().st_size // 1024} KB, {sum(f['seconds'] for f in frames):.0f} s)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tools/record_demo.py <nvda log> <out.webm>")
        raise SystemExit(2)
    if not Path(sys.argv[1]).exists():
        print(f"NVDA log not found: {sys.argv[1]}. Start NVDA with logging first "
              "(see tools/nvda_pass.py).")
        raise SystemExit(2)
    run(Path(sys.argv[1]), Path(sys.argv[2]))
