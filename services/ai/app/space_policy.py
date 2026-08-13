"""Politique d'approbation par espace (space_policy.json)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

POLICY_VERSION = 1
POLICY_FILE = "space_policy.json"

ApprovalMode = Literal["security", "trust"]
DEFAULT_APPROVAL_MODE: ApprovalMode = "security"


def policy_path(workspace_data_dir: Path) -> Path:
    return workspace_data_dir / POLICY_FILE


@dataclass
class SpacePolicy:
    version: int = POLICY_VERSION
    approval_mode: ApprovalMode = DEFAULT_APPROVAL_MODE

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "approvalMode": self.approval_mode,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> SpacePolicy:
        mode = raw.get("approvalMode", DEFAULT_APPROVAL_MODE)
        if mode not in ("security", "trust"):
            mode = DEFAULT_APPROVAL_MODE

        version = raw.get("version", POLICY_VERSION)
        if not isinstance(version, int):
            version = POLICY_VERSION

        return cls(version=version, approval_mode=mode)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_approval_mode(workspace_data_dir: Path) -> ApprovalMode:
    path = policy_path(workspace_data_dir)
    if not path.is_file():
        return DEFAULT_APPROVAL_MODE
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_APPROVAL_MODE
    if not isinstance(raw, dict):
        return DEFAULT_APPROVAL_MODE
    return SpacePolicy.from_json(raw).approval_mode


def set_approval_mode(workspace_data_dir: Path, mode: str) -> ApprovalMode:
    if mode not in ("security", "trust"):
        mode = DEFAULT_APPROVAL_MODE
    approval_mode: ApprovalMode = mode  # type: ignore[assignment]
    policy = SpacePolicy(approval_mode=approval_mode)
    save(workspace_data_dir, policy)
    return approval_mode


def save(workspace_data_dir: Path, policy: SpacePolicy) -> SpacePolicy:
    workspace_data_dir.mkdir(parents=True, exist_ok=True)
    target = policy_path(workspace_data_dir)
    payload = policy.to_json()
    fd, tmp_name = tempfile.mkstemp(
        prefix=".space_policy.",
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
    return policy
