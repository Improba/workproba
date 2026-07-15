"""Diff technique avant écriture (texte/code/markdown et Office)."""

from __future__ import annotations

import difflib
import html
import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.documents.extractor import is_binary_document
from app.documents.preview import (
    _render_docx_html,
    _render_pdf_html,
    _render_xlsx_html,
)
from app.documents.writer import build_docx_bytes, build_pdf_bytes, build_xlsx_bytes
from app.i18n import t
from app.versions import normalize_relative_path

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".tiff", ".tif"}
_OFFICE_EXTS = {".docx", ".xlsx", ".pdf"}
_OFFICE_WRITE_TOOLS = {"write_docx", "write_xlsx", "write_pdf"}


def _is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_EXTS


def _is_office_file(path: Path) -> bool:
    return path.suffix.lower() in _OFFICE_EXTS


def _is_binary_for_diff(path: Path) -> bool:
    mime, _ = mimetypes.guess_type(path.name)
    return is_binary_document(path.name, mime) or _is_image_file(path)


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class _HtmlToPlainText(HTMLParser):
    """Convertit un aperçu HTML Office en texte pour le diff ligne à ligne."""

    _BLOCK_TAGS = frozenset(
        {"p", "div", "h1", "h2", "h3", "h4", "li", "tr", "br", "section", "ul", "ol"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")
        if tag == "td":
            self._parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS or tag in {"table", "thead", "tbody"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _html_to_plain_text(html_content: str) -> str:
    parser = _HtmlToPlainText()
    parser.feed(html_content)
    parser.close()
    return parser.get_text()


def _render_office_bytes_to_text(path: Path, content: bytes) -> str:
    ext = path.suffix.lower()
    if ext == ".docx":
        rendered = _render_docx_html(content)
    elif ext == ".xlsx":
        rendered = _render_xlsx_html(content)
    elif ext == ".pdf":
        rendered = _render_pdf_html(content)
    else:
        return ""
    return _html_to_plain_text(rendered)


def _build_proposed_office_bytes(tool_name: str, tool_args: dict[str, Any]) -> bytes:
    if tool_name == "write_docx":
        title = tool_args.get("title")
        paragraphs = tool_args.get("paragraphs")
        return build_docx_bytes(
            title=str(title) if isinstance(title, str) and title else None,
            paragraphs=paragraphs if isinstance(paragraphs, list) else None,
        )
    if tool_name == "write_xlsx":
        sheets = tool_args.get("sheets")
        return build_xlsx_bytes(
            sheets=sheets if isinstance(sheets, list) else None,
        )
    if tool_name == "write_pdf":
        title = tool_args.get("title")
        sections = tool_args.get("sections")
        return build_pdf_bytes(
            title=str(title) if isinstance(title, str) and title else None,
            sections=sections if isinstance(sections, list) else None,
        )
    raise ValueError(f"Unsupported office tool: {tool_name}")


def _office_preview_diff(
    *,
    target: Path,
    tool_name: str,
    tool_args: dict[str, Any],
    is_new: bool,
) -> dict[str, object]:
    old_bytes = b"" if is_new else target.read_bytes()
    new_bytes = _build_proposed_office_bytes(tool_name, tool_args)
    old_text = _render_office_bytes_to_text(target, old_bytes)
    new_text = _render_office_bytes_to_text(target, new_bytes)
    return {
        "is_new": is_new,
        "is_binary": False,
        "diff_html": build_line_diff_html(old_text, new_text),
        "message": "",
        "old_size": len(old_bytes),
        "new_size": len(new_bytes),
    }


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
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    locale: str = "fr",
) -> dict[str, object]:
    ws_dir = workspace_data_dir.expanduser().resolve()
    root = project_root.expanduser().resolve()
    normalized = normalize_relative_path(file_path)
    target = (root / normalized).resolve()

    if not target.is_relative_to(root):
        raise ValueError("Path outside workspace")

    is_new = not target.is_file()
    office_tool = tool_name if tool_name in _OFFICE_WRITE_TOOLS else None
    if office_tool is None and tool_args and _is_office_file(target):
        ext = target.suffix.lower()
        office_tool = {
            ".docx": "write_docx",
            ".xlsx": "write_xlsx",
            ".pdf": "write_pdf",
        }.get(ext)

    if office_tool and tool_args:
        return _office_preview_diff(
            target=target,
            tool_name=office_tool,
            tool_args=tool_args,
            is_new=is_new,
        )

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
