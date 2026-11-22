"""Builds synthetic decks for training the intent model.

Usage: python tools/make_training_decks.py <out_dir> [n_decks=120] [seed=7]

Every deck carries 2-4 deliberate design patterns (elements named ``deliberate-<pattern>-<n>``)
and 2-4 mistakes (``mistake-<pattern>-<n>``). The label comes from the name prefix only.
Ordinary content is named ``content-...`` so candidates that involve no labelled element can be
dropped. Deliberate patterns sit in free bands away from the content; mistakes go anywhere.
Positions, sizes and colours come from overlapping ranges, and each pattern has variants so no
single feature separates the classes by construction.
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
from pptx.oxml.xmlchemy import OxmlElement
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
        self.slides: list = []
        self._imgs: dict = {}

    def u(self, a, b):
        return self.rng.uniform(a, b)

    def chance(self, p):
        return self.rng.random() < p

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

    def free_y(self, h):
        """Top of a box of height h inside the band under the content (content ends at 4.9 in)."""
        return self.u(5.15, max(5.15, 6.95 - h))

    def edge_xy(self, w, h, f, side=None, corner=False):
        """Top-left of a w x h box so that fraction f of it lies past one slide edge (or a corner)."""
        side = side or self.rng.choice("lrtb")
        ax, ay = self.u(0.5, max(0.5, self.w - w - 0.5)), self.u(1.5, max(1.5, self.h - h - 0.5))
        if corner:
            return ((-f * w if self.chance(0.5) else self.w - (1 - f) * w),
                    (-f * h if self.chance(0.5) else self.h - (1 - f) * h))
        return {"l": (-f * w, ay), "r": (self.w - (1 - f) * w, ay),
                "t": (ax, -f * h), "b": (ax, self.h - (1 - f) * h)}[side]


def _picture(c, s, x, y, w, h, name):
    p = s.shapes.add_picture(c.image(), Inches(x), Inches(y), Inches(w), Inches(h))
    p.name = name
    return p


def _rect(c, s, x, y, w, h, name, shape=MSO_SHAPE.RECTANGLE, text=None, rotate=False, alpha=None):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = c.colour()
    sh.line.fill.background()
    sh.name = name
    if text:
        sh.text_frame.text = text
    if rotate:
        sh.rotation = c.u(5, 15)
    if alpha:
        tag = OxmlElement("a:alpha")
        tag.set("val", str(alpha))
        sh._element.spPr.xpath("./a:solidFill/a:srgbClr")[0].append(tag)
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


def _blank(s):
    return s.shapes.title is None


# --- deliberate patterns: (ctx, slide, name). Placed in free bands, away from content. -------

def d_full_bleed(c, s, name):
    m = c.u(0.12, 0.4)
    _to_back(s, _picture(c, s, -m, -m, c.w + 2 * m, c.h + 2 * m, name))


def d_edge_banner(c, s, name):
    out_f = c.u(0.05, 0.3)
    if c.chance(0.35):  # side strip that touches one edge and not the full height
        w, h = c.u(0.3, 0.5), c.u(2, 4)
        left = c.chance(0.5)
        _rect(c, s, -w * out_f if left else c.w - w + w * out_f, c.u(1.0, c.h - h - 0.5), w, h, name)
        return
    h = c.u(0.5, 1.3)
    top = _blank(s) and c.chance(0.5)
    _rect(c, s, c.u(-0.2, 0.0), -h * out_f if top else c.h - h + h * out_f, c.w + 0.3, h, name,
          text="Section heading" if c.chance(0.6) else None)


def d_half_circle(c, s, name):
    d, f = c.u(1.5, 2.2), c.u(0.3, 0.7)
    side = c.rng.choice("lrbt" if _blank(s) else "lrb")
    if side in "lr":
        x, y = (-f * d if side == "l" else c.w - (1 - f) * d), c.free_y(d)
    else:
        x, y = c.u(1.6, c.w - d - 1.6), (-f * d if side == "t" else c.h - (1 - f) * d)
    _rect(c, s, x, y, d, d, name, MSO_SHAPE.OVAL, rotate=c.chance(0.2))


def d_corner_badge(c, s, name):
    d, f = c.u(0.5, 1.6), c.u(0.1, 0.4)
    if c.chance(0.3):  # one edge only
        x, y = c.u(1.6, c.w - d - 1.6), c.h - (1 - f) * d
    else:
        x = -f * d if c.chance(0.5) else c.w - (1 - f) * d
        y = -f * d if c.chance(0.5) else c.h - (1 - f) * d
    _rect(c, s, x, y, d, d, name, MSO_SHAPE.OVAL if c.chance(0.5) else MSO_SHAPE.RECTANGLE,
          text="1" if c.chance(0.5) else None, rotate=c.chance(0.2))


def d_stacked_icon(c, s, name):
    size, x = c.u(0.6, 1.5), c.u(0.6, c.w - 2.5)
    y = c.free_y(size)
    overhang = c.chance(0.3)
    for k in range(c.rng.randint(2, 3)):
        sz = size * (1 - 0.25 * k)
        off = (size - sz) / 2 if not overhang else (size - sz) + c.u(0, 0.2) * size
        _rect(c, s, x + off, y + off * (0.5 if overhang else 1), sz, sz, f"{name}-{k}",
              MSO_SHAPE.OVAL if k % 2 == 0 else MSO_SHAPE.RECTANGLE)


def d_caption_band(c, s, name):
    w, h = c.u(2.5, 6), c.u(1.4, 1.7)
    x, y = c.u(0.6, c.w - w - 0.6), c.free_y(h)
    _picture(c, s, x, y, w, h, name)
    bh = h * c.u(0.15, 0.3)
    ov = c.u(0.05, 0.25) if c.chance(0.3) else 0
    _rect(c, s, x - ov, y + h - bh, w + 2 * ov, bh, f"{name}-band", text="Photo caption")


def d_frame(c, s, name):
    w, h, pad = c.u(2.5, 5.5), c.u(1.1, 1.4), c.u(0.08, 0.25)
    x, y = c.u(0.9, c.w - w - 0.9), c.free_y(h + 2 * pad) + pad
    if c.chance(0.35):  # offset "shadow" frame: the photo overhangs it
        _rect(c, s, x + c.u(0.1, 0.25), y + c.u(0.1, 0.25), w, h, f"{name}-frame")
    else:
        _rect(c, s, x - pad, y - pad, w + 2 * pad, h + 2 * pad, f"{name}-frame")
    _picture(c, s, x, y, w, h, name)


def d_text_panel(c, s, name):
    w, h = c.u(3, 6), c.u(1.2, 1.7)
    x, y = c.u(0.6, c.w - w - 0.6), c.free_y(h)
    if c.chance(0.7):  # translucent highlights laid over the text
        _textbox(s, x, y, w, h, [c.rng.choice(_POINTS), c.rng.choice(_POINTS)], 18, name)
        n = c.rng.randint(3, 4)
        for k in range(n):  # side-by-side highlights, so they barely overlap each other
            m = c.u(-0.1, 0.15)
            _rect(c, s, x + k * w / n - m, y - m, w / n + 2 * m - 0.1, h + 2 * m, f"{name}-tint{k}",
                  alpha=c.rng.randint(25000, 45000))
        return
    # a filled text box laid on a larger filled panel
    _rect(c, s, x, y, w, h, f"{name}-panel")
    inset = c.u(0.15, 0.4)
    tb = _textbox(s, x + inset, y + inset, w - 2 * inset, h - 2 * inset,
                  [c.rng.choice(_POINTS), c.rng.choice(_POINTS)], 18, name)
    tb.fill.solid()
    tb.fill.fore_color.rgb = c.colour()


# --- mistake patterns -----------------------------------------------------------------------

def m_nudged_text(c, s, name):
    if c.chance(0.25):  # banner-sized box
        w, h = c.u(c.w * 0.6, c.w * 0.9), c.u(0.6, 1.0)
    else:
        w, h = c.u(3, 6), c.u(0.8, 1.6)
    x, y = c.edge_xy(w, h, c.u(0.1, 0.6), corner=c.chance(0.55))
    _textbox(s, x, y, w, h, [c.rng.choice(_POINTS)], 20, name)


def m_picture_over_text(c, s, name):
    w, h = c.u(4, 6.5), 2.0
    x, y = c.u(0.5, c.w - w - 0.5), c.u(1.8, c.h - 3.5)
    roll = c.rng.random()
    if roll < 0.3:  # picture pasted into the middle of a bullet list
        h = 2.3
        _textbox(s, x, y, w, h, c.rng.sample(_POINTS, 4), 18, f"{name}-text")
        pw, ph = c.u(1, 2.2), c.u(0.8, 1.4)
        _picture(c, s, x + c.u(0.4, w - pw - 0.4), y + c.u(0.1, h - ph - 0.1), pw, ph, name)
    elif roll < 0.55:  # small picture dropped onto another photo
        bw, bh = c.u(2.5, 5), c.u(1.8, 3)
        _picture(c, s, x, y, bw, bh, f"{name}-base")
        pw, ph = c.u(0.6, 0.8) * bw, c.u(0.5, 0.8) * bh
        _picture(c, s, x + c.u(0.05, bw - pw - 0.05), y + c.u(0.05, bh - ph - 0.05), pw, ph, name)
    else:
        _textbox(s, x, y, w, h, c.rng.sample(_POINTS, 3), 18, f"{name}-text")
        cov, a, b = c.u(0.1, 0.8), c.u(0, 0.5), c.u(0, 0.4)
        _picture(c, s, x - a, y - b, a + cov * w, b + h * c.u(0.6, 1.2), name)


def m_partly_off(c, s, name):
    roll = c.rng.random()
    if roll < 0.25:  # oversized picture dragged half off one edge
        w, h, f, kind = c.u(6, 10), c.u(3.5, 6), c.u(0.3, 0.5), "pic"
    elif roll < 0.5:  # small stray box
        w, h, f = c.u(0.5, 1.4), c.u(0.4, 1.0), c.u(0.05, 0.4)
        kind = "pic" if c.chance(0.5) else "rect"
    else:
        w, h, f = c.u(1.5, 5), c.u(1, 3.5), c.u(0.05, 0.4)
        kind = "pic" if c.chance(0.5) else "rect"
    x, y = c.edge_xy(w, h, f, corner=c.chance(0.55))
    rotate = kind == "rect" and c.chance(0.2)
    text = "Notes" if kind == "rect" and c.chance(0.6) else None

    def make(slide):
        if kind == "pic":
            _picture(c, slide, x, y, w, h, name)
        else:
            _rect(c, slide, x, y, w, h, name, text=text, rotate=rotate)

    make(s)
    if c.chance(0.5):  # pasted onto other slides too
        others = [o for o in c.slides if o is not s]
        for o in c.rng.sample(others, min(len(others), c.rng.randint(1, 3))):
            make(o)


def m_duplicate(c, s, name):
    w, h = c.u(1.0, 4), c.u(0.6, 2.5)
    x, y = c.u(0.6, c.w - w - 0.8), c.u(1.7, c.h - h - 0.8)
    dx, dy = c.u(0.05, 0.3), c.u(0.05, 0.3)
    shrink = c.chance(0.4)  # the copy ends up fully inside the original
    cw, ch = (w - 2 * dx, h - 2 * dy) if shrink else (w, h)
    if c.chance(0.5):
        _picture(c, s, x, y, w, h, name)
        _picture(c, s, x + dx, y + dy, cw, ch, f"{name}-copy")
    else:
        label = "Key point" if c.chance(0.4) else None
        _rect(c, s, x, y, w, h, name, text=label)
        _rect(c, s, x + dx, y + dy, cw, ch, f"{name}-copy", text=label)


def m_spill_title(c, s, name):
    t = s.shapes.title
    tw = c.u(2, 5)
    cx = (t.left + t.width / 2) / _EMU + c.u(-0.8, 0.8)
    top = t.top / _EMU + t.height / _EMU * c.u(0.2, 0.7)
    _picture(c, s, cx - tw / 2, top, tw, c.u(1.2, 3.5), name)


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
PATTERN_KINDS = list(_DELIBERATE) + list(_EVERY_SLIDE) + list(_MISTAKES)


def _subset(c, slides):
    """Nearly every slide: a repeated element is skipped on a few (e.g. a title or closing slide)."""
    keep = [s for s in slides if c.chance(0.8)]
    return keep if len(keep) >= 3 else slides


def _every_slide(c, slides, kind, name):
    if kind == "corner-logo":
        d, f = c.u(0.6, 1.2), c.u(0.05, 0.25)
        x = -f * d if c.chance(0.5) else c.w - (1 - f) * d
        y = -f * d if c.chance(0.5) else c.h - (1 - f) * d
        for s in _subset(c, slides):
            _picture(c, s, x, y, d, d, name)
    else:
        h = c.u(0.3, 0.6)
        out = h * c.u(0.05, 0.3)
        col = c.colour()
        label = "Campus project 2026" if c.chance(0.5) else None
        for s in _subset(c, slides):
            _rect(c, s, 0, c.h - h + out, c.w, h, name, text=label).fill.fore_color.rgb = col


def _fill_slide(c, s, layout_name, i):
    rng = c.rng
    title = s.shapes.title
    if title is not None:
        title.name = "content-title"
        title.text = f"{rng.choice(_TOPICS)}: part {i + 1}"
        # clear of the corner logos and badges (they reach at most 1.5 in inwards)
        title.left, title.top, title.width, title.height = Inches(1.5), Inches(0.35), Inches(c.w - 3), Inches(1.2)
    lines = rng.sample(_POINTS, rng.randint(2, 4))
    half = c.w * 0.5
    if layout_name == "Title and Content":
        body = s.placeholders[1]
        body.name = "content-text"
        body.left, body.top, body.width, body.height = Inches(0.6), Inches(1.7), Inches(half), Inches(3.2)
        body.text_frame.text = lines[0]
        for t in lines[1:]:
            body.text_frame.add_paragraph().text = t
    else:
        _textbox(s, 0.6, 1.7, half, 3.2, lines, rng.choice([18, 20, 24]), "content-text")
    right = half + 1.0
    roll = rng.random()
    if roll < 0.5:
        _picture(c, s, right, 1.9, c.w - right - 0.5, 3.0, "content-photo")
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
    del_kinds = rng.sample(list(_DELIBERATE) + list(_EVERY_SLIDE), rng.randint(2, 4))
    mis_kinds = rng.sample(list(_MISTAKES), rng.randint(2, 4))
    wanted = [(k, "m") for k in mis_kinds] + [(k, "d") for k in del_kinds if k not in _EVERY_SLIDE]
    rng.shuffle(wanted)
    n_slides = max(rng.randint(6, 10), len(wanted))
    slide_names = [rng.choice(["Title Only", "Title and Content", "Blank"]) for _ in range(n_slides)]
    spots = list(range(n_slides))
    rng.shuffle(spots)
    plan: dict[int, tuple] = {}
    for j, (kind, cls) in enumerate(wanted):  # at most one pattern per slide
        idx = spots[j]
        if kind == "spilled-title" and slide_names[idx] == "Blank":
            slide_names[idx] = "Title Only"
        plan[idx] = (kind, cls)
    slides = [prs.slides.add_slide(layouts[nm]) for nm in slide_names]
    c.slides = slides
    for i, (s, nm) in enumerate(zip(slides, slide_names)):
        _fill_slide(c, s, nm, i)
    n = 0
    for kind in del_kinds:
        if kind in _EVERY_SLIDE:
            n += 1
            _every_slide(c, slides, kind, f"deliberate-{kind}-{n}")
    for idx, (kind, cls) in plan.items():
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
