"""Builds realistic test decks. Usage: python make_decks.py <out_dir>"""
import io, sys, copy, json
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image, ImageDraw

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
EXPECT = {}

def img(w, h, seed=0):
    im = Image.new("RGB", (w, h), (220, 235, 250)); d = ImageDraw.Draw(im)
    d.ellipse([w*0.2, h*0.2, w*0.8, h*0.8], fill=(250, 200, 120), outline=(80, 60, 40), width=max(2, w//150))
    for x in range(0, w, max(8, w//10)): d.line([(x, 0), (x, h)], fill=(150, 170, 210), width=1)
    b = io.BytesIO(); im.save(b, "PNG"); b.seek(0); return b

def new(w=13.333, h=7.5):
    p = Presentation(); p.slide_width, p.slide_height = Inches(w), Inches(h); return p

def layout(p, name): return [l for l in p.slide_layouts if l.name == name][0]

def bullets(slide, x, y, w, h, lines, size=24):
    tf = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, t in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); para.text = t; para.font.size = Pt(size)
    return tf

# 1. Clean student deck: 12 slides, nothing wrong
p = new()
s = p.slides.add_slide(layout(p, "Title Slide")); s.shapes.title.text = "Water Conservation in Our Campus"; s.placeholders[1].text = "Environmental Studies - Group 4"
for i in range(1, 12):
    s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = f"Section {i}: Findings"
    bullets(s, 0.6, 1.6, 6.2, 4.8, [f"Observation {j} for section {i}" for j in range(1, 5)])
    if i % 2: s.shapes.add_picture(img(1200, 900, i), Inches(7.2), Inches(1.6), Inches(5.4), Inches(4.05))
p.save(OUT / "clean_student_deck.pptx"); EXPECT["clean_student_deck.pptx"] = []

# 2. Charts, tables, groups, rotation, crop, hidden slide (mostly clean, with 3 planted errors)
p = new()
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Quarterly numbers"
cd = CategoryChartData(); cd.categories = ["Q1", "Q2", "Q3", "Q4"]; cd.add_series("Litres saved", (120, 150, 180, 210))
s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.6), Inches(6), Inches(4.5), cd)
t = s.shapes.add_table(3, 3, Inches(7), Inches(1.6), Inches(5.6), Inches(2)).table
for r in range(3):
    for c in range(3): t.cell(r, c).text = f"R{r}C{c}"
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Grouped diagram"
g = s.shapes.add_group_shape()
for k in range(3):
    sh = g.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8 + 4*k), Inches(2.5), Inches(3.2), Inches(1.5)); sh.text = f"Step {k+1}"
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Rotated label (planted: sticks out)"
r = s.shapes.add_textbox(Inches(11.2), Inches(3), Inches(4), Inches(1)); r.text_frame.text = "Rotated note that runs off"; r.rotation = 20; r.name = "rotated-note"
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Cropped photo (correct proportions)"
pic = s.shapes.add_picture(img(1600, 900), Inches(1), Inches(1.6), Inches(6), Inches(4.5)); pic.crop_left = pic.crop_right = 0.125
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Slight stretch 3% (fine) and 9% (planted minor)"
s.shapes.add_picture(img(800, 600), Inches(0.6), Inches(1.6), Inches(5.15), Inches(3.75))
q = s.shapes.add_picture(img(800, 600), Inches(6.8), Inches(1.6), Inches(5.45), Inches(3.75)); q.name = "photo-9pc"
s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = "Hidden backup slide"
bullets(s, 0.6, 1.6, 6, 3, ["Only for questions"])
s._element.set("show", "0")
p.save(OUT / "constructs_deck.pptx")
EXPECT["constructs_deck.pptx"] = [("C1", 3, "rotated-note"), ("C4", 5, "photo-9pc")]

# 3. 4:3 lecture deck with one real off-slide picture
p = new(10, 7.5)
for i in range(6):
    s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = f"Lecture point {i+1}"
    bullets(s, 0.5, 1.6, 9, 4, ["Key idea", "Example", "Question for the class"])
s = p.slides[4]; x = s.shapes.add_picture(img(800, 600), Inches(7.5), Inches(4), Inches(4), Inches(3)); x.name = "diagram-off"
p.save(OUT / "lecture_4x3.pptx"); EXPECT["lecture_4x3.pptx"] = [("C1", 5, "diagram-off")]

# 4. Long 40-slide deck, clean
p = new()
for i in range(40):
    s = p.slides.add_slide(layout(p, "Title Only")); s.shapes.title.text = f"Topic {i+1}"
    bullets(s, 0.6, 1.6, 12, 4.5, ["Point A", "Point B", "Point C"])
p.save(OUT / "long_40_slides.pptx"); EXPECT["long_40_slides.pptx"] = []

# 5. Linked picture (image stored outside the file) + full-bleed background, clean otherwise
p = new()
s1 = p.slides.add_slide(layout(p, "Title Only")); s1.shapes.title.text = "Linked image"
lp = s1.shapes.add_picture(img(800, 600), Inches(1), Inches(1.6), Inches(5), Inches(3.75))
s2 = p.slides.add_slide(layout(p, "Blank"))
s2.shapes.add_picture(img(1920, 1080), 0, 0, p.slide_width, p.slide_height)
bullets(s2, 1, 2.5, 8, 2, ["Thank you for listening"], size=40)
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
blip = lp._element.blipFill.blip
rid = s1.part.relate_to("file:///C:/missing/photo.png", RT.IMAGE, is_external=True)
blip.attrib.pop(R + "embed"); blip.set(R + "link", rid)
p.save(OUT / "linked_and_background.pptx"); EXPECT["linked_and_background.pptx"] = []

(OUT / "expected.json").write_text(json.dumps(EXPECT, indent=1))
print("built", sorted(EXPECT))
