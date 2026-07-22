"""Outils agent du plugin cloud (sync dossier local)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.exceptions import ModelRetry

from app.agent.confirmation import raise_unless_approved
from app.agent.effects import classify_effect, effect_headline, protection_labels
from app.agent.human import build_human_summary
from app.agent.tools import ToolDeps
from app.i18n import t
from app.plugins.ports.remote_capability_gateway import (
    IdentityDelegation,
    open_remote_capability_gateway,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, resolve_plugin_data_dir
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.regards_access import open_managed_regards_port_for_cloud
from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
from app.plugins.workproba_cloud.sync_service import (
    is_cloud_enrolled,
    is_mount_configured,
    pull_project_artefacts_from_cloud,
)

UiMode = Literal["agent", "locked"]


def _tool_visibility(tool_def: dict[str, Any]) -> str:
    visibility = tool_def.get("visibility")
    if isinstance(visibility, str) and visibility.strip():
        return visibility.strip()
    return "guided"


def _is_restricted_tool_visibility(visibility: str) -> bool:
    return visibility in ("advanced", "standard")


def _is_restricted_ui_mode(ui_mode: UiMode) -> bool:
    return ui_mode == "locked"


def should_register_managed_tool(tool_def: dict[str, Any], ui_mode: UiMode) -> bool:
    return not (
        _is_restricted_ui_mode(ui_mode)
        and _is_restricted_tool_visibility(_tool_visibility(tool_def))
    )


def managed_tool_name(connector_id: str, tool_name: str) -> str:
    return f"managed__{connector_id}__{tool_name}"


def parse_managed_tool_name(tool_name: str) -> tuple[str, str] | None:
    if not tool_name.startswith("managed__"):
        return None
    rest = tool_name[len("managed__") :]
    cid, sep, name = rest.rpartition("__")
    if not sep or not cid or not name:
        return None
    return cid, name


def managed_connector_id_for_tool(tool_name: str) -> str:
    parsed = parse_managed_tool_name(tool_name)
    return parsed[0] if parsed else ""


def managed_tool_label(tool_name: str) -> str:
    parsed = parse_managed_tool_name(tool_name)
    if parsed is None:
        return tool_name
    return parsed[1].replace("_", " ")


def normalize_tool_input_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}, "additionalProperties": False}
    normalized = copy.deepcopy(schema)
    normalized.setdefault("type", "object")
    normalized.setdefault("properties", {})
    if normalized.get("additionalProperties") is not True:
        normalized["additionalProperties"] = False
    return normalized


def _connector_tools_from_cache(
    cloud_dir: Path, connector_id: str
) -> list[dict[str, Any]] | None:
    for connector in cloud_storage.get_known_managed_connectors(cloud_dir):
        if str(connector.get("id") or "") == connector_id:
            raw_tools = connector.get("tools")
            if isinstance(raw_tools, list):
                return [entry for entry in raw_tools if isinstance(entry, dict)]
            return []
    return None


def _find_cached_tool(
    cloud_dir: Path, connector_id: str, action: str
) -> dict[str, Any] | None:
    tools = _connector_tools_from_cache(cloud_dir, connector_id)
    if not tools:
        return None
    for tool_def in tools:
        tool_action = str(tool_def.get("action") or "")
        tool_name = str(tool_def.get("name") or "")
        if tool_action == action or tool_name == action:
            return tool_def
    return None


def _guided_generic_invoke_allowed(
    cloud_dir: Path,
    connector_id: str,
    action: str | None = None,
) -> bool:
    tools = _connector_tools_from_cache(cloud_dir, connector_id)
    if tools is None or not tools:
        return False
    if action:
        tool_def = _find_cached_tool(cloud_dir, connector_id, action)
        if tool_def is None:
            return False
        return _tool_visibility(tool_def) not in ("advanced", "standard")
    return any(
        _tool_visibility(tool_def) not in ("advanced", "standard")
        for tool_def in tools
    )


def _light_validate_payload(
    payload: dict[str, Any], schema: dict[str, Any]
) -> str | None:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}

    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if not isinstance(key, str):
                continue
            if key not in payload:
                return f"missing required field: {key}"

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        matched = False
        for branch in any_of:
            if not isinstance(branch, dict):
                continue
            branch_required = branch.get("required")
            if not isinstance(branch_required, list):
                continue
            if all(
                isinstance(req, str) and req in payload for req in branch_required
            ):
                matched = True
                break
        if not matched:
            return "payload does not match any required alternative"

    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, value in payload.items():
        prop_schema = properties.get(key)
        if not isinstance(prop_schema, dict):
            continue
        expected = prop_schema.get("type")
        if isinstance(expected, list):
            types = tuple(
                type_map[item]
                for item in expected
                if isinstance(item, str) and item in type_map
            )
            if types and not isinstance(value, types):
                return f"invalid type for field: {key}"
        elif isinstance(expected, str) and expected in type_map:
            if not isinstance(value, type_map[expected]):
                return f"invalid type for field: {key}"
    return None


def _validate_payload_against_schema(
    payload: dict[str, Any], schema: dict[str, Any]
) -> str | None:
    try:
        import jsonschema
    except ImportError:
        return _light_validate_payload(payload, schema)
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        return str(exc.message)
    return None


def _connector_cache_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    connector_id = entry.get("id")
    if not isinstance(connector_id, str) or not connector_id.strip():
        return None
    cached: dict[str, Any] = {
        "id": connector_id.strip(),
        "name": str(entry.get("name") or connector_id).strip(),
    }
    tools_raw = entry.get("tools")
    if isinstance(tools_raw, list):
        tools: list[dict[str, Any]] = []
        for tool_entry in tools_raw:
            if not isinstance(tool_entry, dict):
                continue
            name = tool_entry.get("name")
            action = tool_entry.get("action")
            if not isinstance(name, str) or not name.strip():
                continue
            if not isinstance(action, str) or not action.strip():
                continue
            tool_cached: dict[str, Any] = {
                "name": name.strip(),
                "action": action.strip(),
            }
            description = tool_entry.get("description")
            if isinstance(description, str):
                tool_cached["description"] = description
            effect = tool_entry.get("effect")
            if isinstance(effect, str):
                tool_cached["effect"] = effect
            visibility = tool_entry.get("visibility")
            if isinstance(visibility, str):
                tool_cached["visibility"] = visibility
            input_schema = tool_entry.get("input_schema")
            if isinstance(input_schema, dict):
                tool_cached["input_schema"] = input_schema
            tools.append(tool_cached)
        cached["tools"] = tools
    return cached


async def refresh_known_managed_connectors_cache(cloud_dir: Path) -> frozenset[str]:
    """Best-effort refresh du cache connecteurs/tools. Retourne les ids allowlistés."""
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url or not is_cloud_enrolled(cloud_dir):
        return frozenset()
    try:
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        payload = await client.list_connectors()
    except Exception:
        known = cloud_storage.get_known_managed_connectors(cloud_dir)
        return frozenset(
            str(entry.get("id"))
            for entry in known
            if isinstance(entry.get("id"), str) and str(entry.get("id")).strip()
        )
    raw = payload.get("connectors") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return frozenset()
    connectors: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cached = _connector_cache_entry(entry)
        if cached is not None:
            connectors.append(cached)
    cloud_storage.save_known_managed_connectors(cloud_dir, connectors)
    return frozenset(str(entry["id"]) for entry in connectors)


def make_managed_tool_shim(
    connector_id: str,
    tool_def: dict[str, Any],
    *,
    gate_tool_name: str,
):
    action = str(tool_def["action"])

    async def _shim(ctx: RunContext[ToolDeps], **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": action}
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value
        return await invoke_managed_connector_impl(
            ctx,
            connector_id=connector_id,
            payload=payload,
            gate_tool_name=gate_tool_name,
        )

    return _shim


def register_managed_connector_tools(
    agent: Agent[ToolDeps, str],
    cloud_dir: Path,
    *,
    ui_mode: UiMode,
    managed_allowed_connector_ids: frozenset[str] | None = None,
) -> None:
    for connector in cloud_storage.get_known_managed_connectors(cloud_dir):
        connector_id = str(connector.get("id") or "")
        if not connector_id or not cloud_storage.is_managed_connector_enabled(
            cloud_dir, connector_id
        ):
            continue
        # Turn snapshot: when provided, only register connectors frozen for this turn.
        if (
            managed_allowed_connector_ids is not None
            and connector_id not in managed_allowed_connector_ids
        ):
            continue
        tools = connector.get("tools")
        if not isinstance(tools, list):
            continue
        for tool_def in tools:
            if not isinstance(tool_def, dict):
                continue
            if not should_register_managed_tool(tool_def, ui_mode):
                continue
            tool_name_value = tool_def.get("name")
            if not isinstance(tool_name_value, str) or not tool_name_value.strip():
                continue
            tool_name = managed_tool_name(connector_id, tool_name_value.strip())
            description = str(tool_def.get("description") or tool_name_value).strip()
            json_schema = normalize_tool_input_schema(tool_def.get("input_schema"))
            shim = make_managed_tool_shim(
                connector_id,
                tool_def,
                gate_tool_name=tool_name,
            )
            tool = Tool.from_schema(
                shim,
                name=tool_name,
                description=description,
                json_schema=json_schema,
                takes_ctx=True,
            )
            agent._function_toolset.add_tool(tool)


def build_managed_connectors_agent_prompt(
    locale: str,
    items: list[tuple[str, str, bool]],
) -> str:
    """Fragment advisory : connecteurs org et activation locale."""
    if not items:
        return ""
    lines = [t(locale, "tools.managed_connectors_header")]
    for connector_id, name, enabled_local in items:
        if enabled_local:
            lines.append(
                t(
                    locale,
                    "tools.managed_connectors_enabled",
                    id=connector_id,
                    name=name,
                )
            )
        else:
            lines.append(
                t(
                    locale,
                    "tools.managed_connectors_disabled",
                    id=connector_id,
                    name=name,
                )
            )
    return "\n".join(lines)


def _cloud_data_dir(ctx: RunContext[ToolDeps]) -> Path:
    data_dir = resolve_plugin_data_dir(
        PLUGIN_WORKPROBA_CLOUD,
        ctx.deps.context.plugin_data_dir,
    )
    if data_dir is None:
        raise ModelRetry("Plugin cloud: plugin_data_dir manquant")
    return data_dir


def register_cloud_tools(
    agent: Agent[ToolDeps, str],
    *,
    plugin_data_dir: Path | None = None,
    ui_mode: UiMode = "agent",
    managed_allowed_connector_ids: frozenset[str] | None = None,
) -> None:
    cloud_dir = resolve_plugin_data_dir(PLUGIN_WORKPROBA_CLOUD, plugin_data_dir)
    if cloud_dir is not None:
        register_managed_connector_tools(
            agent,
            cloud_dir,
            ui_mode=ui_mode,
            managed_allowed_connector_ids=managed_allowed_connector_ids,
        )

    @agent.system_prompt
    async def managed_connectors_prompt(ctx: RunContext[ToolDeps]) -> str:
        locale = ctx.deps.context.locale
        try:
            cloud_dir = _cloud_data_dir(ctx)
        except ModelRetry:
            return ""

        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if not base_url or not is_cloud_enrolled(cloud_dir):
            return ""

        # Snapshot du tour (cache disque) : même source que l'enregistrement des tools.
        connectors = cloud_storage.get_known_managed_connectors(cloud_dir)
        if not connectors:
            return t(locale, "tools.managed_connectors_empty")

        turn_allowed = ctx.deps.context.managed_allowed_connector_ids
        items = [
            (
                str(entry["id"]),
                str(entry.get("name") or entry["id"]),
                (
                    str(entry["id"]) in turn_allowed
                    if turn_allowed is not None
                    else cloud_storage.is_managed_connector_enabled(
                        cloud_dir, str(entry["id"])
                    )
                ),
            )
            for entry in connectors
            if isinstance(entry.get("id"), str) and str(entry.get("id")).strip()
        ]
        return build_managed_connectors_agent_prompt(locale, items)

    @agent.tool
    async def sync_to_cloud(ctx: RunContext[ToolDeps], project_id: str) -> dict[str, Any]:
        """Push local published artefacts to the configured cloud mount folder.

        Not available when enrolled with cloud as source of truth; use publish instead.

        Args:
            project_id: Target collaborative project id.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)

        if is_cloud_enrolled(cloud_dir):
            raise ModelRetry(t(locale, "cloud.use_cloud_sot_not_mirror_sync"))

        if not is_mount_configured(cloud_dir):
            raise ModelRetry(t(locale, "cloud.not_configured"))

        try:
            sync_port = open_sync_port_for_cloud(cloud_dir.parent)
            result = cloud_storage.sync_project(
                plugin_data_dir=cloud_dir,
                sync_port=sync_port,
                project_id=project_id,
            )
        except PermissionError as exc:
            raise ModelRetry(str(exc)) from exc
        except ValueError as exc:
            code = str(exc)
            key = f"cloud.{code}" if code.startswith("cloud_") else f"errors.{code}"
            message = t(locale, key)
            if message == key:
                message = str(exc)
            raise ModelRetry(message) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        synced = result.get("synced") or []
        human_summary = build_human_summary(
            "sync_to_cloud",
            {
                "project_id": project_id,
                "count": len(synced),
                "mount_path": result.get("mount_path", ""),
            },
            locale=locale,
        )
        if ctx.deps.context.plugin_data_dir is not None:
            from app.agent.work_events import audit_details_with_work_id
            from app.audit import log_event, resolve_app_data_dir

            log_event(
                resolve_app_data_dir(ctx.deps.context.plugin_data_dir),
                "cloud.sync",
                "agent",
                audit_details_with_work_id(
                    {
                        "project_id": project_id,
                        "count": len(synced),
                        "mount_path": result.get("mount_path", ""),
                    },
                    ctx.deps.context.work_id,
                    session_id=ctx.deps.context.session_id,
                ),
                enabled=ctx.deps.context.audit_enabled,
            )
        return {**result, "human_summary": human_summary, "count": len(synced)}

    @agent.tool
    async def sync_from_cloud(ctx: RunContext[ToolDeps], project_id: str) -> dict[str, Any]:
        """Pull confirmed project artefacts from the cloud control plane into local mirror.

        Not available when enrolled with cloud as source of truth; use open artefact instead.

        Args:
            project_id: Target collaborative project id.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)

        if is_cloud_enrolled(cloud_dir):
            raise ModelRetry(t(locale, "cloud.use_cloud_sot_not_mirror_sync"))

        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if not base_url:
            raise ModelRetry(t(locale, "cloud.not_configured"))

        try:
            sync_port = open_sync_port_for_cloud(cloud_dir.parent)
            client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
            result = await pull_project_artefacts_from_cloud(
                cloud_dir=cloud_dir,
                sync_port=sync_port,
                project_id=project_id,
                client=client,
            )
        except PermissionError as exc:
            raise ModelRetry(str(exc)) from exc
        except ValueError as exc:
            code = str(exc)
            key = f"cloud.{code}" if code.startswith("cloud_") else f"errors.{code}"
            message = t(locale, key)
            if message == key:
                message = str(exc)
            raise ModelRetry(message) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        pulled = result.get("pulled") or []
        human_summary = build_human_summary(
            "sync_from_cloud",
            {"project_id": project_id, "count": len(pulled)},
            locale=locale,
        )
        return {**result, "human_summary": human_summary, "count": len(pulled)}

    @agent.tool
    async def enroll_to_cloud(
        ctx: RunContext[ToolDeps],
        base_url: str,
        bearer_token: str | None = None,
        device_code: str | None = None,
        join_token: str | None = None,
        org_id: str | None = None,
        device_name: str | None = None,
    ) -> dict[str, Any]:
        """Enroll this desktop with the cloud control plane (join token, bearer or device code).

        Args:
            base_url: Control plane API base URL.
            bearer_token: Optional bearer token for direct auth.
            device_code: Optional device enrollment code.
            join_token: Optional zero-config join invitation code.
            org_id: Optional organization id (with bearer or device code).
            device_name: Optional device display name for join enrollment.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)
        cloud_storage.save_config(cloud_dir, {"base_url": base_url.rstrip("/")})
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        try:
            import socket

            if join_token:
                resolved_name = (device_name or "").strip() or socket.gethostname() or "workproba-desktop"
                join_payload = await client.join_with_token(
                    token=join_token,
                    device_name=resolved_name,
                )
                tokens = client.load_tokens()
                result = {
                    **join_payload,
                    "authenticated": bool(tokens.get("access_token")),
                    "method": "join_token",
                    "org_id": tokens.get("org_id"),
                }
            elif bearer_token:
                result = await client.authenticate(
                    bearer_token=bearer_token,
                    device_code=None,
                    org_id=org_id,
                )
            elif device_code:
                result = await client.authenticate(
                    bearer_token=None,
                    device_code=device_code,
                    org_id=org_id,
                )
            elif org_id:
                raise ValueError("join_token_required")
            else:
                raise ValueError("cloud_auth_required")
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        human_summary = build_human_summary(
            "enroll_to_cloud",
            {"base_url": base_url, "authenticated": result.get("authenticated")},
            locale=locale,
        )
        return {**result, "human_summary": human_summary}

    @agent.tool
    async def sync_managed_regards(
        ctx: RunContext[ToolDeps],
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Pull signed regards catalogs from the control plane and install locally.

        Args:
            org_id: Optional organization id override.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)
        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if not base_url:
            raise ModelRetry(t(locale, "cloud.not_configured"))

        try:
            client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
            port = open_managed_regards_port_for_cloud(cloud_dir.parent)
            result = await client.pull_and_install_regards(port, org_id=org_id)
        except PermissionError as exc:
            raise ModelRetry(str(exc)) from exc
        except ValueError as exc:
            code = str(exc)
            key = f"cloud.{code}" if code.startswith("cloud_") else f"errors.{code}"
            message = t(locale, key)
            if message == key:
                message = str(exc)
            raise ModelRetry(message) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

        human_summary = build_human_summary(
            "sync_managed_regards",
            {"count": result.get("count", 0)},
            locale=locale,
        )
        return {**result, "human_summary": human_summary}

    @agent.tool
    async def invoke_managed_connector(
        ctx: RunContext[ToolDeps],
        connector_id: str,
        payload_json: str = "{}",
    ) -> dict[str, Any]:
        """Invoke a managed Improba Cloud connector (Mode A transport relay).
        Prefer the dedicated managed_* tools when available. This generic tool is a fallback.

        Args:
            connector_id: Managed connector id (e.g. ihora, echo, ihora.shaped).
            payload_json: JSON object string passed as connector payload.
        """
        import json

        locale = ctx.deps.context.locale
        try:
            payload = json.loads(payload_json) if payload_json.strip() else {}
            if not isinstance(payload, dict):
                raise ValueError("payload_must_be_object")
        except json.JSONDecodeError as exc:
            raise ModelRetry(f"invalid_payload_json: {exc}") from exc
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

        return await invoke_managed_connector_impl(
            ctx,
            connector_id=connector_id,
            payload=payload,
            gate_tool_name="invoke_managed_connector",
            human_connector_id=connector_id,
            locale=locale,
        )


async def invoke_managed_connector_impl(
    ctx: RunContext[ToolDeps],
    *,
    connector_id: str,
    payload: dict[str, Any],
    gate_tool_name: str,
    human_connector_id: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    locale = locale or ctx.deps.context.locale
    deps = ctx.deps
    cloud_dir = _cloud_data_dir(ctx)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url:
        raise ModelRetry(t(locale, "cloud.not_configured"))

    if not deps.context.permissions_network:
        raise ModelRetry(t(locale, "errors.network_locked"))

    # Ordre : local → auth → allowlist → gate humaine → re-check local (TOCTOU) → invoke.
    if not cloud_storage.is_managed_connector_enabled(cloud_dir, connector_id):
        raise ModelRetry(
            t(locale, "cloud.connector_disabled_locally", connector_id=connector_id)
        )

    ui_mode = getattr(deps.context, "ui_mode", "agent")
    action_raw = payload.get("action")
    action = action_raw.strip() if isinstance(action_raw, str) else None
    if _is_restricted_ui_mode(ui_mode) and not _guided_generic_invoke_allowed(
        cloud_dir, connector_id, action=action
    ):
        raise ModelRetry(
            t(locale, "cloud.connector_advanced_only", connector_id=connector_id)
        )

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    tokens = client.load_tokens()
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise ModelRetry(t(locale, "cloud.not_authenticated"))

    org_id = tokens.get("org_id")
    org_id_str = org_id.strip() if isinstance(org_id, str) else None
    device_id = tokens.get("device_id")
    subject = (
        device_id.strip()
        if isinstance(device_id, str) and device_id.strip()
        else "local"
    )

    try:
        allowed = deps.context.managed_allowed_connector_ids
        if allowed is None:
            try:
                allowed = await client.fetch_allowed_connector_ids()
            except PermissionError as exc:
                raise ModelRetry(t(locale, "cloud.connectors_auth_failed")) from exc
            except Exception as exc:  # noqa: BLE001
                raise ModelRetry(t(locale, "cloud.connectors_load_failed")) from exc

        if connector_id not in allowed:
            raise ModelRetry(f"connector_not_allowed:{connector_id}")

        if action:
            tool_def = _find_cached_tool(cloud_dir, connector_id, action)
            if tool_def is not None:
                input_schema = tool_def.get("input_schema")
                if isinstance(input_schema, dict):
                    payload_for_validation = {
                        key: value for key, value in payload.items() if key != "action"
                    }
                    validation_error = _validate_payload_against_schema(
                        payload_for_validation, input_schema
                    )
                    if validation_error:
                        raise ModelRetry(
                            t(
                                locale,
                                "cloud.connector_payload_invalid",
                                connector_id=connector_id,
                                action=action,
                                detail=validation_error,
                            )
                        )

        gate = deps.confirmation_gate
        if gate is not None:
            summary_connector_id = human_connector_id or connector_id
            human_summary = build_human_summary(
                gate_tool_name,
                {
                    "connector_id": summary_connector_id,
                    "tool_name": gate_tool_name,
                    "action": action or "",
                },
                locale=locale,
            )
            proposal = classify_effect(
                gate_tool_name,
                {
                    "connector_id": summary_connector_id,
                    "tool_name": gate_tool_name,
                    "action": action or "",
                },
                permissions_network=deps.context.permissions_network,
            )
            if proposal is None:
                raise ModelRetry(f"Effet non classifiable pour {gate_tool_name}")
            proposal = proposal.model_copy(update={"human_summary": human_summary})
            proposal = proposal.model_copy(
                update={
                    "headline": effect_headline(proposal, locale),
                    "protection_labels": protection_labels(proposal, locale),
                }
            )
            outcome = await gate.request_effect(
                tool_call_id=ctx.tool_call_id or "",
                proposal=proposal,
                audit_app_data_dir=deps.context.workspace_data_dir,
                audit_enabled=deps.context.audit_enabled,
            )
            raise_unless_approved(outcome, locale)

        if not cloud_storage.is_managed_connector_enabled(cloud_dir, connector_id):
            raise ModelRetry(
                t(locale, "cloud.connector_disabled_locally", connector_id=connector_id)
            )

        plugins_root = cloud_dir.parent
        gateway = open_remote_capability_gateway(
            caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
            caller_permissions=frozenset(
                [
                    "capability:remote",
                    "network:improba-cloud",
                ]
            ),
            plugins_root=plugins_root,
            base_url=base_url,
            allowed_capability_ids=allowed,
        )
        identity = IdentityDelegation(
            subject_id=subject,
            org_id=org_id_str,
            scopes=frozenset({"connectors:invoke"}),
            access_token=access_token.strip(),
        )
        result = await gateway.invoke_remote(connector_id, payload, identity)
    except ModelRetry:
        raise
    except PermissionError as exc:
        raise ModelRetry(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

    summary_connector_id = human_connector_id or connector_id
    human_summary = build_human_summary(
        gate_tool_name,
        {
            "connector_id": summary_connector_id,
            "tool_name": gate_tool_name,
            "ok": bool(result.get("ok", True)),
        },
        locale=locale,
    )
    return {**result, "human_summary": human_summary}
