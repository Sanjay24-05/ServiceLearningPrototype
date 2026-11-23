"""Before/after images of the slides a fix changed (for sighted viewers)."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

GAP = 24
WHITE = (255, 255, 255)
EDGE = (107, 114, 128)  # thin outline so white slides stand apart


def _flat(path: Path) -> Image.Image:
    with Image.open(path) as im:
        im = im.convert("RGBA")
    bg = Image.new("RGB", im.size, WHITE)
    bg.paste(im, mask=im.getchannel("A"))
    return bg


def compose(before_png: Path, after_png: Path, out_png: Path) -> None:
    """Write before (left) and after (right), same height, 24 px apart on white.

    Each half gets a 1 px grey outline so white slides do not merge into
    the gap.
    """
    a, b = _flat(before_png), _flat(after_png)
    h = max(a.height, b.height)

    def fit(im: Image.Image) -> Image.Image:
        if im.height == h:
            return im
        w = max(1, round(im.width * h / im.height))
        return im.resize((w, h), Image.LANCZOS)

    a, b = fit(a), fit(b)
    out = Image.new("RGB", (a.width + GAP + b.width, h), WHITE)
    out.paste(a, (0, 0))
    out.paste(b, (a.width + GAP, 0))
    draw = ImageDraw.Draw(out)
    draw.rectangle((0, 0, a.width - 1, h - 1), outline=EDGE)
    draw.rectangle((a.width + GAP, 0, a.width + GAP + b.width - 1, h - 1),
                   outline=EDGE)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_png, "PNG")


def alt_text(n: int, logs: list[str]) -> str:
    """`Slide {n} before and after: {changes}`, built from the change log."""
    prefix = f"Slide {n}: "
    parts = [(t[len(prefix):] if t.startswith(prefix) else t).rstrip(". ")
             for t in logs]
    return f"Slide {n} before and after: " + "; ".join(parts) + "."


def image_path(run_dir: Path, n: int) -> Path:
    return Path(run_dir) / "output" / f"compare-slide-{n}.png"


def clear(run_dir: Path) -> None:
    """Remove images from an earlier export of this run."""
    for p in (Path(run_dir) / "output").glob("compare-slide-*.png"):
        try:
            p.unlink()
        except OSError:
            pass


def _png(render, n: int) -> Path | None:
    if render is None or render.status != "ok" or not 1 <= n <= len(render.slides):
        return None
    slide = render.slides[n - 1]
    if slide is None or not Path(slide.png_path).is_file():
        return None
    return Path(slide.png_path)


def build(run_dir: Path, original, export,
          logs: dict[int, list[str]]) -> list[tuple[int, str]]:
    """Compose one image per changed slide; return [(n, alt)] in slide order.

    logs maps each changed slide number to its change-log lines. Returns []
    (and writes nothing) unless both renders have a PNG for every changed
    slide, so the section is simply absent without LibreOffice.
    """
    clear(run_dir)
    final = export.final if export is not None else None
    if not logs or final is None:
        return []
    pairs = {n: (_png(original.render, n), _png(final.render, n)) for n in logs}
    if any(b is None or a is None for b, a in pairs.values()):
        return []
    out: list[tuple[int, str]] = []
    try:
        for n in sorted(pairs):
            compose(*pairs[n], image_path(run_dir, n))
            out.append((n, alt_text(n, logs[n])))
    except Exception:
        clear(run_dir)
        return []
    return out


_DIGITS = re.compile(r"[1-9][0-9]{0,5}")


def parse_n(text: str) -> int | None:
    """A slide number from the URL, or None for anything else."""
    return int(text) if _DIGITS.fullmatch(text) else None
