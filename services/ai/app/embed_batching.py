"""Découpage des requêtes d'embedding en lots compatibles providers."""

from __future__ import annotations

from collections.abc import Iterator


def iter_embedding_batches(
    texts: list[str],
    *,
    max_items: int,
    max_chars: int,
) -> Iterator[list[str]]:
    """Découpe `texts` en lots respectant un plafond de taille et de caractères.

    Les providers (ex. Mistral) rejettent les requêtes dont le total de tokens
    dépasse une borne ; le plafond caractères complète le plafond en nombre de
    morceaux pour rester sous cette limite.
    """
    if max_items <= 0:
        raise ValueError("max_items must be positive")
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    batch: list[str] = []
    batch_chars = 0

    for text in texts:
        text_len = len(text)
        if text_len > max_chars:
            if batch:
                yield batch
                batch = []
                batch_chars = 0
            yield [text]
            continue

        exceeds_items = len(batch) >= max_items
        exceeds_chars = batch and batch_chars + text_len > max_chars
        if exceeds_items or exceeds_chars:
            yield batch
            batch = []
            batch_chars = 0

        batch.append(text)
        batch_chars += text_len

    if batch:
        yield batch
