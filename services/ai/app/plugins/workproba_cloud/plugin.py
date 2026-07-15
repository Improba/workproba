"""Outils agent du plugin cloud (sync dossier local)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.human import build_human_summary
from app.agent.tools import ToolDeps
from app.i18n import t
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, resolve_plugin_data_dir
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.regards_access import open_managed_regards_port_for_cloud
from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud


def _cloud_data_dir(ctx: RunContext[ToolDeps]) -> Path:
    data_dir = resolve_plugin_data_dir(
        PLUGIN_WORKPROBA_CLOUD,
        ctx.deps.context.plugin_data_dir,
    )
    if data_dir is None:
        raise ModelRetry("Plugin cloud: plugin_data_dir manquant")
    return data_dir


def register_cloud_tools(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def sync_to_cloud(ctx: RunContext[ToolDeps], project_id: str) -> dict[str, Any]:
        """Sync published project artefacts to the configured local cloud folder.

        Args:
            project_id: Target collaborative project id.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)

        if not cloud_storage.get_mount_path(cloud_dir):
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
    async def enroll_to_cloud(
        ctx: RunContext[ToolDeps],
        base_url: str,
        bearer_token: str | None = None,
        device_code: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Enroll this desktop with the cloud control plane (bearer or device code stub).

        Args:
            base_url: Control plane API base URL.
            bearer_token: Optional bearer token for direct auth.
            device_code: Optional device enrollment code.
            org_id: Optional organization id.
        """
        locale = ctx.deps.context.locale
        cloud_dir = _cloud_data_dir(ctx)
        cloud_storage.save_config(cloud_dir, {"base_url": base_url.rstrip("/")})
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        try:
            result = await client.authenticate(
                bearer_token=bearer_token,
                device_code=device_code,
                org_id=org_id,
            )
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
