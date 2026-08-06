"""Résolution du panel tools d'un agent métier contre le cache connecteurs desktop."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.plugins.workproba_cloud.plugin import managed_tool_name

JsonDict = dict[str, Any]


SpecialistRunMode = str  # "regard" | "operative"
ToolFilter = Literal["disabled", "pure_read", "allowlist"]

_DEFAULT_TOOL_FILTERS: dict[str, ToolFilter] = {
    "regard": "pure_read",
    "operative": "allowlist",
}


@dataclass(frozen=True)
class ResolvedPanelTool:
    connector_id: str
    tool_name: str
    managed_name: str
    tool_def: JsonDict
    effect: str


@dataclass(frozen=True)
class ResolvedReadTool:
    connector_id: str
    tool_name: str
    managed_name: str
    tool_def: JsonDict


@dataclass(frozen=True)
class DegradedTool:
    connector_id: str
    tool: str
    reason: str

    def to_dict(self) -> JsonDict:
        return {
            "connector_id": self.connector_id,
            "tool": self.tool,
            "reason": self.reason,
        }


@dataclass
class PanelToolsResolution:
    allowed_read_tools: list[ResolvedReadTool] = field(default_factory=list)
    allowed_panel_tools: list[ResolvedPanelTool] = field(default_factory=list)
    degraded_tools: list[DegradedTool] = field(default_factory=list)


def active_connectors_snapshot(cloud_dir: Path) -> list[JsonDict]:
    """Connecteurs connus du cache desktop, activés localement."""
    from app.plugins.workproba_cloud import storage as cloud_storage

    snapshot: list[JsonDict] = []
    for connector in cloud_storage.get_known_managed_connectors(cloud_dir):
        connector_id = str(connector.get("id") or "").strip()
        if not connector_id:
            continue
        if not cloud_storage.is_managed_connector_enabled(cloud_dir, connector_id):
            continue
        snapshot.append(connector)
    return snapshot


def _tool_ref_key(ref: JsonDict) -> tuple[str, str] | None:
    connector_id = ref.get("connector_id")
    tool = ref.get("tool")
    if not isinstance(connector_id, str) or not connector_id.strip():
        return None
    if not isinstance(tool, str) or not tool.strip():
        return None
    return connector_id.strip(), tool.strip()


def _parse_panel_refs(specialist: JsonDict) -> list[JsonDict]:
    tools = specialist.get("tools")
    if not isinstance(tools, dict):
        return []
    allowed_raw = tools.get("allowed")
    forbidden_raw = tools.get("forbidden")
    allowed = [entry for entry in (allowed_raw or []) if isinstance(entry, dict)]
    forbidden = {
        key
        for entry in (forbidden_raw or [])
        if isinstance(entry, dict)
        for key in [_tool_ref_key(entry)]
        if key is not None
    }
    effective: list[JsonDict] = []
    for entry in allowed:
        key = _tool_ref_key(entry)
        if key is None or key in forbidden:
            continue
        effective.append(entry)
    return effective


def _connector_index(connectors_snapshot: list[JsonDict]) -> dict[str, JsonDict]:
    index: dict[str, JsonDict] = {}
    for connector in connectors_snapshot:
        connector_id = connector.get("id")
        if isinstance(connector_id, str) and connector_id.strip():
            index[connector_id.strip()] = connector
    return index


def resolve_tool_filter(
    specialist: JsonDict,
    mode: SpecialistRunMode,
) -> ToolFilter:
    """Lit modes.{mode}.tool_filter avec défauts cloud (regard=pure_read, operative=allowlist)."""
    modes = specialist.get("modes")
    if not isinstance(modes, dict):
        return _DEFAULT_TOOL_FILTERS.get(mode, "pure_read")
    mode_cfg = modes.get(mode)
    if not isinstance(mode_cfg, dict):
        return _DEFAULT_TOOL_FILTERS.get(mode, "pure_read")
    raw = mode_cfg.get("tool_filter")
    if raw in ("disabled", "pure_read", "allowlist"):
        return raw  # type: ignore[return-value]
    return _DEFAULT_TOOL_FILTERS.get(mode, "pure_read")


def _find_tool_in_connector(connector: JsonDict, tool_name: str) -> JsonDict | None:
    tools = connector.get("tools")
    if not isinstance(tools, list):
        return None
    for tool_def in tools:
        if not isinstance(tool_def, dict):
            continue
        name = str(tool_def.get("name") or "")
        action = str(tool_def.get("action") or "")
        if tool_name == name or tool_name == action:
            return tool_def
    return None


def resolve_panel_tools(
    specialist: JsonDict,
    connectors_snapshot: list[JsonDict],
    *,
    mode: SpecialistRunMode = "regard",
) -> PanelToolsResolution:
    """Résout les refs panel → tools managed ; le reste est dégradé."""
    refs = _parse_panel_refs(specialist)
    index = _connector_index(connectors_snapshot)
    allowed_read: list[ResolvedReadTool] = []
    allowed_panel: list[ResolvedPanelTool] = []
    degraded: list[DegradedTool] = []

    for ref in refs:
        key = _tool_ref_key(ref)
        if key is None:
            continue
        connector_id, tool_name = key

        connector = index.get(connector_id)
        if connector is None:
            degraded.append(
                DegradedTool(connector_id, tool_name, "connector_unavailable")
            )
            continue

        tool_def = _find_tool_in_connector(connector, tool_name)
        if tool_def is None:
            degraded.append(DegradedTool(connector_id, tool_name, "tool_unavailable"))
            continue

        effect = str(tool_def.get("effect") or "")
        if mode == "regard":
            if effect != "read":
                degraded.append(DegradedTool(connector_id, tool_name, "effect_not_read"))
                continue
        elif effect not in {"read", "write"}:
            degraded.append(DegradedTool(connector_id, tool_name, "effect_unsupported"))
            continue

        managed_name = managed_tool_name(connector_id, tool_name)
        allowed_panel.append(
            ResolvedPanelTool(
                connector_id=connector_id,
                tool_name=tool_name,
                managed_name=managed_name,
                tool_def=tool_def,
                effect=effect,
            )
        )
        if effect == "read":
            allowed_read.append(
                ResolvedReadTool(
                    connector_id=connector_id,
                    tool_name=tool_name,
                    managed_name=managed_name,
                    tool_def=tool_def,
                )
            )

    return PanelToolsResolution(
        allowed_read_tools=allowed_read,
        allowed_panel_tools=allowed_panel,
        degraded_tools=degraded,
    )
