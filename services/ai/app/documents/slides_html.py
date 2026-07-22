"""Rendu HTML/CSS des slides sémantiques (source de vérité visuelle preview / PDF)."""

from __future__ import annotations

import html
from typing import Any

from app.documents.slides_schema import normalize_deck

_THEME_CSS: dict[str, dict[str, str]] = {
    "improba": {
        "bg": "#faf8f4",
        "surface": "#ffffff",
        "text": "#203d52",
        "muted": "#5a6e7d",
        "accent": "#c4a35a",
    },
    "light": {
        "bg": "#ffffff",
        "surface": "#f7f4ef",
        "text": "#1c1917",
        "muted": "#57534e",
        "accent": "#c4a35a",
    },
    "dark": {
        "bg": "#1c1917",
        "surface": "#292524",
        "text": "#f5f5f4",
        "muted": "#a8a29e",
        "accent": "#d4af37",
    },
}


def render_deck_html(
    slides: list[dict[str, Any]] | None,
    *,
    theme: str = "improba",
) -> str:
    """Produit un document HTML 16:9 (un div .wp-slide par slide)."""
    theme_key = (theme or "improba").strip().lower()
    if theme_key not in _THEME_CSS:
        theme_key = "improba"
    colors = _THEME_CSS[theme_key]
    normalized = normalize_deck(slides, theme=theme_key)

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>",
        f"<style>{_css(colors)}</style></head><body>",
    ]
    for index, slide in enumerate(normalized, start=1):
        parts.append(_render_slide(slide, index=index))
    parts.append("</body></html>")
    return "\n".join(parts)


def _css(colors: dict[str, str]) -> str:
    return f"""
@page {{ size: 13.333in 7.5in; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0;
  font-family: Calibri, 'Segoe UI', sans-serif;
  background: {colors['bg']}; color: {colors['text']};
}}
.wp-slide {{
  width: 13.333in; height: 7.5in; overflow: hidden;
  padding: 0.7in 0.9in 0.7in 1.05in;
  position: relative; page-break-after: always; break-after: page;
  background: {colors['bg']};
  border-left: 0.18in solid {colors['accent']};
}}
.wp-slide__eyebrow {{
  font-size: 14pt; color: {colors['accent']}; font-weight: 600;
  margin: 0 0 0.25in; text-transform: uppercase; letter-spacing: 0.04em;
}}
.wp-slide__title {{
  font-size: 36pt; font-weight: 700; margin: 0 0 0.2in; line-height: 1.15;
}}
.wp-slide__title--hero {{ font-size: 44pt; margin-top: 1.6in; }}
.wp-slide__lede {{
  font-size: 18pt; color: {colors['muted']}; margin: 0 0 0.35in; line-height: 1.4;
}}
.wp-slide__list {{
  margin: 0; padding-left: 0.35in; font-size: 20pt; line-height: 1.45;
}}
.wp-slide__list li {{ margin-bottom: 0.18in; }}
.wp-slide__grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.45in; margin-top: 0.35in;
}}
.wp-slide__col-title {{
  font-size: 16pt; color: {colors['accent']}; font-weight: 700; margin: 0 0 0.2in;
}}
.wp-kpi {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(2.2in, 1fr));
  gap: 0.3in; margin-top: 0.5in;
}}
.wp-kpi__card {{
  background: {colors['surface']}; border-top: 0.08in solid {colors['accent']};
  padding: 0.35in 0.25in; text-align: center; min-height: 2.2in;
}}
.wp-kpi__value {{ font-size: 28pt; font-weight: 700; margin: 0.4in 0 0.15in; }}
.wp-kpi__label {{ font-size: 13pt; color: {colors['muted']}; }}
.wp-quote {{
  font-size: 26pt; text-align: center; margin: 1.5in 0.8in 0.4in; line-height: 1.35;
}}
.wp-quote__attr {{
  text-align: center; color: {colors['muted']}; font-size: 16pt;
}}
.wp-accent-bar {{
  width: 1.8in; height: 0.07in; background: {colors['accent']}; margin: 0.15in 0 0.35in;
}}
"""


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _render_slide(slide: dict[str, Any], *, index: int) -> str:
    grammar = str(slide.get("grammar") or "sequence")
    hierarchy = slide.get("hierarchy") if isinstance(slide.get("hierarchy"), dict) else {}
    primary = str(hierarchy.get("primary") or "").strip()
    secondary = hierarchy.get("secondary") if isinstance(hierarchy.get("secondary"), list) else []
    secondary = [str(s) for s in secondary if str(s).strip()]
    tertiary = hierarchy.get("tertiary") if isinstance(hierarchy.get("tertiary"), list) else []
    tertiary = [str(s) for s in tertiary if str(s).strip()]
    bullets = secondary + tertiary
    visual = slide.get("visual") if isinstance(slide.get("visual"), dict) else {}
    vtype = str(visual.get("type") or "none")
    items = visual.get("items") if isinstance(visual.get("items"), list) else []
    message = str(slide.get("message") or "").strip()

    body: list[str] = [
        f"<div class='wp-slide wp-slide--{_esc(grammar)}' data-slide='{index}'>"
    ]
    if message and grammar != "hero":
        body.append(f"<p class='wp-slide__eyebrow'>{_esc(message)}</p>")

    if grammar == "hero":
        body.append(
            f"<h1 class='wp-slide__title wp-slide__title--hero'>{_esc(primary or 'Présentation')}</h1>"
        )
        if bullets:
            body.append(f"<p class='wp-slide__lede'>{_esc(bullets[0])}</p>")
        if len(bullets) > 1:
            body.append(_ul(bullets[1:]))
    elif grammar in {"split", "comparison"}:
        if primary:
            body.append(f"<h1 class='wp-slide__title'>{_esc(primary)}</h1>")
            body.append("<div class='wp-accent-bar'></div>")
        left_lines, right_lines, left_t, right_t = _split_items(items, bullets)
        body.append("<div class='wp-slide__grid'>")
        body.append("<div>")
        if left_t:
            body.append(f"<p class='wp-slide__col-title'>{_esc(left_t)}</p>")
        body.append(_ul(left_lines))
        body.append("</div><div>")
        if right_t:
            body.append(f"<p class='wp-slide__col-title'>{_esc(right_t)}</p>")
        body.append(_ul(right_lines))
        body.append("</div></div>")
    elif grammar == "dashboard" or vtype == "kpi_row":
        if primary:
            body.append(f"<h1 class='wp-slide__title'>{_esc(primary)}</h1>")
            body.append("<div class='wp-accent-bar'></div>")
        cards = _kpi_cards(items, bullets)
        body.append("<div class='wp-kpi'>")
        for card in cards:
            body.append(
                "<div class='wp-kpi__card'>"
                f"<p class='wp-kpi__value'>{_esc(card['value'])}</p>"
                f"<p class='wp-kpi__label'>{_esc(card['label'])}</p>"
                "</div>"
            )
        body.append("</div>")
    elif grammar == "editorial" or vtype == "quote":
        body.append(f"<p class='wp-quote'>« {_esc(primary)} »</p>")
        if secondary:
            body.append(f"<p class='wp-quote__attr'>- {_esc(secondary[0])}</p>")
    elif grammar in {"sequence", "diagram"}:
        if primary:
            body.append(f"<h1 class='wp-slide__title'>{_esc(primary)}</h1>")
            body.append("<div class='wp-accent-bar'></div>")
        steps = bullets or _lines_from_items(items)
        body.append(_ul(steps))
    else:
        if primary:
            body.append(f"<h1 class='wp-slide__title'>{_esc(primary)}</h1>")
        body.append(_ul(bullets))

    body.append("</div>")
    return "\n".join(body)


def _ul(lines: list[str]) -> str:
    if not lines:
        return ""
    items = "".join(f"<li>{_esc(line)}</li>" for line in lines)
    return f"<ul class='wp-slide__list'>{items}</ul>"


def _split_items(
    items: list[Any], secondary: list[str]
) -> tuple[list[str], list[str], str, str]:
    left_t = right_t = ""
    left: list[str] = []
    right: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        side = str(item.get("side") or "").lower()
        title = str(item.get("title") or "").strip()
        lines = item.get("lines") if isinstance(item.get("lines"), list) else []
        lines_s = [str(x).strip() for x in lines if str(x).strip()]
        if side == "right":
            right_t = title or right_t
            right.extend(lines_s)
        else:
            left_t = title or left_t
            left.extend(lines_s)
    if not left and not right and secondary:
        mid = max(1, len(secondary) // 2)
        left, right = secondary[:mid], secondary[mid:]
    return left, right, left_t, right_t


def _kpi_cards(items: list[Any], secondary: list[str]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            cards.append(
                {
                    "label": str(item.get("label") or "").strip(),
                    "value": str(item.get("value") or "-").strip(),
                }
            )
        if len(cards) >= 4:
            break
    if not cards:
        for line in secondary[:4]:
            if ":" in line:
                label, _, value = line.partition(":")
                cards.append({"label": label.strip(), "value": value.strip()})
            else:
                cards.append({"label": "", "value": line})
    return cards or [{"label": "KPI", "value": "-"}]


def _lines_from_items(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text") or item.get("label") or item.get("value")
            if text:
                out.append(str(text).strip())
    return out


__all__ = ["render_deck_html"]
