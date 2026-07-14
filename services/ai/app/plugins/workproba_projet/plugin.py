"""Outils agent du plugin projet (publish_artifact, list_projects, create_project)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.effects import classify_effect
from app.agent.human import build_human_summary
from app.agent.tools import ToolDeps
from app.i18n import t
from app.plugins.workproba_projet import storage


def _plugin_data_dir(ctx: RunContext[ToolDeps]) -> Path:
    data_dir = ctx.deps.context.plugin_data_dir
    if data_dir is None:
        raise ModelRetry("Plugin projet: plugin_data_dir manquant")
    return data_dir


def _workspace_root(ctx: RunContext[ToolDeps]) -> Path:
    root = ctx.deps.context.project_root
    if root is not None:
        return root.resolve()
    data_dir = ctx.deps.context.workspace_data_dir
    if data_dir is not None:
        return data_dir.resolve()
    raise ModelRetry("Plugin projet: espace de travail introuvable")


def _retry_from_value_error(exc: ValueError, locale: str) -> ModelRetry:
    code = str(exc)
    key = f"errors.{code}"
    message = t(locale, key)
    if message == key:
        message = str(exc)
    return ModelRetry(message)


def register_projet_tools(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def list_projects(ctx: RunContext[ToolDeps]) -> dict[str, Any]:
        """List collaborative projects managed by the project plugin.

        Returns all projects with id, name, and created_at.
        """
        locale = ctx.deps.context.locale
        try:
            projects = storage.load_projects(_plugin_data_dir(ctx))
            return {"projects": projects, "count": len(projects)}
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

    @agent.tool
    async def create_project(ctx: RunContext[ToolDeps], name: str) -> dict[str, Any]:
        """Create a new collaborative project.

        Args:
            name: Display name for the project.
        """
        locale = ctx.deps.context.locale
        try:
            project = storage.create_project(_plugin_data_dir(ctx), name)
            return {"project": project}
        except ValueError as exc:
            raise _retry_from_value_error(exc, locale) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc

    @agent.tool
    async def publish_artifact(
        ctx: RunContext[ToolDeps],
        source_path: str,
        project_id: str,
        name: str,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Publish a workspace file or markdown content into a project artefact.

        Copies the source document from the space into the project's artefact
        store, or writes markdown content directly. Requires user confirmation
        before writing.

        Args:
            source_path: Relative path of the file within the workspace (use "" for content-only).
            project_id: Target project id.
            name: Artefact filename in the project.
            content: Markdown content to publish instead of copying a file.
        """
        deps = ctx.deps
        locale = deps.context.locale
        plugin_data_dir = _plugin_data_dir(ctx)

        project = storage.find_project(plugin_data_dir, project_id)
        if project is None:
            raise ModelRetry(t(locale, "errors.project_not_found", project_id=project_id))

        has_source = bool(source_path and source_path.strip())
        has_content = content is not None
        if has_source and has_content:
            raise ModelRetry(t(locale, "errors.ambiguous_publish_source"))
        if not has_source and not has_content:
            raise ModelRetry(t(locale, "errors.missing_publish_source"))

        artefact_name = name
        project_name = str(project.get("name") or project_id)
        gate = deps.confirmation_gate

        if gate is not None:
            human_summary = build_human_summary(
                "publish_artifact",
                {"name": artefact_name, "project": project_name, "project_id": project_id},
                locale=locale,
            )
            proposal = classify_effect(
                "publish_artifact",
                {
                    "name": artefact_name,
                    "project": project_name,
                    "project_id": project_id,
                },
                permissions_network=deps.context.permissions_network,
            )
            if proposal is None:
                raise ModelRetry("Effet non classifiable pour publish_artifact")
            proposal = proposal.model_copy(update={"human_summary": human_summary})
            approved = await gate.request_effect(
                tool_call_id=ctx.tool_call_id or "",
                proposal=proposal,
                audit_app_data_dir=deps.context.workspace_data_dir,
            )
            if not approved:
                return {
                    "cancelled": True,
                    "message": t(locale, "tools.action_cancelled_by_user"),
                }

        workspace_root = _workspace_root(ctx) if has_source else None
        try:
            artefact = storage.publish_artifact(
                plugin_data_dir=plugin_data_dir,
                workspace_root=workspace_root,
                source_path=source_path,
                content=content,
                project_id=project_id,
                name=name,
                work_id=deps.context.work_id,
            )
            return artefact
        except FileNotFoundError as exc:
            raise ModelRetry(
                t(locale, "errors.source_not_found", path=source_path or "")
            ) from exc
        except ValueError as exc:
            raise _retry_from_value_error(exc, locale) from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelRetry(f"{type(exc).__name__}: {exc}") from exc
