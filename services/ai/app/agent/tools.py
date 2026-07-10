"""Outils Workproba exposés à l'agent Pydantic AI.

Chaque outil est une fonction typée async enregistrée via `@agent.tool` ;
Pydantic AI déduit le schéma JSON depuis la signature + docstring. Les deps
(`ToolDeps`) portent le contexte de tour et les clients projet/sandbox.

Toute exception levée par un outil est convertie en `ModelRetry` : l'échec
remonte côté UI via un `ToolCallResultEvent(is_error=True)` (RetryPromptPart)
et le modèle est informé pour s'adapter, comme le faisait l'ancien
`ToolRegistry.dispatch` (qui enveloppait les erreurs dans un ToolResult is_error).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry

from app.agent.confirmation import ConfirmationGate
from app.agent.human import build_human_summary
from app.limits import DEFAULT_LIMITS, Limits
from app.project_client import ProjectClient
from app.sandbox.runner import SandboxRunner
from app.schemas import DocumentReference, UiMode

WORKPROBA_SYSTEM_PROMPT = (
    "Tu es Workproba, l'assistant IA local d'Improba. Tu aides l'utilisateur "
    "à analyser, comprendre et produire du contenu à partir des fichiers de "
    "son workspace local. Utilise les outils fournis (list_files, search_kb, "
    "read_document, run_code, generate_document) quand c'est pertinent. "
    "Réponds en français, de façon claire et concise. Cite les chemins de "
    "fichiers relatifs quand tu t'appuies sur leur contenu. Les outils "
    "appliquent des plafonds de taille : si read_document renvoie "
    "`truncated: true`, rappelle-le avec un `offset_lines` plus grand pour "
    "paginer. Pour décrire le contenu d'un dossier, commence par list_files."
)


@dataclass(frozen=True)
class ToolContext:
    tenant_id: str
    project_id: str
    session_id: str
    documents: list[DocumentReference]
    project_root: Path | None = None


@dataclass
class ToolDeps:
    context: ToolContext
    project_client: ProjectClient
    sandbox_runner: SandboxRunner
    limits: Limits = field(default_factory=lambda: DEFAULT_LIMITS)
    confirmation_gate: ConfirmationGate | None = None


def _retry(exc: Exception) -> ModelRetry:
    return ModelRetry(f"{type(exc).__name__}: {exc}")


def _normalize_relative_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _write_action(
    project_root: Path | None,
    name: str,
) -> tuple[str, Literal["create", "modify"]]:
    proposed_path = _normalize_relative_path(name)
    if project_root is None:
        return proposed_path, "create"
    target = (project_root / proposed_path).resolve()
    if target.is_file():
        return proposed_path, "modify"
    return proposed_path, "create"


def build_inventory_prompt(documents: list[DocumentReference], cap: int) -> str:
    """Construit le prompt système listant les fichiers projet transmis.

    Sans ça, l'agent ignore quels fichiers existent : search_kb est une
    recherche par contenu (pas un listing) et run_code tourne dans un sandbox
    isolé. L'inventaire est borné par `cap`.
    """
    if not documents:
        return (
            "Aucun fichier projet n'a été transmis dans le contexte. "
            "Utilise l'outil list_files pour explorer l'arborescence du "
            "dossier projet avant de conclure qu'il est vide."
        )
    lines: list[str] = []
    for doc in documents[:cap]:
        path = doc.metadata.get("relativePath") or doc.id
        kind = doc.metadata.get("kind") or "fichier"
        lines.append(f"- {path} ({kind})")
    text = (
        "Inventaire du projet (chemins relatifs, extrait de l'arborescence) :\n"
        + "\n".join(lines)
    )
    if len(documents) > cap:
        text += f"\n… et {len(documents) - cap} autres fichiers non listés ici."
    text += (
        "\nUtilise read_document pour lire un fichier (par chemin relatif), "
        "search_kb pour rechercher du contenu par mot-clé, list_files pour "
        "lister une sous-arborescence, run_code pour exécuter du code en "
        "précisant les project_files à exposer au sandbox."
    )
    return text


def build_agent(
    model: Any,
    *,
    ui_mode: UiMode = "guided",
    sandbox_available: bool = True,
) -> Agent[ToolDeps, str]:
    """Construit l'agent Pydantic AI avec ses outils métier."""
    agent: Agent[ToolDeps, str] = Agent(
        model=model,
        deps_type=ToolDeps,
        output_type=str,
        system_prompt=WORKPROBA_SYSTEM_PROMPT,
    )

    @agent.system_prompt
    def project_inventory_prompt(ctx: RunContext[ToolDeps]) -> str:
        """Injecte l'inventaire des fichiers projet reçus dans le payload."""
        return build_inventory_prompt(
            ctx.deps.context.documents, ctx.deps.limits.inventory_max_entries
        )

    @agent.tool
    async def list_files(
        ctx: RunContext[ToolDeps],
        subdir: str = "",
        max_entries: int = 200,
    ) -> dict[str, Any]:
        """List project files and folders under an optional subdirectory.

        Returns a bounded tree (respecting ignored dirs like `.git`,
        `node_modules`). Use this to answer "what's in the folder?" or to
        discover file names before reading them. `subdir` is a relative path
        within the project (defaults to the project root).

        Args:
            subdir: Optional relative subdirectory to list (defaults to root).
            max_entries: Max entries to return. Clamped server-side.
        """
        deps = ctx.deps
        try:
            response = await deps.project_client.list_files(
                subdir=subdir,
                max_entries=max_entries,
            )
            return response.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def search_kb(
        ctx: RunContext[ToolDeps],
        query: str,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search the current project knowledge base or local files.

        Args:
            query: The search query (natural language or keywords).
            limit: Maximum number of results to return. Clamped to 1..20 by the server.
            filters: Optional metadata filters.
        """
        deps = ctx.deps
        clamped = max(1, min(int(limit), deps.limits.search_max_limit))
        try:
            response = await deps.project_client.search_kb(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                query=query,
                limit=clamped,
                filters=filters,
            )
            return response.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    @agent.tool
    async def read_document(
        ctx: RunContext[ToolDeps],
        document_id: str,
        offset_lines: int = 0,
        max_lines: int = 0,
    ) -> dict[str, Any]:
        """Read a project document by id or relative local path.

        Reads a bounded window of the file (the server caps the number of lines
        and bytes returned). For text files, use `offset_lines` to paginate when
        the result is `truncated`. For binary documents (PDF, docx, xlsx, pptx),
        pagination params are ignored and extraction is capped server-side.

        Args:
            document_id: Relative path or id of the document within the project.
            offset_lines: Number of lines to skip from the top (text files only).
            max_lines: Max lines to return. 0 = server default (capped).
        """
        deps = ctx.deps
        try:
            document = await deps.project_client.read_document(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                document_id=document_id,
                offset_lines=offset_lines,
                max_lines=max_lines,
            )
            return document.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    if ui_mode == "advanced":

        @agent.tool
        async def run_code(
            ctx: RunContext[ToolDeps],
            code: str,
            project_files: list[str] | None = None,
        ) -> dict[str, Any]:
            """Run generated Python code in the isolated sandbox.

            The sandbox runs in a throwaway working directory with resource limits
            (CPU, memory, file size) and a minimal environment. Only the files listed
            in `project_files` (relative paths within the project) are copied in and
            made available to the code; writes stay inside the sandbox and are
            returned in `files`. Network access is blocked when possible.

            Args:
                code: Python source code to execute.
                project_files: Optional list of project file paths to make available.
            """
            deps = ctx.deps
            if not sandbox_available:
                raise ModelRetry(
                    "Sandbox indisponible : Docker n'est pas démarré. "
                    "Lancez Docker ou utilisez le mode guidé."
                )
            project_root = deps.context.project_root
            try:
                result = await deps.sandbox_runner.run(
                    code=code,
                    project_files=list(project_files or []),
                    project_root=project_root,
                )
                return result.model_dump(mode="json")
            except Exception as exc:  # noqa: BLE001 - surfaced to the model
                raise _retry(exc) from exc

    @agent.tool
    async def generate_document(
        ctx: RunContext[ToolDeps],
        name: str,
        mime_type: str,
        content_markdown: str,
    ) -> dict[str, Any]:
        """Save a generated document into the project.

        Args:
            name: Relative path/name of the document to create.
            mime_type: MIME type of the document (e.g. text/markdown).
            content_markdown: The markdown content to write.
        """
        deps = ctx.deps
        proposed_path, action = _write_action(deps.context.project_root, name)
        gate = deps.confirmation_gate

        # Future T-D3d: en mode advanced, permettre de désactiver la confirmation
        # via un toggle UI (branchement ici sur ui_mode + préférence utilisateur).
        if gate is not None:
            human_summary = build_human_summary("generate_document", {"name": name})
            approved = await gate.request_write(
                tool_call_id=ctx.tool_call_id or "",
                action=action,
                proposed_path=proposed_path,
                human_summary=human_summary,
            )
            if not approved:
                return {
                    "cancelled": True,
                    "message": "Action annulée par l'utilisateur",
                }

        content_base64 = base64.b64encode(content_markdown.encode("utf-8")).decode("ascii")
        try:
            document = await deps.project_client.save_generated_document(
                tenant_id=deps.context.tenant_id,
                project_id=deps.context.project_id,
                session_id=deps.context.session_id,
                name=name,
                mime_type=mime_type,
                content_base64=content_base64,
                metadata={"generated_by": "workproba-ai"},
            )
            return document.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            raise _retry(exc) from exc

    return agent


__all__ = [
    "ToolContext",
    "ToolDeps",
    "build_agent",
    "build_inventory_prompt",
    "WORKPROBA_SYSTEM_PROMPT",
]
