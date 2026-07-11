"""Tests de l'infrastructure i18n."""

from __future__ import annotations

import pytest

from app.i18n import (
    DEFAULT_LOCALE,
    MESSAGES,
    all_message_keys,
    attachment_status_label,
    format_summary,
    normalize_locale,
    t,
)


def test_fr_en_key_parity() -> None:
    fr_keys = all_message_keys("fr")
    en_keys = all_message_keys("en")
    assert fr_keys == en_keys
    assert fr_keys, "expected non-empty message catalog"


def test_normalize_locale_fallback() -> None:
    assert normalize_locale("fr") == "fr"
    assert normalize_locale("en") == "en"
    assert normalize_locale("EN") == "en"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("fr-FR") == "fr"
    assert normalize_locale(None) == DEFAULT_LOCALE
    assert normalize_locale("de") == DEFAULT_LOCALE
    assert normalize_locale("unknown") == DEFAULT_LOCALE


def test_t_substitution() -> None:
    assert (
        t("fr", "human.list_files.will", location="de l'espace")
        == "Je vais lister les fichiers de l'espace"
    )
    assert (
        t("en", "human.list_files.will", location="of the space")
        == "I will list files of the space"
    )


def test_t_missing_var_keeps_placeholder() -> None:
    assert t("fr", "human.list_files.will") == "Je vais lister les fichiers {location}"


def test_t_unknown_key_returns_key() -> None:
    assert t("fr", "does.not.exist") == "does.not.exist"


def test_format_summary_plural_one_many() -> None:
    fr_one = format_summary(
        "fr",
        "human.list_files.count",
        {"location": "de l'espace"},
        1,
    )
    fr_many = format_summary(
        "fr",
        "human.list_files.count",
        {"location": "de l'espace"},
        2,
    )
    assert fr_one == "J'ai listé les fichiers de l'espace (1 élément)"
    assert fr_many == "J'ai listé les fichiers de l'espace (2 éléments)"

    en_one = format_summary(
        "en",
        "human.search_kb.count",
        {"query": "« test »"},
        1,
    )
    en_many = format_summary(
        "en",
        "human.search_kb.count",
        {"query": "« test »"},
        2,
    )
    assert en_one == "I found 1 result for « test »"
    assert en_many == "I found 2 results for « test »"


def test_attachment_status_labels() -> None:
    assert attachment_status_label("fr", "viewed") == "Vue (image)"
    assert attachment_status_label("fr", "scanned_pdf") == "Lue (PDF scanné)"
    assert attachment_status_label("en", "word") == "Read (Word)"
    assert attachment_status_label("en", "unknown") == "Reading unavailable"


@pytest.mark.parametrize(
    ("locale", "key"),
    [
        ("fr", "tools.system_prompt"),
        ("en", "tools.system_prompt"),
        ("fr", "auth.local_only"),
        ("en", "auth.local_only"),
    ],
)
def test_core_messages_non_empty(locale: str, key: str) -> None:
    message = t(locale, key)
    assert message
    assert message != key


def test_messages_structure_has_both_locales() -> None:
    assert set(MESSAGES) == {"fr", "en"}
