"""Plain-text "what a screen reader announces" transcript of a page.

Built from Playwright's accessibility snapshot, flattened depth-first in
document order. Used by tests/test_transcript.py to compare against golden
files, so most of the manual NVDA checklist is covered on every change.
"""
from __future__ import annotations

import re

_RUN_ID = re.compile(r"\b[0-9a-f]{16,}\b")
_SKIP = {"generic", "none", "presentation", "document", "WebArea", "RootWebArea",
         "list", "listitem", "paragraph", "main", "banner", "contentinfo",
         "navigation", "form", "region", "StaticText", "LineBreak"}
_TEXT_ROLES = {"text", "StaticText"}


def _clean(s) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return _RUN_ID.sub("<run>", s)


def flatten(node):
    """Depth-first, document-order walk of an accessibility snapshot node."""
    if node is None:
        return
    yield node
    for child in node.get("children") or []:
        yield from flatten(child)


def _line(node) -> str | None:
    role = node.get("role", "")
    name = _clean(node.get("name"))
    if role == "heading":
        return f"heading level {node.get('level', '?')}: {name}" if name else None
    if role == "checkbox":
        state = "checked" if node.get("checked") in (True, "true") else "not checked"
        return f"checkbox {state}: {name}"
    if role in {"button", "link", "status", "alert", "group"}:
        return f"{role}: {name}" if name else None
    if role in {"textbox", "file upload"}:
        return f"file upload: {name}" if name else None
    if role in _TEXT_ROLES:
        return f"text: {name}" if name else None
    return None


def transcript(page) -> list[str]:
    # page.accessibility is deprecated in newer Playwright; this relies on the
    # pinned 1.47.
    snap = page.accessibility.snapshot(interesting_only=True)
    active = page.evaluate(
        "(() => { const e = document.activeElement;"
        " return [e.tagName, (e.textContent || '').trim().slice(0, 80)]; })()")
    # Edge reports <input type=file> as a button; say "file upload" instead.
    file_names = {_clean(n) for n in page.evaluate(
        "[...document.querySelectorAll('input[type=file]')]"
        ".map(i => i.labels && i.labels[0] ? i.labels[0].textContent : '')")}

    def describe_node(node):
        if node.get("role") in {"button", "textbox"} and _clean(node.get("name")) in file_names:
            return {**node, "role": "file upload"}
        return node

    focused = next((n for n in flatten(snap) if n.get("focused")), None)
    if focused is not None:
        focused = describe_node(focused)
        lines = [f"focus: {focused.get('role')} {_clean(focused.get('name'))}"]
    elif active[0] == "BODY":
        lines = ["focus: page body (nothing focused)"]
    else:
        lines = [f"focus: {active[0].lower()} {_clean(active[1])}"]
    for node in flatten(snap):
        line = _line(describe_node(node))
        if line:
            lines.append(line)
    return lines
