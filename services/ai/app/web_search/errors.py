"""Erreurs métier recherche web."""

from __future__ import annotations

from app.i18n import t


class WebSearchError(Exception):
    """Erreur recherche web (``detail`` = clé i18n ``errors.*``)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def web_search_error_detail(detail: str, locale: str) -> str:
    key = f"errors.{detail}"
    translated = t(locale, key)
    return translated if translated != key else detail
