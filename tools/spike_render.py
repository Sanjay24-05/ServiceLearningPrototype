"""M0 spike: time a LibreOffice render and dump spans.

Usage: python tools/spike_render.py <deck.pptx>
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation  # noqa: E402

from slideproof.render.pdf import read_pdf  # noqa: E402
from slideproof.render.pipeline import slide_size  # noqa: E402
from slideproof.render.soffice import convert_to_pdf, find_soffice  # noqa: E402


def main(deck: Path) -> int:
    soffice = find_soffice()
    if soffice is None:
        print("LibreOffice not found (set SOFFICE_PATH or install it)")
        return 1
    with tempfile.TemporaryDirectory() as td:
        run = Path(td)
        t0 = time.perf_counter()
        pdf = convert_to_pdf(soffice, deck, run / "pdf", run / "lo-profile")
        print(f"conversion: {time.perf_counter() - t0:.2f}s")
        w, h = slide_size(deck)
        t1 = time.perf_counter()
        pages = read_pdf(pdf, run / "png", w, h)
        print(f"read_pdf: {time.perf_counter() - t1:.2f}s")
        print(f"pages: {len(pages)} (slides: {len(Presentation(str(deck)).slides)})")
        for p in pages:
            print(f"slide {p.page_index + 1}: {len(p.spans)} spans")
            for sp in p.spans[:3]:
                b = sp.bbox
                e = 914400
                print(f"   {sp.text[:40]!r} bbox(in)=({b.x/e:.2f},{b.y/e:.2f},"
                      f"{b.w/e:.2f},{b.h/e:.2f}) font={sp.font} "
                      f"size={sp.size_pt:.1f} rgb={sp.rgb}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
