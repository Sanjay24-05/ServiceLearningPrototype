"""FastAPI app: upload, progress, report, export, result, download."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from slideproof import intent
from slideproof.analysis import analyse
from slideproof.demo_deck import build_demo_deck
from slideproof.describe import describe
from slideproof.describe.layout_map import slide_map
from slideproof.describe.coverage import (INTENT_COVERAGE, cannot_check_sentence, checked_sentence,
                                          checks_run_items, not_checked_sentence, plural,
                                          unchecked_sentence)
from slideproof.verify import export_and_verify
from slideproof.web import compare
from slideproof.web.runs import Run, RunStore, startup_check

HERE = Path(__file__).parent
MAX_BYTES = 50 * 1024 * 1024
EXPIRED = "This check has expired. Check the file again."


def create_app(runs_root: Path, extra_hosts: tuple[str, ...] = ()) -> FastAPI:
    app = FastAPI()
    intent.available()  # load the model now, so the first check is not slower
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["127.0.0.1", "localhost", *extra_hosts])
    store = RunStore(Path(runs_root))
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.filters["plural"] = plural
    app.mount("/static", StaticFiles(directory=str(HERE / "static")),
              name="static")

    def page(request: Request, name: str, status: int = 200, **ctx):
        return templates.TemplateResponse(request, name, ctx,
                                          status_code=status)

    def error(request: Request, message: str, status: int = 400):
        return page(request, "error.html", status, message=message)

    def find(run_id: str) -> Run | None:
        try:
            return store.get(run_id)
        except KeyError:
            return None

    def items(run: Run, findings, intentional: bool = False) -> list[dict]:
        deck = run.analysis.deck
        out = []
        for f in findings:
            d = describe(f, deck, intentional)
            t = deck.slides[f.slide_index - 1].title_text
            title = (f'Slide {f.slide_index}, "{t}": {d.headline}' if t
                     else f"Slide {f.slide_index}: {d.headline}")
            out.append({"f": f, "d": d, "title": title,
                        "layout": slide_map(deck.slides[f.slide_index - 1], deck),
                        "preticked": not intentional})
        return out

    def change_logs(run: Run, ex) -> dict[int, list[str]]:
        """Change-log lines of the applied fixes, by slide number."""
        findings = {f.fix.fix_id: f for f in run.analysis.findings if f.fix}
        logs: dict[int, list[str]] = {}
        for fx in ex.applied:
            f = findings[fx.fix_id]
            line = describe(f, run.analysis.deck).change_log
            if line:
                logs.setdefault(f.slide_index, []).append(line)
        return logs

    def _start_analysis(run: Run, path: Path):
        def job(progress):
            run.analysis = analyse(path, run.dir, progress)
            return f"/runs/{run.id}/report"

        store.start(run, job)
        return RedirectResponse(f"/runs/{run.id}/progress", status_code=303)

    @app.get("/")
    def index(request: Request):
        return page(request, "index.html", problems=startup_check())

    @app.get("/about")
    def about(request: Request):
        return page(request, "about.html", checks=checks_run_items(),
                    not_checked=not_checked_sentence(),
                    accuracy=intent.accuracy(),
                    cannot_check=cannot_check_sentence())

    @app.post("/check")
    async def check(request: Request):
        # An empty file field arrives as a plain string, not an upload, so
        # validate by hand instead of letting FastAPI answer with a 422.
        file = (await request.form()).get("file")
        if not hasattr(file, "read") or not (file.filename or "").strip():
            return error(request, "Choose a PowerPoint file (.pptx) first.")
        name = Path((file.filename or "").replace("\\", "/")).name
        if not name.lower().endswith(".pptx"):
            return error(request, "Save as .pptx and try again.")
        size, chunks = 0, []
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                return error(request, "This file is larger than 50 MB.")
            chunks.append(chunk)
        run = store.create(name)
        path = run.dir / "original" / name
        try:
            path.write_bytes(b"".join(chunks))
        except OSError:
            return error(request, "This file name can't be used. Rename the "
                                  "file and try again.")

        return _start_analysis(run, path)

    @app.post("/demo")
    def demo(request: Request):
        run = store.create("demo_deck.pptx")
        folder = run.dir / "original"
        try:
            path, _ = build_demo_deck(folder)
        except Exception:
            return error(request, "The demo presentation could not be created.")
        return _start_analysis(run, path)

    @app.get("/runs/{run_id}/progress")
    def progress_page(request: Request, run_id: str):
        run = find(run_id)
        if run is None:
            return error(request, EXPIRED, 404)
        return page(request, "progress.html", run=run,
                    snap=store.snapshot(run))

    @app.get("/runs/{run_id}/status")
    def status(run_id: str):
        run = find(run_id)
        if run is None:
            return JSONResponse({"state": "error", "message": EXPIRED,
                                 "next": None}, status_code=404)
        return store.snapshot(run)

    @app.get("/runs/{run_id}/report")
    def report(request: Request, run_id: str):
        run = find(run_id)
        if run is None:
            return error(request, EXPIRED, 404)
        if run.analysis is None:
            return RedirectResponse(f"/runs/{run_id}/progress",
                                    status_code=303)
        rep = run.analysis.report
        return page(request, "report.html", run=run, rep=rep,
                    note=run.analysis.skipped_note,
                    intent_note=run.analysis.intent_note,
                    coverage=checked_sentence() + (f" {INTENT_COVERAGE}" if intent.available() else ""),
                    unchecked=unchecked_sentence(run.analysis.deck),
                    visible=items(run, rep.visible),
                    minor=items(run, rep.minor),
                    intentional=items(run, rep.intentional, True))

    @app.post("/runs/{run_id}/export")
    async def export(request: Request, run_id: str,
                     fix: list[str] = Form(default=[])):
        run = find(run_id)
        if run is None:
            return error(request, EXPIRED, 404)
        if run.analysis is None:
            return error(request, "This check is not finished yet.")
        if store.snapshot(run)["state"] == "working":
            return RedirectResponse(f"/runs/{run.id}/progress",
                                    status_code=303)
        if not fix:
            return page(request, "result.html", run=run, none_selected=True)
        original = run.analysis
        by_id = {f.fix.fix_id: f.fix for f in original.findings if f.fix}
        selected = [by_id[i] for i in dict.fromkeys(fix) if i in by_id]
        out = run.dir / "output" / f"{Path(run.filename).stem} (checked).pptx"

        def job(progress):
            run.compare = []
            compare.clear(run.dir)
            ex = export_and_verify(original, selected, out, run.dir, progress)
            progress("Preparing the before and after images…")
            run.compare = compare.build(run.dir, original, ex,
                                        change_logs(run, ex))
            run.export = ex
            return f"/runs/{run.id}/result"

        store.start(run, job, "Applying fixes…", clear_export=True)
        return RedirectResponse(f"/runs/{run.id}/progress", status_code=303)

    @app.get("/runs/{run_id}/result")
    def result(request: Request, run_id: str):
        run = find(run_id)
        if run is None:
            return error(request, EXPIRED, 404)
        ex = run.export
        if ex is None:
            return RedirectResponse(f"/runs/{run_id}/progress",
                                    status_code=303)
        findings = {f.fix.fix_id: f for f in run.analysis.findings if f.fix}
        deck = run.analysis.deck
        rolled = [(describe(findings[fx.fix_id], deck).headline, why)
                  for fx, why in ex.rolled_back]
        changes = [describe(findings[fx.fix_id], deck).change_log
                   for fx in ex.applied]
        return page(request, "result.html", run=run, ex=ex, rolled=rolled,
                    changes=[c for c in changes if c],
                    compare=[(f"/runs/{run.id}/compare/{n}.png", alt)
                             for n, alt in run.compare],
                    stem=Path(run.filename).stem, none_selected=False)

    @app.get("/runs/{run_id}/compare/{n}.png")
    def compare_image(request: Request, run_id: str, n: str):
        run = find(run_id)
        num = compare.parse_n(n)
        if run is None or run.export is None or num is None:
            return error(request, "This image is not available.", 404)
        if num not in {m for m, _ in run.compare}:
            return error(request, "This image is not available.", 404)
        path = compare.image_path(run.dir, num)
        if not path.is_file():
            return error(request, "This image is not available.", 404)
        # A later export of this run rewrites the image at the same URL.
        return FileResponse(path, media_type="image/png",
                            headers={"Cache-Control": "no-store"})

    @app.get("/runs/{run_id}/download")
    def download(request: Request, run_id: str):
        run = find(run_id)
        if run is None:
            return error(request, EXPIRED, 404)
        if run.export is None or run.export.output is None:
            return error(request, "There is no corrected copy to download.",
                         404)
        return FileResponse(
            run.export.output,
            media_type="application/vnd.openxmlformats-officedocument."
                       "presentationml.presentation",
            filename=f"{Path(run.filename).stem} (checked).pptx")

    return app
