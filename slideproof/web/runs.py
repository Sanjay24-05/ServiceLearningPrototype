"""In-memory run store, background jobs and startup checks."""
from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from slideproof.analysis import Analysis
from slideproof.loader import DeckError
from slideproof.render.soffice import find_soffice
from slideproof.verify import ExportResult

GENERIC_ERROR = ("Something went wrong while checking this file. Try saving it "
                 "again in PowerPoint and checking it again.")


@dataclass
class Run:
    id: str
    filename: str
    dir: Path
    state: Literal["working", "done", "error"] = "working"
    message: str = "Starting…"
    next_url: str | None = None
    analysis: Analysis | None = None
    export: ExportResult | None = None
    error: str | None = None


class RunStore:
    def __init__(self, root: Path):
        self.root = root
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Run:
        run_id = uuid.uuid4().hex
        d = self.root / run_id
        (d / "original").mkdir(parents=True, exist_ok=True)
        (d / "output").mkdir(parents=True, exist_ok=True)
        run = Run(run_id, filename, d)
        with self._lock:
            self._runs[run_id] = run
        return run

    def get(self, run_id: str) -> Run:
        with self._lock:
            return self._runs[run_id]

    def start(self, run: Run, fn: Callable[[Callable[[str], None]], str],
              message: str = "Starting…") -> None:
        """Run fn(progress) in a daemon thread; fn returns the next URL."""
        with self._lock:
            run.state, run.message, run.next_url, run.error = (
                "working", message, None, None)

        def progress(msg: str) -> None:
            with self._lock:
                run.message = msg

        def work() -> None:
            try:
                nxt = fn(progress)
            except DeckError as e:
                self._fail(run, str(e))
            except Exception:
                self._fail(run, GENERIC_ERROR)
            else:
                with self._lock:
                    run.state, run.next_url = "done", nxt

        threading.Thread(target=work, daemon=True).start()

    def _fail(self, run: Run, msg: str) -> None:
        with self._lock:
            run.state, run.error, run.message = "error", msg, msg

    def snapshot(self, run: Run) -> dict:
        with self._lock:
            return {"state": run.state, "message": run.message,
                    "next": run.next_url}


_FONTS = (("Carlito", "Carlito"), ("Caladea", "Caladea"),
          ("LiberationSans", "Liberation Sans"),
          ("LiberationSerif", "Liberation Serif"))


def _font_dirs() -> list[Path]:
    dirs = [Path(r"C:\Windows\Fonts")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return dirs


def startup_check() -> list[str]:
    problems: list[str] = []
    if find_soffice() is None:
        problems.append(
            "LibreOffice was not found. Text overflow and contrast checks will "
            "be skipped. Install LibreOffice 7.6 or later, or set SOFFICE_PATH.")
    names: list[str] = []
    for d in _font_dirs():
        try:
            names += [p.name for p in d.iterdir()]
        except OSError:
            pass
    for prefix, label in _FONTS:
        if not any(n.lower().startswith(prefix.lower()) for n in names):
            problems.append(f"The {label} font is not installed; text "
                            "measurements may be less accurate.")
    return problems
