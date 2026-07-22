"""Schéma sémantique des slides (intention → grammaire → rendu)."""

from __future__ import annotations

from typing import Any

# Phase 1 natives + phase 3 étendues (toutes validées ; rendu progressif).
GRAMMARS = frozenset(
    {
        "hero",
        "split",
        "comparison",
        "sequence",
        "dashboard",
        "diagram",
        "editorial",
    }
)
PHASE1_GRAMMARS = frozenset({"hero", "split", "comparison", "sequence"})

DENSITIES = frozenset({"low", "medium", "high"})
VISUAL_TYPES = frozenset(
    {
        "none",
        "kpi_row",
        "before_after",
        "quote",
        "cards",
        "steps",
        "timeline",
        "diagram",
    }
)
IMPORTANCES = frozenset({"low", "medium", "high"})

# Ancien catalogue layout → grammaire
_LAYOUT_TO_GRAMMAR: dict[str, str] = {
    "title": "hero",
    "section": "hero",
    "bullets": "sequence",
    "two_column": "split",
    "kpi_row": "dashboard",
    "quote": "editorial",
    "closing": "hero",
}


def normalize_deck(
    slides: list[dict[str, Any]] | None,
    *,
    theme: str = "improba",
) -> list[dict[str, Any]]:
    """Normalise une liste de slides (ancien layout ou nouveau grammar)."""
    _ = theme  # réservé (thème validé côté builder)
    if slides is None or (isinstance(slides, list) and len(slides) == 0):
        return [
            {
                "grammar": "hero",
                "message": "",
                "hierarchy": {
                    "primary": "Présentation",
                    "secondary": [],
                    "tertiary": [],
                },
                "visual": {"type": "none", "importance": "medium", "items": []},
                "density": "low",
            }
        ]
    if not isinstance(slides, list):
        raise ValueError("slides doit être une liste de dicts")
    if len(slides) > 60:
        raise ValueError(f"Trop de slides ({len(slides)}). Maximum: 60")

    return [normalize_slide(raw, index=i + 1) for i, raw in enumerate(slides)]


def normalize_slide(raw: Any, *, index: int = 1) -> dict[str, Any]:
    """Convertit une slide brute en forme sémantique canonique."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"Slide {index}: attendu un dict, reçu {type(raw).__name__}"
        )

    if "grammar" in raw or "hierarchy" in raw or "visual" in raw:
        return _normalize_semantic(raw, index=index)

    if "layout" in raw:
        return _normalize_legacy_layout(raw, index=index)

    # Inférence minimale title/bullets
    title = str(raw.get("title") or "").strip()
    bullets = _str_list(raw.get("bullets"))
    if title and not bullets:
        return _normalize_semantic(
            {
                "grammar": "hero",
                "hierarchy": {"primary": title, "secondary": _str_list(raw.get("subtitle"))},
            },
            index=index,
        )
    if title or bullets:
        return _normalize_semantic(
            {
                "grammar": "sequence",
                "hierarchy": {"primary": title or f"Slide {index}", "secondary": bullets},
                "visual": {"type": "steps", "importance": "medium"},
            },
            index=index,
        )
    raise ValueError(
        f"Slide {index}: fournir grammar/hierarchy ou layout, ou title/bullets"
    )


def _normalize_legacy_layout(raw: dict[str, Any], *, index: int) -> dict[str, Any]:
    layout = str(raw.get("layout") or "").strip().lower()
    grammar = _LAYOUT_TO_GRAMMAR.get(layout)
    if not grammar:
        allowed = ", ".join(sorted(_LAYOUT_TO_GRAMMAR))
        raise ValueError(
            f"Slide {index}: layout inconnu {layout!r}. Utilise: {allowed} "
            f"ou une grammar parmi {', '.join(sorted(GRAMMARS))}"
        )

    title = str(raw.get("title") or "").strip()
    subtitle = str(raw.get("subtitle") or "").strip()
    bullets = _str_list(raw.get("bullets"))
    left = _str_list(raw.get("left"))
    right = _str_list(raw.get("right"))
    quote = str(raw.get("quote") or raw.get("body") or "").strip()
    attribution = str(raw.get("attribution") or raw.get("author") or "").strip()
    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), list) else []

    hierarchy = {
        "primary": title,
        "secondary": [],
        "tertiary": [],
    }
    visual: dict[str, Any] = {"type": "none", "importance": "medium", "items": []}

    if layout == "title" or layout == "closing" or layout == "section":
        hierarchy["primary"] = title or (
            f"Section {index}" if layout == "section" else "Présentation"
        )
        if subtitle:
            hierarchy["secondary"] = [subtitle]
        if bullets:
            hierarchy["secondary"] = hierarchy["secondary"] + bullets
        visual["type"] = "none"
        density = "low"
    elif layout == "bullets":
        hierarchy["primary"] = title or f"Slide {index}"
        hierarchy["secondary"] = bullets
        visual["type"] = "steps"
        density = "medium"
        if not title and not bullets:
            raise ValueError(f"Slide {index} (bullets): fournir title et/ou bullets")
    elif layout == "two_column":
        hierarchy["primary"] = title or f"Slide {index}"
        left_title = str(raw.get("left_title") or "").strip()
        right_title = str(raw.get("right_title") or "").strip()
        if not (left or right or bullets):
            raise ValueError(
                f"Slide {index} (two_column): fournir left, right ou bullets"
            )
        visual = {
            "type": "before_after",
            "importance": "high",
            "items": [
                {"side": "left", "title": left_title, "lines": left or bullets[: max(1, len(bullets) // 2)]},
                {
                    "side": "right",
                    "title": right_title,
                    "lines": right or bullets[max(1, len(bullets) // 2) :],
                },
            ],
        }
        density = "medium"
    elif layout == "kpi_row":
        hierarchy["primary"] = title or f"Slide {index}"
        cards = [m for m in metrics if isinstance(m, dict)]
        if len(cards) > 4:
            raise ValueError(f"Slide {index} (kpi_row): maximum 4 metrics")
        if not cards and not bullets:
            raise ValueError(f"Slide {index} (kpi_row): fournir metrics ou bullets")
        if not cards:
            for item in bullets[:4]:
                if ":" in item:
                    label, _, value = item.partition(":")
                    cards.append({"label": label.strip(), "value": value.strip()})
                else:
                    cards.append({"label": "", "value": item})
        visual = {
            "type": "kpi_row",
            "importance": "high",
            "items": cards[:4],
        }
        density = "low"
    elif layout == "quote":
        body = quote or (bullets[0] if bullets else title)
        if not body:
            raise ValueError(
                f"Slide {index} (quote): fournir quote, body, title ou bullets"
            )
        hierarchy["primary"] = body
        if attribution:
            hierarchy["secondary"] = [attribution]
        visual = {"type": "quote", "importance": "high", "items": []}
        density = "low"
    else:
        density = "medium"

    return _normalize_semantic(
        {
            "grammar": grammar,
            "message": str(raw.get("message") or "").strip(),
            "hierarchy": hierarchy,
            "visual": visual,
            "density": density,
        },
        index=index,
    )


def _normalize_semantic(raw: dict[str, Any], *, index: int) -> dict[str, Any]:
    grammar = str(raw.get("grammar") or "sequence").strip().lower()
    if grammar not in GRAMMARS:
        raise ValueError(
            f"Slide {index}: grammar inconnue {grammar!r}. "
            f"Utilise: {', '.join(sorted(GRAMMARS))}"
        )

    hierarchy_raw = raw.get("hierarchy") if isinstance(raw.get("hierarchy"), dict) else {}
    primary = str(
        hierarchy_raw.get("primary")
        or raw.get("title")
        or raw.get("message")
        or ""
    ).strip()
    secondary = _str_list(hierarchy_raw.get("secondary"))
    if not secondary:
        secondary = _str_list(raw.get("bullets")) or _str_list(raw.get("subtitle"))
    tertiary = _str_list(hierarchy_raw.get("tertiary"))

    visual_raw = raw.get("visual") if isinstance(raw.get("visual"), dict) else {}
    vtype = str(visual_raw.get("type") or "none").strip().lower()
    if vtype not in VISUAL_TYPES:
        vtype = "none"
    importance = str(visual_raw.get("importance") or "medium").strip().lower()
    if importance not in IMPORTANCES:
        importance = "medium"
    items = visual_raw.get("items") if isinstance(visual_raw.get("items"), list) else []

    density = str(raw.get("density") or "medium").strip().lower()
    if density not in DENSITIES:
        density = "medium"

    message = str(raw.get("message") or "").strip()

    # Contenu minimal par grammaire
    if grammar in {"hero", "editorial"} and not primary:
        primary = f"Slide {index}"
    if grammar == "sequence" and not primary and not secondary:
        raise ValueError(
            f"Slide {index} (sequence): fournir hierarchy.primary et/ou secondary"
        )
    if grammar in {"split", "comparison"}:
        if not items and not secondary:
            raise ValueError(
                f"Slide {index} ({grammar}): fournir visual.items ou secondary"
            )
    if grammar == "dashboard":
        if vtype == "none":
            vtype = "kpi_row"
        if not items and not secondary:
            raise ValueError(
                f"Slide {index} (dashboard): fournir visual.items (KPI) ou secondary"
            )

    return {
        "grammar": grammar,
        "message": message,
        "hierarchy": {
            "primary": primary,
            "secondary": secondary,
            "tertiary": tertiary,
        },
        "visual": {
            "type": vtype,
            "importance": importance,
            "items": items,
        },
        "density": density,
    }


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
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


__all__ = [
    "GRAMMARS",
    "PHASE1_GRAMMARS",
    "normalize_deck",
    "normalize_slide",
]
