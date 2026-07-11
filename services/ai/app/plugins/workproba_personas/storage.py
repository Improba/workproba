"""Stockage namespace plugin personas (sets, réunions, discussions)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

SETS_FILE = "sets.json"
BUILTIN_SET_ID = "default"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_iso() -> str:
    return now_iso()


def builtin_persona_set() -> JsonDict:
    """Set Improba par défaut (en code, non éditable)."""
    return {
        "id": BUILTIN_SET_ID,
        "name": "Improba",
        "personas": [
            {
                "id": "01",
                "name": "Sylvie",
                "role": "Assistante RH",
                "description": (
                    "Assistante RH pragmatique, non technique, soucieuse de ne pas casser "
                    "les processus existants."
                ),
                "system_prompt": (
                    "Tu es Sylvie, assistante RH chez Improba. Tu n'es pas technique. "
                    "Tu raisonnes en termes de personnes, de conformité RH, de clarté pour "
                    "les collaborateurs et de risques opérationnels. Tu as peur de casser "
                    "ce qui fonctionne : tu préfères des changements progressifs et bien "
                    "expliqués. Réponds de façon concise, accessible, sans jargon IT."
                ),
                "avatar_color": "#FFCC49",
            },
            {
                "id": "02",
                "name": "Samira",
                "role": "Ingénieure produit",
                "description": (
                    "Ingénieure produit focalisée sur la cohérence fonctionnelle et les "
                    "cas limites."
                ),
                "system_prompt": (
                    "Tu es Samira, ingénieure produit chez Improba. Tu es technique sur le "
                    "fonctionnel. Tu cherches la cohérence du parcours utilisateur, les "
                    "edge cases, les critères d'acceptation et la testabilité. Tu poses des "
                    "questions précises et proposes des améliorations concrètes."
                ),
                "avatar_color": "#E8B84A",
            },
            {
                "id": "03",
                "name": "Marc",
                "role": "Technicien terrain",
                "description": (
                    "Technicien prudent et rigoureux, non développeur, soucieux de la "
                    "fiabilité sur le terrain."
                ),
                "system_prompt": (
                    "Tu es Marc, technicien terrain chez Improba. Tu n'es pas développeur. "
                    "Tu raisonnes en procédures, check-lists, sécurité opérationnelle et "
                    "simplicité d'exécution. Tu es prudent : tu signales ce qui peut mal "
                    "se passer en conditions réelles. Réponds sans jargon inutile."
                ),
                "avatar_color": "#D4A843",
            },
            {
                "id": "04",
                "name": "Karim",
                "role": "Power-user avancé",
                "description": (
                    "Utilisateur expert exigeant, à l'aise avec la technique et les détails "
                    "d'implémentation."
                ),
                "system_prompt": (
                    "Tu es Karim, power-user avancé chez Improba. Tu es technique et "
                    "exigeant. Tu attends des réponses précises, structurées, avec les "
                    "compromis techniques explicites. Tu challenge les simplifications "
                    "abusives et tu proposes des alternatives concrètes."
                ),
                "avatar_color": "#C09838",
            },
            {
                "id": "05",
                "name": "Claire",
                "role": "Responsable SI",
                "description": (
                    "Responsable SI orientée sécurité, conformité et verrouillage des "
                    "environnements."
                ),
                "system_prompt": (
                    "Tu es Claire, responsable SI chez Improba. Tu raisonnes en sécurité, "
                    "conformité, gouvernance des accès et maîtrise des risques. Tu "
                    "recommandes le verrouillage quand c'est nécessaire et tu identifies "
                    "les fuites de données ou les dérives de politique."
                ),
                "avatar_color": "#A88030",
            },
            {
                "id": "06",
                "name": "Nathalie",
                "role": "Product Owner",
                "description": (
                    "PO qui arbitre, synthétise les points de vue et formule des décisions."
                ),
                "system_prompt": (
                    "Tu es Nathalie, Product Owner chez Improba. Tu synthétises les avis, "
                    "identifies convergences et divergences, puis tu formules des "
                    "recommandations actionnables. Tu restes factuelle et orientée décision."
                ),
                "avatar_color": "#907028",
            },
        ],
    }


def _sets_path(plugin_data_dir: Path) -> Path:
    return plugin_data_dir / SETS_FILE


def load_custom_sets(plugin_data_dir: Path) -> list[JsonDict]:
    path = _sets_path(plugin_data_dir)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return []
    sets = raw.get("sets")
    return list(sets) if isinstance(sets, list) else []


def save_custom_sets(plugin_data_dir: Path, sets: list[JsonDict]) -> None:
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    with _sets_path(plugin_data_dir).open("w", encoding="utf-8") as handle:
        json.dump({"sets": sets}, handle, ensure_ascii=False, indent=2)


def _sanitize_set_personas(personas: Any) -> list[JsonDict]:
    if not isinstance(personas, list):
        return []
    cleaned: list[JsonDict] = []
    for persona in personas:
        if not isinstance(persona, dict):
            continue
        persona_id = persona.get("id")
        if not isinstance(persona_id, str) or not persona_id:
            continue
        cleaned.append(
            {
                "id": persona_id,
                "name": str(persona.get("name") or ""),
                "role": str(persona.get("role") or ""),
                "description": str(persona.get("description") or ""),
                "system_prompt": str(persona.get("system_prompt") or ""),
                "avatar_color": str(persona.get("avatar_color") or "#888888"),
            }
        )
    return cleaned


def upsert_custom_set(plugin_data_dir: Path, set_payload: JsonDict) -> JsonDict:
    set_id = set_payload.get("id")
    if not isinstance(set_id, str) or not set_id or set_id == BUILTIN_SET_ID:
        set_id = f"custom_{uuid.uuid4().hex[:12]}"
    name = str(set_payload.get("name") or "").strip()
    if not name:
        raise ValueError("invalid_set_name")
    personas = _sanitize_set_personas(set_payload.get("personas"))
    if not personas:
        raise ValueError("invalid_set_personas")
    record: JsonDict = {"id": set_id, "name": name, "personas": personas}
    custom = load_custom_sets(plugin_data_dir)
    updated = False
    for index, existing in enumerate(custom):
        if existing.get("id") == set_id:
            custom[index] = record
            updated = True
            break
    if not updated:
        custom.append(record)
    save_custom_sets(plugin_data_dir, custom)
    return record


def delete_custom_set(plugin_data_dir: Path, set_id: str) -> bool:
    if not _safe_object_id(set_id) or set_id == BUILTIN_SET_ID:
        return False
    custom = load_custom_sets(plugin_data_dir)
    filtered = [item for item in custom if item.get("id") != set_id]
    if len(filtered) == len(custom):
        return False
    save_custom_sets(plugin_data_dir, filtered)
    return True


def list_sets(plugin_data_dir: Path) -> list[JsonDict]:
    return [builtin_persona_set(), *load_custom_sets(plugin_data_dir)]


def _persona_index(plugin_data_dir: Path) -> dict[str, JsonDict]:
    index: dict[str, JsonDict] = {}
    for persona_set in list_sets(plugin_data_dir):
        for persona in persona_set.get("personas") or []:
            if not isinstance(persona, dict):
                continue
            persona_id = persona.get("id")
            if isinstance(persona_id, str) and persona_id:
                index[persona_id] = persona
    return index


def resolve_personas(plugin_data_dir: Path, persona_ids: list[str]) -> list[JsonDict]:
    index = _persona_index(plugin_data_dir)
    resolved: list[JsonDict] = []
    for persona_id in persona_ids:
        persona = index.get(persona_id)
        if persona is not None:
            resolved.append(persona)
    return resolved


def _safe_object_id(object_id: str) -> bool:
    if not object_id or object_id in {".", ".."}:
        return False
    if "/" in object_id or "\\" in object_id or ".." in object_id:
        return False
    return True


def meeting_dir(plugin_data_dir: Path, meeting_id: str) -> Path:
    if not _safe_object_id(meeting_id):
        raise ValueError("invalid_meeting_id")
    return plugin_data_dir / "meetings" / meeting_id


def save_meeting_transcript(
    plugin_data_dir: Path,
    meeting_id: str,
    transcript: JsonDict,
) -> Path:
    directory = meeting_dir(plugin_data_dir, meeting_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "transcript.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(transcript, handle, ensure_ascii=False, indent=2)
    return path


def discussion_dir(plugin_data_dir: Path, discussion_id: str) -> Path:
    if not _safe_object_id(discussion_id):
        raise ValueError("invalid_discussion_id")
    return plugin_data_dir / "discussions" / discussion_id


def load_discussion_messages(
    plugin_data_dir: Path,
    discussion_id: str,
) -> list[JsonDict]:
    path = discussion_dir(plugin_data_dir, discussion_id) / "messages.json"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return []
    messages = raw.get("messages")
    return list(messages) if isinstance(messages, list) else []


def save_discussion_messages(
    plugin_data_dir: Path,
    discussion_id: str,
    messages: list[JsonDict],
    *,
    persona_ids: list[str],
    title: str | None = None,
) -> Path:
    directory = discussion_dir(plugin_data_dir, discussion_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "messages.json"
    created_at = _now_iso()
    if path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        if isinstance(existing, dict) and existing.get("created_at"):
            created_at = str(existing["created_at"])
    payload: JsonDict = {
        "id": discussion_id,
        "title": title or "",
        "persona_ids": persona_ids,
        "created_at": created_at,
        "updated_at": _now_iso(),
        "messages": messages,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def _meetings_root(plugin_data_dir: Path) -> Path:
    return plugin_data_dir / "meetings"


def _discussions_root(plugin_data_dir: Path) -> Path:
    return plugin_data_dir / "discussions"


def _meeting_summary_from_transcript(raw: JsonDict, meeting_id: str) -> JsonDict:
    return {
        "meeting_id": raw.get("id") or meeting_id,
        "topic": raw.get("topic") or "",
        "persona_ids": list(raw.get("persona_ids") or []),
        "rounds": int(raw.get("rounds") or 0),
        "created_at": raw.get("created_at") or "",
    }


def list_meetings(plugin_data_dir: Path) -> list[JsonDict]:
    root = _meetings_root(plugin_data_dir)
    if not root.is_dir():
        return []
    meetings: list[JsonDict] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        transcript_path = directory / "transcript.json"
        if not transcript_path.is_file():
            continue
        with transcript_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            continue
        meetings.append(_meeting_summary_from_transcript(raw, directory.name))
    return meetings


def get_meeting(plugin_data_dir: Path, meeting_id: str) -> JsonDict | None:
    if not _safe_object_id(meeting_id):
        return None
    path = meeting_dir(plugin_data_dir, meeting_id) / "transcript.json"
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return None
    detail = _meeting_summary_from_transcript(raw, meeting_id)
    detail["transcript"] = list(raw.get("turns") or [])
    summary_raw = raw.get("summary")
    if isinstance(summary_raw, dict):
        detail["summary"] = summary_raw
    return detail


def _discussion_last_message_at(messages: list[JsonDict], fallback: str) -> str:
    for item in reversed(messages):
        created_at = item.get("created_at")
        if isinstance(created_at, str) and created_at:
            return created_at
    return fallback


def list_discussions(plugin_data_dir: Path) -> list[JsonDict]:
    root = _discussions_root(plugin_data_dir)
    if not root.is_dir():
        return []
    discussions: list[JsonDict] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        messages_path = directory / "messages.json"
        if not messages_path.is_file():
            continue
        with messages_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            continue
        messages = list(raw.get("messages") or [])
        updated_at = str(raw.get("updated_at") or "")
        created_at = str(raw.get("created_at") or updated_at)
        discussions.append(
            {
                "discussion_id": raw.get("id") or directory.name,
                "persona_ids": list(raw.get("persona_ids") or []),
                "created_at": created_at,
                "last_message_at": _discussion_last_message_at(messages, updated_at),
            }
        )
    return discussions


def get_discussion(plugin_data_dir: Path, discussion_id: str) -> JsonDict | None:
    if not _safe_object_id(discussion_id):
        return None
    path = discussion_dir(plugin_data_dir, discussion_id) / "messages.json"
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return None
    messages = list(raw.get("messages") or [])
    updated_at = str(raw.get("updated_at") or "")
    created_at = str(raw.get("created_at") or updated_at)
    return {
        "discussion_id": raw.get("id") or discussion_id,
        "persona_ids": list(raw.get("persona_ids") or []),
        "created_at": created_at,
        "last_message_at": _discussion_last_message_at(messages, updated_at),
        "messages": messages,
    }


def new_meeting_id() -> str:
    return f"mtg_{uuid.uuid4().hex[:12]}"


def new_discussion_id() -> str:
    return f"disc_{uuid.uuid4().hex[:12]}"
