"""Profil d'activation des capacites par espace (capabilities.json)."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

PROFILE_VERSION = 1
CAPABILITIES_FILE = "capabilities.json"
MANAGED_PREFIX = "managed:"

LOCAL_CAPABILITY_IDS = frozenset(
    {
        "workproba_cloud",
        "projects",
        "regards",
        "web_navigation",
    }
)

LOCAL_ENABLE_BY_DEFAULT_IN_PROJECTS: dict[str, bool] = {
    "workproba_cloud": True,
    "projects": True,
    "regards": True,
    "web_navigation": False,
}

MANAGED_CONNECTOR_ENABLE_BY_DEFAULT_IN_PROJECTS: dict[str, bool] = {
    "echo": False,
    "ihora.shaped": False,
    "ihora": True,
}

InitializedFrom = Literal["defaults", "migration", "user"]


class InvalidCapabilityIdError(ValueError):
    """Capability id hors catalogue."""


def capabilities_path(workspace_data_dir: Path) -> Path:
    return workspace_data_dir / CAPABILITIES_FILE


def is_managed_capability_id(capability_id: str) -> bool:
    return capability_id.startswith(MANAGED_PREFIX)


def connector_id_from_managed_capability(capability_id: str) -> str:
    return capability_id[len(MANAGED_PREFIX) :]


def is_valid_capability_id(capability_id: str) -> bool:
    if not isinstance(capability_id, str) or not capability_id.strip():
        return False
    if capability_id in LOCAL_CAPABILITY_IDS:
        return True
    if is_managed_capability_id(capability_id):
        connector_id = connector_id_from_managed_capability(capability_id)
        return bool(connector_id.strip())
    return False


def validate_capability_id(capability_id: str) -> None:
    if not is_valid_capability_id(capability_id):
        raise InvalidCapabilityIdError(f"unknown_capability_id:{capability_id}")


def enable_by_default_in_projects(
    capability_id: str,
    *,
    managed_defaults: dict[str, bool] | None = None,
) -> bool:
    if is_managed_capability_id(capability_id):
        connector_id = connector_id_from_managed_capability(capability_id)
        defaults = managed_defaults or MANAGED_CONNECTOR_ENABLE_BY_DEFAULT_IN_PROJECTS
        return bool(defaults.get(connector_id, False))
    return bool(LOCAL_ENABLE_BY_DEFAULT_IN_PROJECTS.get(capability_id, False))


def build_initial_wanted(
    entitled_ids: Iterable[str],
    *,
    enable_by_default: Callable[[str], bool] | None = None,
) -> dict[str, bool]:
    fn = enable_by_default or enable_by_default_in_projects
    wanted: dict[str, bool] = {}
    seen: set[str] = set()
    for raw_id in entitled_ids:
        cap_id = str(raw_id).strip()
        if not cap_id or cap_id in seen:
            continue
        seen.add(cap_id)
        if not is_valid_capability_id(cap_id):
            continue
        if fn(cap_id):
            wanted[cap_id] = True
    return wanted


@dataclass
class CapabilitiesProfile:
    wanted: dict[str, bool]
    initialized_from: InitializedFrom
    migrated_at: str | None = None
    updated_at: str = ""
    version: int = PROFILE_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "wanted": dict(self.wanted),
            "initializedFrom": self.initialized_from,
            "migratedAt": self.migrated_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> CapabilitiesProfile:
        wanted_raw = raw.get("wanted", {})
        wanted: dict[str, bool] = {}
        if isinstance(wanted_raw, dict):
            for key, value in wanted_raw.items():
                if isinstance(key, str) and isinstance(value, bool):
                    wanted[key] = value

        initialized_from = raw.get("initializedFrom", "defaults")
        if initialized_from not in ("defaults", "migration", "user"):
            initialized_from = "defaults"

        migrated_at = raw.get("migratedAt")
        if migrated_at is not None and not isinstance(migrated_at, str):
            migrated_at = None

        updated_at = raw.get("updatedAt", "")
        if not isinstance(updated_at, str):
            updated_at = ""

        version = raw.get("version", PROFILE_VERSION)
        if not isinstance(version, int):
            version = PROFILE_VERSION

        return cls(
            wanted=wanted,
            initialized_from=initialized_from,
            migrated_at=migrated_at,
            updated_at=updated_at,
            version=version,
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load(workspace_data_dir: Path) -> CapabilitiesProfile | None:
    path = capabilities_path(workspace_data_dir)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("invalid_capabilities_profile")
    return CapabilitiesProfile.from_json(raw)


def save(workspace_data_dir: Path, profile: CapabilitiesProfile) -> CapabilitiesProfile:
    workspace_data_dir.mkdir(parents=True, exist_ok=True)
    profile.updated_at = _now_iso()
    target = capabilities_path(workspace_data_dir)
    payload = profile.to_json()
    fd, tmp_name = tempfile.mkstemp(
        prefix=".capabilities.",
        suffix=".json.tmp",
        dir=str(workspace_data_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return profile


def ensure_initialized(
    workspace_data_dir: Path,
    entitled_ids: Iterable[str],
    *,
    initialized_from: InitializedFrom = "defaults",
) -> CapabilitiesProfile:
    existing = load(workspace_data_dir)
    if existing is not None:
        return existing

    now = _now_iso()
    profile = CapabilitiesProfile(
        wanted=build_initial_wanted(entitled_ids),
        initialized_from=initialized_from,
        migrated_at=now if initialized_from == "migration" else None,
        updated_at=now,
    )
    save(workspace_data_dir, profile)
    return profile


def set_wanted(
    workspace_data_dir: Path,
    updates: dict[str, bool],
) -> CapabilitiesProfile:
    profile = load(workspace_data_dir)
    if profile is None:
        raise ValueError("capabilities_profile_not_initialized")

    for cap_id, value in updates.items():
        validate_capability_id(cap_id)
        profile.wanted[cap_id] = value

    save(workspace_data_dir, profile)
    return profile
