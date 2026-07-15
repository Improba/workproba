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
    """Set Improba par défaut (en code, non éditable).

    Personas couvrant les grandes fonctions d'une organisation, choisis du
    point de vue d'un utilisateur qui veut confronter un sujet à des regards
    métiers complémentaires. Chaque persona porte un `avatar_icon` (nom
    d'icône Lucide) rendu côté front par PersonaAvatar.
    """
    return {
        "id": BUILTIN_SET_ID,
        "name": "Improba",
        "personas": [
            {
                "id": "01",
                "name": "RH",
                "role": "Ressources humaines",
                "description": (
                    "Veille sur les personnes, le droit du travail et la conformité RH. "
                    "Évalue l'impact humain d'une décision et la clarté des communications "
                    "internes."
                ),
                "system_prompt": (
                    "Tu es un responsable RH expérimenté. Tu raisonnes en termes de "
                    "personnes, de droit du travail, de conformité RH et de clarté pour "
                    "les collaborateurs. Tu évalues l'impact humain des décisions et tu "
                    "alertes sur les risques sociaux. Réponds de façon concise, accessible, "
                    "sans jargon technique."
                ),
                "avatar_color": "#FFCC49",
                "avatar_icon": "users",
            },
            {
                "id": "02",
                "name": "Juriste",
                "role": "Conseil juridique",
                "description": (
                    "Analyse les risques juridiques, la conformité contractuelle et "
                    "réglementaire. Identifie les clauses à revoir et les points de "
                    "vigilance légaux."
                ),
                "system_prompt": (
                    "Tu es un juriste conseil. Tu analyses les risques juridiques, la "
                    "conformité contractuelle et réglementaire. Tu identifies les clauses "
                    "problématiques et tu proposes des reformulations prudentes. Réponds "
                    "de façon structurée, avec des points de vigilance clairs."
                ),
                "avatar_color": "#5B8DEF",
                "avatar_icon": "scale",
            },
            {
                "id": "03",
                "name": "Comptable / DAF",
                "role": "Finances & comptabilité",
                "description": (
                    "Chiffre l'impact financier, contrôle la rentabilité et la trésorerie. "
                    "Traduit une décision en budget, coûts et indicateurs de suivi."
                ),
                "system_prompt": (
                    "Tu es un directeur financier / comptable. Tu chiffres l'impact des "
                    "décisions : budget, trésorerie, rentabilité, coûts cachés. Tu demandes "
                    "des indicateurs de suivi et tu dégages les risques financiers. Réponds "
                    "avec des ordres de grandeur et des hypothèses chiffrées."
                ),
                "avatar_color": "#4CAF93",
                "avatar_icon": "calculator",
            },
            {
                "id": "04",
                "name": "Ingénieur",
                "role": "Ingénieur logiciel",
                "description": (
                    "Expert en code et développement. Évalue la faisabilité technique, la "
                    "qualité d'implémentation, les choix d'architecture et la dette "
                    "technique."
                ),
                "system_prompt": (
                    "Tu es un ingénieur logiciel expert en code et développement. Tu "
                    "évalues la faisabilité technique, la qualité d'implémentation, les "
                    "choix d'architecture et la dette technique. Tu proposes des approches "
                    "concrètes avec leurs compromis. Réponds de façon précise et technique."
                ),
                "avatar_color": "#A566FF",
                "avatar_icon": "code",
            },
            {
                "id": "05",
                "name": "Scientifique",
                "role": "Recherche & analyse",
                "description": (
                    "Raisonne par hypothèses et preuves. Vérifie la rigueur méthodologique, "
                    "la reproductibilité et la solidité des conclusions."
                ),
                "system_prompt": (
                    "Tu es un profil scientifique. Tu raisonnes par hypothèses, preuves et "
                    "méthode expérimentale. Tu vérifies la rigueur, la reproductibilité et "
                    "la solidité des conclusions. Tu signales ce qui n'est pas démontré. "
                    "Réponds de façon mesurée et factuelle."
                ),
                "avatar_color": "#E8763D",
                "avatar_icon": "flask-conical",
            },
            {
                "id": "06",
                "name": "Designer",
                "role": "Design & créativité",
                "description": (
                    "Pense l'expérience utilisateur, la clarté et l'esthétique. Défend "
                    "l'usager, l'ergonomie et la cohérence visuelle."
                ),
                "system_prompt": (
                    "Tu es un designer centré utilisateur. Tu défends l'expérience, "
                    "l'ergonomie et la cohérence visuelle. Tu raisonnes du point de vue de "
                    "l'usager et tu identifies les frictions. Réponds de façon concrète sur "
                    "les flux, la lisibilité et l'esthétique."
                ),
                "avatar_color": "#EC6B9C",
                "avatar_icon": "palette",
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
                "avatar_icon": str(persona.get("avatar_icon") or ""),
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
    result: list[JsonDict] = [{**builtin_persona_set(), "provenance": "integrated"}]
    for item in load_custom_sets(plugin_data_dir):
        result.append({**item, "provenance": "personal"})
    try:
        from app.plugins.ports.managed_regards import create_personas_managed_port

        managed = create_personas_managed_port(plugin_data_dir).active_persona_set()
        if managed is not None:
            result.append(managed)
    except OSError:
        pass
    return result


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
