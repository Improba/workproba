"""Détection PDF scanné (peu ou pas de texte extractable)."""

from __future__ import annotations

from io import BytesIO


def is_scanned_pdf(
    content: bytes,
    *,
    max_pages: int = 5,
    min_chars_per_page: int = 30,
) -> bool:
    """Retourne True si le PDF semble être une image scannée sans couche texte."""
    import pdfplumber

    with pdfplumber.open(BytesIO(content)) as pdf:
        if not pdf.pages:
            return True
        for page in pdf.pages[:max_pages]:
            text = (page.extract_text() or "").strip()
            if len(text) >= min_chars_per_page:
                return False
        return True
