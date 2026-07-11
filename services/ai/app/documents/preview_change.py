"""Diff technique avant écriture (texte/code/markdown)."""

from __future__ import annotations

import difflib
import html
import mimetypes
from pathlib import Path

from app.documents.extractor import is_binary_document
from app.i18n import t
from app.versions import normalize_relative_path

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".tiff", ".tif"}


def _is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTS


def _is_binary_for_diff(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    return is_binary_document(path.name, mime) or _is_image_file(path)


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def build_line_diff_html(old_text: str, new_text: str) -> str:
    """Diff ligne par ligne avec classes wp-diff-add/del/common."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    parts: list[str] = ['<div class="wp-diff">']
    for line in difflib.ndiff(old_lines, new_lines):
        if not line:
            continue
        code = line[:2]
        content = html.escape(line[2:].rstrip("\n\r"))
        if code == "+ ":
            parts.append(f'<div class="wp-diff-add">{content}</div>')
        elif code == "- ":
            parts.append(f'<div class="wp-diff-del">{content}</div>')
        elif code == "  ":
            parts.append(f'<div class="wp-diff-common">{content}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def preview_change(
    *,
    workspace_data_dir: Path,
    project_root: Path,
    file_path: str,
    proposed_content: str,
    locale: str = "fr",
) -> dict[str, object]:
    ws_dir = workspace_data_dir.expanduser().resolve()
    root = project_root.expanduser().resolve()
    normalized = normalize_relative_path(file_path)
    target = (root / normalized).resolve()

    if not target.is_relative_to(root):
        raise ValueError("Path outside workspace")

    is_new = not target.is_file()
    is_binary = False if is_new else _is_binary_for_diff(target)

    old_size = target.stat().st_size if target.is_file() else 0
    new_size = len(proposed_content.encode("utf-8"))

    if is_binary:
        return {
            "is_new": is_new,
            "is_binary": True,
            "diff_html": "",
            "message": t(locale, "preview_change.binary_unavailable"),
            "old_size": old_size,
            "new_size": new_size,
        }

    old_text = "" if is_new else _read_text_file(target)
    diff_html = build_line_diff_html(old_text, proposed_content)
    return {
        "is_new": is_new,
        "is_binary": False,
        "diff_html": diff_html,
        "message": "",
        "old_size": old_size,
        "new_size": new_size,
    }
