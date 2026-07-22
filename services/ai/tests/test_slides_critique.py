"""Tests critique déterministe slides."""

from __future__ import annotations

import pytest

from app.documents.slides_critique import critique_and_fix


def test_critique_splits_too_dense_slide() -> None:
    bullets = [f"Point {i} avec du texte" for i in range(12)]
    result = critique_and_fix(
        [
            {
                "grammar": "sequence",
                "hierarchy": {"primary": "Dense", "secondary": bullets},
                "density": "high",
            }
        ]
    )
    assert result.split_performed is True
    assert len(result.slides) >= 2
    assert any(i.code == "auto_split" for i in result.issues)
    assert result.ok is True
    assert not any(i.code == "too_dense" for i in result.issues)


def test_critique_ok_for_light_slide() -> None:
    result = critique_and_fix(
        [{"grammar": "hero", "hierarchy": {"primary": "OK", "secondary": ["Sub"]}}]
    )
    assert result.ok is True
    assert len(result.slides) == 1


def test_critique_splits_dashboard_kpi_items_without_duplication() -> None:
    kpis = [{"label": f"K{i}", "value": str(i)} for i in range(6)]
    result = critique_and_fix(
        [
            {
                "grammar": "dashboard",
                "hierarchy": {"primary": "Tableau de bord", "secondary": [], "tertiary": []},
                "visual": {"type": "kpi_row", "items": kpis},
            }
        ]
    )
    assert result.split_performed is True
    assert len(result.slides) == 2
    all_labels: list[str] = []
    for slide in result.slides:
        visual = slide["visual"]
        for item in visual["items"]:
            all_labels.append(str(item["label"]))
    assert len(all_labels) == 6
    assert len(set(all_labels)) == 6
    assert result.ok is True


def test_critique_preserves_tertiary_on_split() -> None:
    secondary = [f"Sec {i} avec du texte supplementaire" for i in range(7)]
    tertiary = [f"Ter {i} detail complementaire" for i in range(4)]
    result = critique_and_fix(
        [
            {
                "grammar": "sequence",
                "hierarchy": {
                    "primary": "Titre",
                    "secondary": secondary,
                    "tertiary": tertiary,
                },
                "density": "high",
            }
        ]
    )
    assert result.split_performed is True
    all_tertiary: list[str] = []
    for slide in result.slides:
        all_tertiary.extend(slide["hierarchy"]["tertiary"])
    assert all_tertiary == tertiary
    assert result.ok is True


def test_critique_ok_false_when_dense_not_splittable() -> None:
    long_line = "mot " * 20
    result = critique_and_fix(
        [
            {
                "grammar": "sequence",
                "hierarchy": {"primary": "Court", "secondary": [long_line, long_line]},
                "density": "high",
            }
        ]
    )
    assert result.split_performed is False
    assert len(result.slides) == 1
    assert any(i.code == "too_dense" for i in result.issues)
    assert result.ok is False


def test_critique_raises_when_post_split_exceeds_60() -> None:
    bullets = [f"Point {i} avec du texte supplementaire" for i in range(12)]
    slides = [
        {
            "grammar": "sequence",
            "hierarchy": {"primary": f"Dense {i}", "secondary": list(bullets)},
            "density": "high",
        }
        for i in range(40)
    ]
    with pytest.raises(ValueError, match="Trop de slides"):
        critique_and_fix(slides)
