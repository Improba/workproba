"""Critique visuelle déterministe des slides sémantiques (sans VLM)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from app.documents.slides_schema import normalize_deck, normalize_slide

# Règles produit (phase 3)
_MAX_WORDS = 60
_MAX_SECONDARY = 6
_MAX_PRIMARY_CHARS = 80
_MAX_KPI_ITEMS = 4


@dataclass
class CritiqueIssue:
    code: str
    message: str
    slide_index: int


@dataclass
class CritiqueResult:
    ok: bool
    issues: list[CritiqueIssue] = field(default_factory=list)
    slides: list[dict[str, Any]] = field(default_factory=list)
    split_performed: bool = False


def critique_and_fix(
    slides: list[dict[str, Any]] | None,
    *,
    theme: str = "improba",
) -> CritiqueResult:
    """Valide densité / overflow textuel et répartit si une slide déborde.

    Retourne les slides normalisées (éventuellement splittées) + issues.
    """
    normalized = normalize_deck(slides, theme=theme)
    issues: list[CritiqueIssue] = []
    fixed: list[dict[str, Any]] = []
    split_performed = False

    for index, slide in enumerate(normalized, start=1):
        local_issues = _check_slide(slide, index=index)
        issues.extend(local_issues)
        overflow = any(i.code == "too_dense" for i in local_issues)
        if overflow:
            parts = _split_slide(slide)
            if len(parts) > 1:
                split_performed = True
                issues = [
                    i
                    for i in issues
                    if not (i.code == "too_dense" and i.slide_index == index)
                ]
                issues.append(
                    CritiqueIssue(
                        code="auto_split",
                        message=(
                            f"Slide {index}: contenu trop dense, "
                            f"réparti en {len(parts)} slides"
                        ),
                        slide_index=index,
                    )
                )
                fixed.extend(parts)
                continue
        fixed.append(slide)

    # Re-normaliser après split (index cohérents)
    final = [normalize_slide(s, index=i + 1) for i, s in enumerate(fixed)]
    if len(final) > 60:
        raise ValueError(f"Trop de slides ({len(final)}). Maximum: 60")

    ok = not any(i.code == "too_dense" for i in issues)
    return CritiqueResult(
        ok=ok,
        issues=issues,
        slides=final,
        split_performed=split_performed,
    )


def _check_slide(slide: dict[str, Any], *, index: int) -> list[CritiqueIssue]:
    issues: list[CritiqueIssue] = []
    grammar = str(slide.get("grammar") or "sequence")
    hierarchy = slide.get("hierarchy") if isinstance(slide.get("hierarchy"), dict) else {}
    primary = str(hierarchy.get("primary") or "").strip()
    secondary = hierarchy.get("secondary") if isinstance(hierarchy.get("secondary"), list) else []
    secondary_s = [str(s).strip() for s in secondary if str(s).strip()]
    tertiary = hierarchy.get("tertiary") if isinstance(hierarchy.get("tertiary"), list) else []
    tertiary_s = [str(s).strip() for s in tertiary if str(s).strip()]
    visual = slide.get("visual") if isinstance(slide.get("visual"), dict) else {}
    vtype = str(visual.get("type") or "none")
    items = visual.get("items") if isinstance(visual.get("items"), list) else []

    words = _word_count(primary, *secondary_s, *tertiary_s)
    if len(primary) > _MAX_PRIMARY_CHARS:
        issues.append(
            CritiqueIssue(
                code="title_too_long",
                message=f"Slide {index}: titre trop long ({len(primary)} car.)",
                slide_index=index,
            )
        )
    if len(secondary_s) > _MAX_SECONDARY or words > _MAX_WORDS:
        issues.append(
            CritiqueIssue(
                code="too_dense",
                message=(
                    f"Slide {index}: densite trop elevee "
                    f"({words} mots, {len(secondary_s)} puces)"
                ),
                slide_index=index,
            )
        )
    density = str(slide.get("density") or "medium")
    if density == "high" and words > 40:
        issues.append(
            CritiqueIssue(
                code="too_dense",
                message=f"Slide {index}: density=high incompatible avec {words} mots",
                slide_index=index,
            )
        )
    if (grammar == "dashboard" or vtype == "kpi_row") and len(items) > _MAX_KPI_ITEMS:
        issues.append(
            CritiqueIssue(
                code="too_dense",
                message=(
                    f"Slide {index}: trop de KPI ({len(items)} items, "
                    f"maximum {_MAX_KPI_ITEMS})"
                ),
                slide_index=index,
            )
        )
    return issues


def _split_slide(slide: dict[str, Any]) -> list[dict[str, Any]]:
    hierarchy = slide.get("hierarchy") if isinstance(slide.get("hierarchy"), dict) else {}
    primary = str(hierarchy.get("primary") or "").strip()
    secondary = hierarchy.get("secondary") if isinstance(hierarchy.get("secondary"), list) else []
    secondary_s = [str(s).strip() for s in secondary if str(s).strip()]
    tertiary = hierarchy.get("tertiary") if isinstance(hierarchy.get("tertiary"), list) else []
    tertiary_s = [str(s).strip() for s in tertiary if str(s).strip()]
    visual = slide.get("visual") if isinstance(slide.get("visual"), dict) else {}
    vtype = str(visual.get("type") or "none")
    items = visual.get("items") if isinstance(visual.get("items"), list) else []
    grammar = str(slide.get("grammar") or "sequence")

    can_split_bullets = len(secondary_s) >= 4
    can_split_items = (
        (grammar == "dashboard" or vtype == "kpi_row") and len(items) >= 2
    )
    if not can_split_bullets and not can_split_items:
        return [slide]

    part_a = copy.deepcopy(slide)
    part_b = copy.deepcopy(slide)

    if can_split_bullets:
        sec_mid = (len(secondary_s) + 1) // 2
        ter_mid = (len(tertiary_s) + 1) // 2
        part_a["hierarchy"] = {
            "primary": primary,
            "secondary": secondary_s[:sec_mid],
            "tertiary": tertiary_s[:ter_mid],
        }
        part_b["hierarchy"] = {
            "primary": f"{primary} (suite)" if primary else "Suite",
            "secondary": secondary_s[sec_mid:],
            "tertiary": tertiary_s[ter_mid:],
        }
    else:
        part_a["hierarchy"] = {
            "primary": primary,
            "secondary": list(secondary_s),
            "tertiary": list(tertiary_s),
        }
        part_b["hierarchy"] = {
            "primary": f"{primary} (suite)" if primary else "Suite",
            "secondary": [],
            "tertiary": [],
        }

    if can_split_items:
        items_mid = (len(items) + 1) // 2
        part_a["visual"] = {**visual, "items": items[:items_mid]}
        part_b["visual"] = {**visual, "items": items[items_mid:]}
    elif isinstance(part_b.get("visual"), dict):
        part_b["visual"] = {**part_b["visual"], "items": []}

    part_a["density"] = "medium"
    part_b["density"] = "medium"
    return [part_a, part_b]


def _word_count(*parts: str) -> int:
    total = 0
    for part in parts:
        total += len([w for w in part.replace("\n", " ").split(" ") if w.strip()])
    return total


__all__ = ["CritiqueIssue", "CritiqueResult", "critique_and_fix"]
