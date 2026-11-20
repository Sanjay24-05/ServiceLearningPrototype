"""Locate and drive headless LibreOffice."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_WINDOWS_PATHS = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)


class RenderError(Exception):
    pass


def find_soffice() -> Path | None:
    env = os.environ.get("SOFFICE_PATH")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    found = shutil.which("soffice")
    if found:
        return Path(found)
    for p in _WINDOWS_PATHS:
        if p.is_file():
            return p
    return None


def convert_to_pdf(soffice: Path, pptx: Path, outdir: Path, profile_dir: Path,
                   timeout: int = 120) -> Path:
    """Convert `pptx` to PDF. Raises RenderError on failure; lets
    subprocess.TimeoutExpired propagate on timeout."""
    outdir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(soffice), "--headless", "--norestore",
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--convert-to", "pdf", "--outdir", str(outdir), str(pptx),
    ]
    log_path = outdir / "soffice.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                    stderr=subprocess.STDOUT, creationflags=flags)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                raise
    except OSError as e:
        raise RenderError(f"could not start LibreOffice: {e}") from e
    if proc.returncode != 0:
        raise RenderError(f"LibreOffice exited with code {proc.returncode}: "
                          f"{_log_tail(log_path)}")
    out = outdir / (pptx.stem + ".pdf")
    if not out.is_file():
        raise RenderError(f"LibreOffice produced no PDF: {_log_tail(log_path)}")
    return out


def _log_tail(path: Path, n: int = 500) -> str:
    try:
        return path.read_text(errors="replace")[-n:].strip()
    except OSError:
        return ""


def _kill_tree(proc) -> None:
    """Kill soffice and its soffice.bin child so the profile is released."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
