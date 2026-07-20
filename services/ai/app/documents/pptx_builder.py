"""Génération native PowerPoint (.pptx) avec thèmes et layouts structurés."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

# Layouts supportés par write_pptx (catalogue produit, pas d'improvisation libre).
PPTX_LAYOUTS = frozenset(
    {
        "title",
        "section",
        "bullets",
        "two_column",
        "kpi_row",
        "quote",
        "closing",
    }
)
PPTX_THEMES = frozenset({"light", "dark", "improba"})
MAX_PPTX_SLIDES = 60
MAX_KPI_CARDS = 4

_SLIDE_W = 13.333  # inches, 16:9 widescreen
_SLIDE_H = 7.5


@dataclass(frozen=True)
class _Theme:
    name: str
    bg: tuple[int, int, int]
    surface: tuple[int, int, int]
    text: tuple[int, int, int]
    muted: tuple[int, int, int]
    accent: tuple[int, int, int]
    on_accent: tuple[int, int, int]


_THEMES: dict[str, _Theme] = {
    "light": _Theme(
        name="light",
        bg=(255, 255, 255),
        surface=(247, 244, 239),
        text=(28, 25, 23),
        muted=(87, 83, 78),
        accent=(196, 163, 90),
        on_accent=(28, 25, 23),
    ),
    "dark": _Theme(
        name="dark",
        bg=(28, 25, 23),
        surface=(41, 37, 36),
        text=(245, 245, 244),
        muted=(168, 162, 158),
        accent=(212, 175, 55),
        on_accent=(28, 25, 23),
    ),
    "improba": _Theme(
        name="improba",
        bg=(250, 248, 244),
        surface=(255, 255, 255),
        text=(32, 61, 82),
        muted=(90, 110, 125),
        accent=(196, 163, 90),
        on_accent=(32, 61, 82),
    ),
}


def build_pptx_bytes(
    *,
    slides: list[dict[str, Any]] | None = None,
    theme: str = "improba",
) -> bytes:
    """Construit un vrai fichier PowerPoint 16:9 à partir de slides structurées."""
    from pptx import Presentation
    from pptx.util import Inches

    theme_key = (theme or "improba").strip().lower()
    if theme_key not in _THEMES:
        allowed = ", ".join(sorted(PPTX_THEMES))
        raise ValueError(f"Thème inconnu {theme!r}. Utilise: {allowed}")
    palette = _THEMES[theme_key]

    normalized = _normalize_slides(slides)

    presentation = Presentation()
    presentation.slide_width = Inches(_SLIDE_W)
    presentation.slide_height = Inches(_SLIDE_H)

    for index, (layout, raw) in enumerate(normalized):
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        _fill_background(slide, palette.bg)
        _draw_layout(slide, layout=layout, data=raw, theme=palette, index=index)

    buf = BytesIO()
    presentation.save(buf)
    return buf.getvalue()


def _normalize_slides(
    slides: list[dict[str, Any]] | None,
) -> list[tuple[str, dict[str, Any]]]:
    if slides is None or (isinstance(slides, list) and len(slides) == 0):
        return [("title", {"layout": "title", "title": "Présentation", "subtitle": ""})]

    if not isinstance(slides, list):
        raise ValueError("slides doit être une liste de dicts")

    if len(slides) > MAX_PPTX_SLIDES:
        raise ValueError(
            f"Trop de slides ({len(slides)}). Maximum: {MAX_PPTX_SLIDES}"
        )

    normalized: list[tuple[str, dict[str, Any]]] = []
    for index, raw in enumerate(slides):
        slide_no = index + 1
        if not isinstance(raw, dict):
            raise ValueError(
                f"Slide {slide_no}: attendu un dict avec 'layout', "
                f"reçu {type(raw).__name__}"
            )
        layout = str(raw.get("layout") or "").strip().lower()
        if not layout:
            layout = "bullets"
        if layout not in PPTX_LAYOUTS:
            allowed = ", ".join(sorted(PPTX_LAYOUTS))
            raise ValueError(
                f"Slide {slide_no}: layout inconnu {layout!r}. Utilise: {allowed}"
            )
        _validate_slide_content(layout, raw, slide_no)
        normalized.append((layout, raw))

    if not normalized:
        raise ValueError(
            "Aucune slide exploitable: passe une liste de dicts avec 'layout'"
        )
    return normalized


def _validate_slide_content(layout: str, data: dict[str, Any], slide_no: int) -> None:
    title = str(data.get("title") or "").strip()
    subtitle = str(data.get("subtitle") or "").strip()
    bullets = _as_str_list(data.get("bullets"))
    left_items = _as_str_list(data.get("left"))
    right_items = _as_str_list(data.get("right"))
    quote = str(data.get("quote") or data.get("body") or "").strip()
    metrics = data.get("metrics") if isinstance(data.get("metrics"), list) else []
    metric_dicts = [m for m in metrics if isinstance(m, dict)]

    if layout == "title":
        return
    if layout == "section":
        return
    if layout == "closing":
        if not (title or subtitle or bullets):
            raise ValueError(
                f"Slide {slide_no} (closing): fournir title, subtitle ou bullets"
            )
        return
    if layout == "bullets":
        if not (title or bullets):
            raise ValueError(
                f"Slide {slide_no} (bullets): fournir title et/ou bullets"
            )
        return
    if layout == "two_column":
        if not (left_items or right_items or bullets):
            raise ValueError(
                f"Slide {slide_no} (two_column): fournir left, right ou bullets"
            )
        return
    if layout == "kpi_row":
        if len(metric_dicts) > MAX_KPI_CARDS:
            raise ValueError(
                f"Slide {slide_no} (kpi_row): maximum {MAX_KPI_CARDS} metrics "
                f"(reçu: {len(metric_dicts)})"
            )
        if not metric_dicts and not bullets:
            raise ValueError(
                f"Slide {slide_no} (kpi_row): fournir metrics ou bullets"
            )
        if not metric_dicts and len(bullets) > MAX_KPI_CARDS:
            raise ValueError(
                f"Slide {slide_no} (kpi_row): maximum {MAX_KPI_CARDS} KPIs "
                f"(reçu: {len(bullets)} bullets)"
            )
        return
    if layout == "quote":
        if not (quote or bullets or title):
            raise ValueError(
                f"Slide {slide_no} (quote): fournir quote, body, title ou bullets"
            )
        return


def _rgb(color: tuple[int, int, int]):
    from pptx.dml.color import RGBColor

    return RGBColor(*color)


def _fill_background(slide: Any, color: tuple[int, int, int]) -> None:
    """Fond plein. Ajouté en premier shape = arrière-plan (pas de réordonnancement XML)."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0),
        Inches(0),
        Inches(_SLIDE_W),
        Inches(_SLIDE_H),
    )
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(color)


def _add_rect(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    fill: tuple[int, int, int],
) -> Any:
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    return shape


def _add_textbox(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    font_size: int,
    color: tuple[int, int, int],
    bold: bool = False,
    align: str = "left",
) -> None:
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    box = slide.shapes.add_textbox(
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    run.font.name = "Calibri"
    if align == "center":
        p.alignment = PP_ALIGN.CENTER
    elif align == "right":
        p.alignment = PP_ALIGN.RIGHT
    else:
        p.alignment = PP_ALIGN.LEFT


def _add_bullets(
    slide: Any,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    items: list[str],
    color: tuple[int, int, int],
    font_size: int = 22,
) -> None:
    from pptx.util import Inches, Pt

    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return

    box = slide.shapes.add_textbox(
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    tf = box.text_frame
    tf.word_wrap = True
    for index, text in enumerate(cleaned):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = text
        p.level = 0
        p.font.size = Pt(font_size)
        p.font.color.rgb = _rgb(color)
        p.font.name = "Calibri"
        p.space_after = Pt(10)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label") or item.get("title") or ""
            val = item.get("value") or item.get("text") or ""
            if label or val:
                out.append(f"{label}: {val}".strip(": ").strip())
    return out


def _draw_layout(
    slide: Any,
    *,
    layout: str,
    data: dict[str, Any],
    theme: _Theme,
    index: int,
) -> None:
    title = str(data.get("title") or "").strip()
    subtitle = str(data.get("subtitle") or "").strip()
    bullets = _as_str_list(data.get("bullets"))
    left_items = _as_str_list(data.get("left"))
    right_items = _as_str_list(data.get("right"))
    quote = str(data.get("quote") or data.get("body") or "").strip()
    attribution = str(data.get("attribution") or data.get("author") or "").strip()
    metrics = data.get("metrics") if isinstance(data.get("metrics"), list) else []

    # Bandeau accent gauche commun
    _add_rect(slide, left=0, top=0, width=0.18, height=_SLIDE_H, fill=theme.accent)

    if layout == "title":
        _add_rect(
            slide,
            left=0.18,
            top=0,
            width=_SLIDE_W - 0.18,
            height=0.12,
            fill=theme.accent,
        )
        _add_textbox(
            slide,
            left=0.9,
            top=2.4,
            width=11.2,
            height=1.6,
            text=title or "Présentation",
            font_size=44,
            color=theme.text,
            bold=True,
        )
        if subtitle:
            _add_textbox(
                slide,
                left=0.9,
                top=4.2,
                width=11.2,
                height=1.0,
                text=subtitle,
                font_size=22,
                color=theme.muted,
            )
        return

    if layout == "section":
        _add_textbox(
            slide,
            left=0.9,
            top=2.6,
            width=11.2,
            height=1.2,
            text=title or f"Section {index + 1}",
            font_size=40,
            color=theme.text,
            bold=True,
            align="center",
        )
        _add_rect(
            slide,
            left=5.4,
            top=4.0,
            width=2.5,
            height=0.08,
            fill=theme.accent,
        )
        if subtitle:
            _add_textbox(
                slide,
                left=1.5,
                top=4.4,
                width=10.3,
                height=1.0,
                text=subtitle,
                font_size=20,
                color=theme.muted,
                align="center",
            )
        return

    if layout == "quote":
        body = quote or (bullets[0] if bullets else title)
        _add_textbox(
            slide,
            left=1.4,
            top=2.2,
            width=10.4,
            height=2.4,
            text=f"« {body} »",
            font_size=28,
            color=theme.text,
            align="center",
        )
        if attribution:
            _add_textbox(
                slide,
                left=1.4,
                top=4.8,
                width=10.4,
                height=0.6,
                text=f"- {attribution}",
                font_size=18,
                color=theme.muted,
                align="center",
            )
        return

    if layout == "kpi_row":
        if title:
            _add_textbox(
                slide,
                left=0.9,
                top=0.55,
                width=11.2,
                height=0.8,
                text=title,
                font_size=32,
                color=theme.text,
                bold=True,
            )
            _add_rect(
                slide,
                left=0.9,
                top=1.35,
                width=1.8,
                height=0.07,
                fill=theme.accent,
            )
        cards = [m for m in metrics if isinstance(m, dict)][:MAX_KPI_CARDS]
        if not cards and bullets:
            for item in bullets[:MAX_KPI_CARDS]:
                if ":" in item:
                    label, _, value = item.partition(":")
                    cards.append({"label": label.strip(), "value": value.strip()})
                else:
                    cards.append({"label": "", "value": item})
        count = max(len(cards), 1)
        gap = 0.35
        usable = 11.4
        card_w = (usable - gap * (count - 1)) / count
        top = 2.4
        for i, card in enumerate(cards):
            left = 0.9 + i * (card_w + gap)
            _add_rect(
                slide,
                left=left,
                top=top,
                width=card_w,
                height=2.8,
                fill=theme.surface,
            )
            _add_rect(
                slide,
                left=left,
                top=top,
                width=card_w,
                height=0.1,
                fill=theme.accent,
            )
            value = str(card.get("value") or "-").strip()
            label = str(card.get("label") or "").strip()
            _add_textbox(
                slide,
                left=left + 0.2,
                top=top + 0.7,
                width=card_w - 0.4,
                height=1.0,
                text=value,
                font_size=28 if len(value) < 12 else 22,
                color=theme.text,
                bold=True,
                align="center",
            )
            if label:
                _add_textbox(
                    slide,
                    left=left + 0.2,
                    top=top + 1.8,
                    width=card_w - 0.4,
                    height=0.6,
                    text=label,
                    font_size=14,
                    color=theme.muted,
                    align="center",
                )
        return

    if layout == "two_column":
        if title:
            _add_textbox(
                slide,
                left=0.9,
                top=0.45,
                width=11.2,
                height=0.7,
                text=title,
                font_size=30,
                color=theme.text,
                bold=True,
            )
            _add_rect(
                slide,
                left=0.9,
                top=1.15,
                width=1.8,
                height=0.07,
                fill=theme.accent,
            )
        left_title = str(data.get("left_title") or "").strip()
        right_title = str(data.get("right_title") or "").strip()
        col_top = 1.5
        if left_title:
            _add_textbox(
                slide,
                left=0.9,
                top=col_top,
                width=5.3,
                height=0.5,
                text=left_title,
                font_size=18,
                color=theme.accent,
                bold=True,
            )
            col_top_left = col_top + 0.55
        else:
            col_top_left = col_top
        if right_title:
            _add_textbox(
                slide,
                left=6.9,
                top=col_top,
                width=5.3,
                height=0.5,
                text=right_title,
                font_size=18,
                color=theme.accent,
                bold=True,
            )
            col_top_right = col_top + 0.55
        else:
            col_top_right = col_top

        if left_items or right_items:
            col_left = left_items
            col_right = right_items
        else:
            mid = max(1, len(bullets) // 2)
            col_left = bullets[:mid]
            col_right = bullets[mid:]

        _add_bullets(
            slide,
            left=0.9,
            top=col_top_left,
            width=5.3,
            height=4.8,
            items=col_left,
            color=theme.text,
            font_size=18,
        )
        _add_bullets(
            slide,
            left=6.9,
            top=col_top_right,
            width=5.3,
            height=4.8,
            items=col_right,
            color=theme.text,
            font_size=18,
        )
        return

    # bullets + closing
    if title:
        _add_textbox(
            slide,
            left=0.9,
            top=0.45,
            width=11.2,
            height=0.7,
            text=title,
            font_size=30,
            color=theme.text,
            bold=True,
        )
        _add_rect(
            slide,
            left=0.9,
            top=1.15,
            width=1.8,
            height=0.07,
            fill=theme.accent,
        )
    if subtitle and layout == "closing":
        _add_textbox(
            slide,
            left=0.9,
            top=1.5,
            width=11.2,
            height=0.6,
            text=subtitle,
            font_size=18,
            color=theme.muted,
        )
        bullets_top = 2.3
    else:
        bullets_top = 1.5
    if bullets:
        _add_bullets(
            slide,
            left=0.9,
            top=bullets_top,
            width=11.2,
            height=5.2,
            items=bullets,
            color=theme.text,
            font_size=20,
        )
