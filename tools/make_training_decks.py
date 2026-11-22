"""Builds synthetic decks for training the intent model.

Usage: python tools/make_training_decks.py <out_dir> [n_decks=120] [seed=7]

Every deck carries 2-4 deliberate design patterns (elements named ``deliberate-<pattern>-<n>``)
and 2-4 mistakes (``mistake-<pattern>-<n>``). The label comes from the name prefix only.
Positions, sizes and colours are drawn from the same ranges for both classes wherever the
pattern allows, so the model has to learn context rather than the generator.
"""
from __future__ import annotations

import io
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

_EMU = 914400
_TOPICS = ["Water use", "Campus energy", "Recycling rates", "Transport survey", "Food waste",
           "Green spaces", "Library access", "Noise levels", "Bike sharing", "Study habits"]
_POINTS = ["Usage fell by a fifth over two terms", "Students reported shorter queues",
           "The pilot covered three buildings", "Costs stayed within the agreed budget",
           "Feedback was mostly positive overall", "Further data is needed next year",
           "Staff trained in small groups", "Results matched the earlier survey"]


class _Ctx:
    def __init__(self, prs, w, h, rng):
        self.prs, self.w, self.h, self.rng = prs, w, h, rng
        self._imgs: dict = {}

    def u(self, a, b):
        return self.rng.uniform(a, b)

    def colour(self):
        return RGBColor(self.rng.randint(20, 235), self.rng.randint(20, 235), self.rng.randint(20, 235))

    def image(self):
        key = (self.rng.randint(0, 7), self.rng.randint(0, 5))
        if key not in self._imgs:
            r = random.Random(key[0] * 10 + key[1])
            im = Image.new("RGB", (160, 120), tuple(r.randint(150, 255) for _ in range(3)))
            ImageDraw.Draw(im).ellipse([30, 20, 130, 100], fill=tuple(r.randint(40, 230) for _ in range(3)))
            b = io.BytesIO()
            im.save(b, "PNG")
            self._imgs[key] = b.getvalue()
        return io.BytesIO(self._imgs[key])

    def edge_xy(self, w, h, f, side=None):
        """Top-left of a w x h box so that fraction f of it lies past one slide edge."""
        side = side or self.rng.choice("lrtb")
        ax, ay = self.u(0.5, max(0.5, self.w - w - 0.5)), self.u(1.5, max(1.5, self.h - h - 0.5))
        return {"l": (-f * w, ay), "r": (self.w - (1 - f) * w, ay),
                "t": (ax, -f * h), "b": (ax, self.h - (1 - f) * h)}[side]


def _picture(c, s, x, y, w, h, name):
    p = s.shapes.add_picture(c.image(), Inches(x), Inches(y), Inches(w), Inches(h))
    p.name = name
    return p


def _rect(c, s, x, y, w, h, name, shape=MSO_SHAPE.RECTANGLE, text=None):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = c.colour()
    sh.line.fill.background()
    sh.name = name
    if text:
        sh.text_frame.text = text
    return sh


def _textbox(s, x, y, w, h, lines, size, name):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    for i, t in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = t
        para.font.size = Pt(size)
    return tb


def _to_back(s, shape):
    tree = s.shapes._spTree
    tree.remove(shape._element)
    tree.insert(2, shape._element)


# --- deliberate patterns: (ctx, slide, name) ------------------------------------------------

def d_full_bleed(c, s, name):
    m = c.u(0.12, 0.4)
    p = _picture(c, s, -m, -m, c.w + 2 * m, c.h + 2 * m, name)
    if c.rng.random() < 0.5:
        _to_back(s, p)


def d_edge_banner(c, s, name):
    h = c.u(0.5, 1.3)
    out = h * c.u(0.05, 0.3)
    top = c.rng.random() < 0.5
    _rect(c, s, c.u(-0.2, 0.0), -out if top else c.h - h + out, c.w + 0.3, h, name)


def d_half_circle(c, s, name):
    d = c.u(1.5, 4)
    x, y = c.edge_xy(d, d, 0.5)
    _rect(c, s, x, y, d, d, name, MSO_SHAPE.OVAL)


def d_corner_badge(c, s, name):
    d, f = c.u(0.8, 1.6), c.u(0.1, 0.4)
    x = -f * d if c.rng.random() < 0.5 else c.w - (1 - f) * d
    y = -f * d if c.rng.random() < 0.5 else c.h - (1 - f) * d
    _rect(c, s, x, y, d, d, name, MSO_SHAPE.OVAL if c.rng.random() < 0.5 else MSO_SHAPE.RECTANGLE)


def d_stacked_icon(c, s, name):
    size, x, y = c.u(0.6, 1.5), c.u(0.6, c.w - 2.5), c.u(1.8, c.h - 2.5)
    for k in range(c.rng.randint(2, 3)):
        sz = size * (1 - 0.25 * k)
        off = (size - sz) / 2
        _rect(c, s, x + off, y + off, sz, sz, f"{name}-{k}",
              MSO_SHAPE.OVAL if k % 2 == 0 else MSO_SHAPE.RECTANGLE)


def d_caption_band(c, s, name):
    w, h = c.u(3.5, 7), c.u(2.5, 4)
    x, y = c.u(0.6, c.w - w - 0.6), c.u(1.7, max(1.7, c.h - h - 0.4))
    _picture(c, s, x, y, w, h, name)
    bh = h * c.u(0.15, 0.3)
    _rect(c, s, x, y + h - bh, w, bh, f"{name}-band", text="Photo caption")


def d_frame(c, s, name):
    w, h = c.u(3, 6.5), c.u(2.2, 4)
    x, y = c.u(0.9, c.w - w - 0.9), c.u(1.9, max(1.9, c.h - h - 0.5))
    pad = c.u(0.08, 0.3)
    _rect(c, s, x - pad, y - pad, w + 2 * pad, h + 2 * pad, f"{name}-frame")
    _picture(c, s, x, y, w, h, name)


def d_text_panel(c, s, name):
    # The label is a filled text box laid on a larger panel (a filled box on a filled box).
    w, h = c.u(4, 7), c.u(2, 3.4)
    x, y = c.u(0.6, c.w - w - 0.6), c.u(1.7, max(1.7, c.h - h - 0.4))
    _rect(c, s, x, y, w, h, f"{name}-panel")
    inset = c.u(0.15, 0.5)
    tb = _textbox(s, x + inset, y + inset, w - 2 * inset, h - 2 * inset,
                  [c.rng.choice(_POINTS), c.rng.choice(_POINTS)], 18, name)
    tb.fill.solid()
    tb.fill.fore_color.rgb = c.colour()


# --- mistake patterns -----------------------------------------------------------------------

def m_nudged_text(c, s, name):
    w, h = c.u(3, 6), c.u(0.8, 1.6)
    x, y = c.edge_xy(w, h, c.u(0.1, 0.6))
    _textbox(s, x, y, w, h, [c.rng.choice(_POINTS)], 20, name)


def m_picture_over_text(c, s, name):
    w, h = c.u(4, 6.5), 2.0
    x, y = c.u(0.5, c.w - w - 0.5), c.u(1.8, c.h - 3.5)
    _textbox(s, x, y, w, h, c.rng.sample(_POINTS, 3), 18, f"{name}-text")
    cov, a, b = c.u(0.1, 0.8), c.u(0, 0.5), c.u(0, 0.4)
    _picture(c, s, x - a, y - b, a + cov * w, b + h * c.u(0.6, 1.2), name)


def m_partly_off(c, s, name):
    w, h = c.u(1.5, 5), c.u(1, 3.5)
    x, y = c.edge_xy(w, h, c.u(0.05, 0.4))
    if c.rng.random() < 0.5:
        _picture(c, s, x, y, w, h, name)
    else:
        _rect(c, s, x, y, w, h, name)


def m_duplicate(c, s, name):
    w, h = c.u(1.5, 4), c.u(1, 2.5)
    x, y = c.u(0.6, c.w - w - 0.8), c.u(1.7, c.h - h - 0.8)
    dx, dy = c.u(0.05, 0.3), c.u(0.05, 0.3)
    if c.rng.random() < 0.5:
        _picture(c, s, x, y, w, h, name)
        _picture(c, s, x + dx, y + dy, w, h, f"{name}-copy")
    else:
        _rect(c, s, x, y, w, h, name)
        _rect(c, s, x + dx, y + dy, w, h, f"{name}-copy")


def m_spill_title(c, s, name):
    t = s.shapes.title
    tw = c.u(2, 5)
    cx = (t.left + t.width / 2) / _EMU + c.u(-0.8, 0.8)
    top = t.top / _EMU + t.height / _EMU * c.u(0.2, 0.7)
    _picture(c, s, cx - tw / 2, top, tw, c.u(2, 3.5), name)


_DELIBERATE = {
    "full-bleed-photo": d_full_bleed, "edge-banner": d_edge_banner, "edge-half-circle": d_half_circle,
    "corner-badge": d_corner_badge, "stacked-icon": d_stacked_icon, "caption-band": d_caption_band,
    "photo-frame": d_frame, "text-panel": d_text_panel,
}
_EVERY_SLIDE = ("corner-logo", "footer-bar")
_MISTAKES = {
    "nudged-text": m_nudged_text, "picture-over-text": m_picture_over_text,
    "partly-off-box": m_partly_off, "duplicate-offset": m_duplicate, "spilled-title": m_spill_title,
}


def _every_slide(c, slides, kind, name):
    if kind == "corner-logo":
        d, f = c.u(0.6, 1.2), c.u(0.05, 0.25)
        x = -f * d if c.rng.random() < 0.5 else c.w - (1 - f) * d
        y = -f * d if c.rng.random() < 0.5 else c.h - (1 - f) * d
        for s in slides:
            _picture(c, s, x, y, d, d, name)
    else:
        h = c.u(0.3, 0.6)
        out = h * c.u(0.05, 0.3)
        col = c.colour()
        for s in slides:
            _rect(c, s, 0, c.h - h + out, c.w, h, name).fill.fore_color.rgb = col


def _fill_slide(c, s, layout_name, i):
    rng = c.rng
    title = s.shapes.title
    if title is not None:
        title.text = f"{rng.choice(_TOPICS)}: part {i + 1}"
        title.left, title.top, title.width, title.height = Inches(0.6), Inches(0.35), Inches(c.w - 1.2), Inches(1.2)
    lines = rng.sample(_POINTS, rng.randint(2, 4))
    half = c.w * 0.5
    if layout_name == "Title and Content":
        body = s.placeholders[1]
        body.left, body.top, body.width, body.height = Inches(0.6), Inches(1.7), Inches(half), Inches(3.8)
        body.text_frame.text = lines[0]
        for t in lines[1:]:
            body.text_frame.add_paragraph().text = t
    elif layout_name == "Title Only":
        _textbox(s, 0.6, 1.7, half, 3.8, lines, rng.choice([18, 20, 24]), "content-text")
    else:
        _textbox(s, 0.6, 0.5, half, 3.8, lines, 24, "content-text")
    right = half + 1.0
    roll = rng.random()
    if roll < 0.5:
        _picture(c, s, right, 1.9, c.w - right - 0.5, 3.2, "content-photo")
    elif roll < 0.75:
        tbl = s.shapes.add_table(3, 3, Inches(right), Inches(1.9), Inches(c.w - right - 0.5), Inches(1.8))
        tbl.name = "content-table"
        for r in range(3):
            for k in range(3):
                tbl.table.cell(r, k).text = f"R{r}C{k}"


def _build_one(path: Path, rng: random.Random) -> None:
    w = rng.choice([13.333, 10.0])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(w), Inches(7.5)
    c = _Ctx(prs, w, 7.5, rng)
    layouts = {l.name: l for l in prs.slide_layouts}
    n_slides = rng.randint(6, 10)
    del_kinds = rng.sample(list(_DELIBERATE) + list(_EVERY_SLIDE), rng.randint(2, 4))
    mis_kinds = rng.sample(list(_MISTAKES), rng.randint(2, 4))
    slide_names = [rng.choice(["Title Only", "Title and Content", "Blank"]) for _ in range(n_slides)]
    spots = list(range(n_slides))
    rng.shuffle(spots)
    wanted = [(k, "m") for k in mis_kinds] + [(k, "d") for k in del_kinds if k not in _EVERY_SLIDE]
    rng.shuffle(wanted)
    plan: dict[int, list] = {}
    for j, (kind, cls) in enumerate(wanted):
        idx = spots[j % n_slides]
        if kind == "spilled-title" and slide_names[idx] == "Blank":
            slide_names[idx] = "Title Only"
        plan.setdefault(idx, []).append((kind, cls))
    slides = [prs.slides.add_slide(layouts[nm]) for nm in slide_names]
    for i, (s, nm) in enumerate(zip(slides, slide_names)):
        _fill_slide(c, s, nm, i)
    n = 0
    for kind in del_kinds:
        if kind in _EVERY_SLIDE:
            n += 1
            _every_slide(c, slides, kind, f"deliberate-{kind}-{n}")
    for idx, items in plan.items():
        for kind, cls in items:
            n += 1
            if cls == "d":
                _DELIBERATE[kind](c, slides[idx], f"deliberate-{kind}-{n}")
            else:
                _MISTAKES[kind](c, slides[idx], f"mistake-{kind}-{n}")
    prs.save(str(path))


def build_training_decks(out_dir: Path, n_decks: int, seed: int) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    paths = []
    for i in range(n_decks):
        p = out_dir / f"train_{seed}_{i:03d}.pptx"
        _build_one(p, random.Random(rng.randrange(2**32)))
        paths.append(p)
    return paths


if __name__ == "__main__":
    out = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    print(f"{len(build_training_decks(out, count, seed))} decks written to {out}")
