"""Estimation conservative de tokens sans dependance externe."""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas import ChatMessage


def _is_cjk_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x3040 <= code <= 0x309F
        or 0x30A0 <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF
        or 0xAC00 <= code <= 0xD7AF
        or 0xF900 <= code <= 0xFAFF
        or 0xFF00 <= code <= 0xFFEF
    )


def count_tokens_heuristic(text: str) -> int:
    if not text:
        return 0
    cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
    other_chars = len(text) - cjk_count
    return math.ceil(cjk_count + other_chars / 3)


def estimate_tokens(text: str, provider: str | None = None) -> int:
    """Estime le nombre de tokens d'un texte de maniere conservative.

    Estimateur offline sans dependance externe (pas de tiktoken). Utilise une
    heuristique locale (CJK ~1 token/caractere, autres caracteres /3) pour eviter
    la sous-estimation qui retarderait la compaction et provoquerait des erreurs
    400 cote provider. Le parametre ``provider`` est reserve pour une evolution
    future et n'est pas utilise par l'heuristique actuelle.
    """
    _ = provider
    return count_tokens_heuristic(text)


def estimate_message_tokens(message: ChatMessage, provider: str | None = None) -> int:
    parts: list[str] = [
        message.content or "",
        message.thinking or "",
        message.name or "",
        message.tool_call_id or "",
        message.role,
    ]
    for tool_call in message.tool_calls:
        parts.append(tool_call.id)
        parts.append(tool_call.name)
        parts.append(json.dumps(tool_call.arguments, ensure_ascii=False))
    return estimate_tokens("\n".join(parts), provider=provider)
