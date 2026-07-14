"""Helpers partagés pour marquer le contenu non fiable injecté dans les prompts."""

from __future__ import annotations

from app.i18n import t


def wrap_untrusted_content(text: str, locale: str, header_key: str) -> str:
    """Encadre un fragment de texte avec en-tête i18n et balises <untrusted> fixes."""
    header = t(locale, header_key)
    return f"{header}\n<untrusted>\n{text.strip()}\n</untrusted>"


__all__ = ["wrap_untrusted_content"]
