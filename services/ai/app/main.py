import asyncio
import base64
import binascii
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse, Response

from app.agent.compaction import compact_history_if_needed
from app.agent.confirmation import confirmation_registry
from app.agent.loop import AgentLoop
from app.agent.plan import plan_registry
from app.agent.tools import build_agent
from app.auth import INTERNAL_SECRET_HEADER, internal_secret_middleware
from app.capabilities import Capabilities, detect_capabilities
from app.config import Settings, get_settings
from app.local_client import LocalProjectClient
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.llm.provider import resolve_litellm_model
from app.llm.provider_sets import (
    ocr_is_supported,
    resolve_chat_from_set,
    resolve_embeddings_from_set,
    vision_is_supported,
)
from app.llm.utility import generate_title, summarize_conversation
from app.rag.store import RagStore
from app.sandbox.runner import SandboxRunner
from app.documents.preview import render_preview
from app.documents.preview_change import preview_change
from app.schemas import (
    AgentConfirmRequest,
    AgentPlanApproveRequest,
    AgentTurnRequest,
    CapabilitiesResponse,
    CompactionEvent,
    DocumentPreviewResponse,
    ErrorEvent,
    LLMProviderConfig,
    PreviewChangeRequest,
    PreviewChangeResponse,
    ProviderSet,
    ProviderSetTestResponse,
    TurnStartEvent,
    UtilitySummarizeRequest,
    UtilitySummarizeResponse,
    UtilityTitleRequest,
    UtilityTitleResponse,
    VersionInfo,
    VersionListResponse,
    VersionRestoreRequest,
    VersionRestoreResponse,
    WorkspaceIndexReport,
    WorkspaceIndexRequest,
)
from app.i18n import normalize_locale, t
from app.turn_manager import turn_manager
from app.versions import list_versions, restore_version
from app.audit import (
    export_audit_csv,
    get_audit_config,
    log_event,
    read_audit,
    resolve_app_data_dir,
    save_audit_config,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = get_settings()
    app.state.capabilities = detect_capabilities()
    yield


app = FastAPI(
    title="Workproba AI Core",
    version="0.1.0",
    lifespan=lifespan,
)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_origin_regex=_settings.compiled_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)
app.middleware("http")(internal_secret_middleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    for error in exc.errors():
        message = str(error.get("msg", ""))
        if "history exceeds" in message or "message exceeds" in message:
            return JSONResponse(
                status_code=422,
                content={"detail": message, "code": "input_too_large"},
            )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "workproba-ai"}


class LlmTestResult(BaseModel):
    ok: bool
    detail: str = ""
    model_count: int | None = None


@app.post("/llm/test", response_model=LlmTestResult)
async def llm_test(payload: LLMProviderConfig) -> LlmTestResult:
    """Valide une config LLM (clé + endpoint) en listant les modèles disponibles.

    Coût nul (GET /models). Utilisé par l'écran de settings de l'app.
    """
    import httpx

    from app.llm.config import _DEFAULT_BASE_URL, _OPENAI_COMPAT_PROVIDERS

    provider = payload.provider
    api_key = payload.api_key.get_secret_value() if payload.api_key else None

    if provider == "ollama":
        base_url = payload.base_url or _DEFAULT_BASE_URL.get("ollama", "http://127.0.0.1:11434/v1")
        headers: dict[str, str] = {}
    elif provider in _OPENAI_COMPAT_PROVIDERS:
        base_url = payload.base_url or _DEFAULT_BASE_URL.get(provider)
        if not base_url:
            return LlmTestResult(ok=False, detail="URL de base manquante pour ce provider")
        if not api_key:
            return LlmTestResult(ok=False, detail="Clé API manquante")
        headers = {"Authorization": f"Bearer {api_key}"}
    elif provider == "anthropic":
        base_url = payload.base_url or "https://api.anthropic.com/v1"
        if not api_key:
            return LlmTestResult(ok=False, detail="Clé API manquante")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        return LlmTestResult(ok=False, detail=f"Provider non testable : {provider}")

    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return LlmTestResult(ok=False, detail=f"Connexion impossible : {exc}")

    if response.status_code == 401:
        return LlmTestResult(ok=False, detail="Clé API invalide (401)")
    if response.status_code == 404:
        return LlmTestResult(
            ok=False, detail=f"Endpoint /models introuvable (404) sur {base_url}"
        )
    if not response.is_success:
        return LlmTestResult(
            ok=False,
            detail=f"Réponse HTTP {response.status_code} : {response.text[:200]}",
        )

    try:
        data = response.json()
        models = data.get("data") if isinstance(data, dict) else None
        count = len(models) if isinstance(models, list) else None
    except ValueError:
        count = None

    return LlmTestResult(ok=True, detail="Connexion OK", model_count=count)


@app.post("/llm/sets/test", response_model=ProviderSetTestResponse)
async def llm_sets_test(payload: ProviderSet) -> ProviderSetTestResponse:
    """Teste chaque sous-composant d'un provider set (chat, embeddings, OCR, vision).

  La persistance des sets est côté Rust (AppSettings.sets). Le sidecar ne
  stocke pas les sets : il valide et teste uniquement la connectivité.
    """
    from app.schemas import (
        ProviderSetTestChatResult,
        ProviderSetTestEmbeddingsResult,
        ProviderSetTestOcrResult,
        ProviderSetTestVisionResult,
    )

    chat_cfg = resolve_chat_from_set(payload)
    chat_result_raw = await llm_test(chat_cfg)
    model_ids: list[str] | None = None
    if chat_result_raw.ok and chat_result_raw.model_count is not None:
        model_ids = []

    chat_result = ProviderSetTestChatResult(
        ok=chat_result_raw.ok,
        detail=chat_result_raw.detail,
        models=model_ids,
    )

    embed_cfg = resolve_embeddings_from_set(payload)
    if embed_cfg is None:
        embed_result = ProviderSetTestEmbeddingsResult(
            ok=True,
            detail="Embeddings non configurés dans ce set",
        )
    else:
        embed_chat_result = await llm_test(embed_cfg)
        embed_result = ProviderSetTestEmbeddingsResult(
            ok=embed_chat_result.ok,
            detail=embed_chat_result.detail,
        )

    ocr_supported = ocr_is_supported(payload)
    ocr_ok = False
    ocr_detail = "OCR absent ou désactivé"
    if ocr_supported:
        from app.ocr.mistral import MistralOcrClient, resolve_ocr_api_key

        try:
            MistralOcrClient(provider_set=payload)
            if resolve_ocr_api_key(payload):
                ocr_ok = True
                ocr_detail = "OCR configuré"
            else:
                ocr_detail = "Clé API OCR manquante"
        except ValueError as exc:
            ocr_detail = str(exc)
    ocr_result = ProviderSetTestOcrResult(
        ok=ocr_ok,
        supported=ocr_supported,
        detail=ocr_detail,
    )

    vision_supported = vision_is_supported(payload)
    vision_result = ProviderSetTestVisionResult(
        ok=vision_supported,
        supported=vision_supported,
        detail="Vision via chat" if vision_supported else "Vision non disponible",
    )

    return ProviderSetTestResponse(
        chat=chat_result,
        embeddings=embed_result,
        ocr=ocr_result,
        vision=vision_result,
    )


@app.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(request: Request) -> CapabilitiesResponse:
    caps: Capabilities = request.app.state.capabilities
    return CapabilitiesResponse(
        docker=caps.docker,
        sandbox_available=caps.sandbox_available,
    )


@app.post("/util/title", response_model=UtilityTitleResponse)
async def util_title(request: Request, payload: UtilityTitleRequest) -> UtilityTitleResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    try:
        return await generate_title(payload, settings)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/util/summarize", response_model=UtilitySummarizeResponse)
async def util_summarize(
    request: Request,
    payload: UtilitySummarizeRequest,
) -> UtilitySummarizeResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    try:
        return await summarize_conversation(payload, settings)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/agent/confirm")
async def agent_confirm(payload: AgentConfirmRequest) -> dict[str, bool]:
    resolved = confirmation_registry.resolve(
        payload.session_id,
        payload.turn_id,
        payload.confirmation_id,
        payload.decision,
    )
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=t(normalize_locale(payload.locale), "main.confirmation_not_found"),
        )
    return {"ok": True}


@app.post("/agent/plan/approve")
async def agent_plan_approve(payload: AgentPlanApproveRequest) -> dict[str, bool]:
    resolved = plan_registry.resolve(
        payload.session_id,
        payload.turn_id,
        payload.plan_id,
        approved=payload.approved,
        modifications=payload.modifications,
    )
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=t(normalize_locale(payload.locale), "main.plan_not_found"),
        )
    return {"ok": True}


@app.post("/agent/turn")
async def agent_turn(request: Request, payload: AgentTurnRequest) -> EventSourceResponse:
    settings: Settings = request.app.state.settings
    turn_id = payload.turn_id or f"turn_{uuid.uuid4().hex[:16]}"

    if not await turn_manager.try_acquire(payload.session_id, turn_id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "turn_in_progress",
                "message": t(payload.locale, "main.turn_in_progress"),
            },
        )

    project_root = resolve_project_root(settings, payload)
    workspace_data_dir = resolve_workspace_data_dir(payload)
    limits = settings.limits
    project_client = LocalProjectClient(
        project_root=project_root,
        workspace_data_dir=workspace_data_dir,
        limits=limits,
        rag_store=build_rag_store(
            settings,
            workspace_data_dir,
            project_root,
            payload.embedding_config,
            provider_set=payload.provider_set,
        ),
    )
    sandbox_runner = SandboxRunner(timeout_seconds=settings.sandbox_timeout_seconds, limits=limits)

    caps: Capabilities = request.app.state.capabilities
    cancel_event = asyncio.Event()

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        try:
            yield to_sse_event(TurnStartEvent(turn_id=turn_id))

            llm_config = resolve_llm_config(
                payload.llm_provider_config,
                settings,
                provider_set=payload.provider_set,
            )
            compaction_event: CompactionEvent | None = None
            if payload.context_window and payload.auto_compact:
                payload.history, compaction_event = await compact_history_if_needed(
                    payload.history,
                    payload.context_window,
                    payload.auto_compact,
                    llm_config,
                    settings,
                    locale=payload.locale,
                )
            model = build_model(llm_config)
            agent = build_agent(
                model,
                ui_mode=payload.ui_mode,
                sandbox_available=caps.sandbox_available,
                locale=payload.locale,
                active_plugins=payload.active_plugins,
            )
            agent_loop = AgentLoop(
                agent=agent,
                project_client=project_client,
                sandbox_runner=sandbox_runner,
                max_iterations=settings.max_agent_iterations,
                model_settings=build_model_settings(llm_config),
                project_root=project_root,
                limits=limits,
            )
            if compaction_event is not None:
                yield to_sse_event(compaction_event)

            try:
                async with asyncio.timeout(settings.turn_timeout_seconds):
                    async for event in agent_loop.run_turn(
                        payload,
                        turn_id=turn_id,
                        cancel_event=cancel_event,
                    ):
                        if await _client_disconnected(request):
                            cancel_event.set()
                            break
                        if cancel_event.is_set():
                            break
                        yield to_sse_event(event)
            except TimeoutError:
                cancel_event.set()
                yield to_sse_event(
                    ErrorEvent(
                        code="turn_timeout",
                        message=t(
                            payload.locale,
                            "main.turn_timeout",
                            seconds=settings.turn_timeout_seconds,
                        ),
                    )
                )
        except Exception:
            yield to_sse_event(
                ErrorEvent(
                    code="internal_error",
                    message=t(payload.locale, "main.internal_error"),
                )
            )
        finally:
            cancel_event.set()
            await project_client.close()
            await turn_manager.release(payload.session_id, turn_id)

    return EventSourceResponse(event_stream(), media_type="text/event-stream")


async def _client_disconnected(request: Request) -> bool:
    """Détection non bloquante de déconnexion client (compatible TestClient)."""
    try:
        return await asyncio.wait_for(request.is_disconnected(), timeout=0)
    except TimeoutError:
        return False


@app.post("/agent/index-workspace", response_model=WorkspaceIndexReport)
async def agent_index_workspace(request: Request, payload: WorkspaceIndexRequest) -> WorkspaceIndexReport:
    """Indexation RAG bulk du dossier de travail.

    Construit le `RagStore` du workspace (config d'embedding par tour ou env),
    parcourt le dossier, extrait le texte des fichiers éligibles et les indexe.
    Si le RAG est désactivé (pas de modèle d'embedding), renvoie un rapport
    `enabled=False` au lieu d'une erreur.
    """
    settings: Settings = request.app.state.settings
    project_root = _resolve_root(settings, payload.project_path, payload.project_id)
    workspace_data_dir = resolve_workspace_data_dir(payload)
    rag_store = build_rag_store(
        settings,
        workspace_data_dir,
        project_root,
        payload.embedding_config,
        provider_set=getattr(payload, "provider_set", None),
    )

    if rag_store is None:
        return WorkspaceIndexReport(
            project_root=project_root.as_posix(),
            enabled=False,
            metadata={"reason": "rag_disabled"},
        )

    project_client = LocalProjectClient(
        project_root=project_root,
        workspace_data_dir=workspace_data_dir,
        limits=settings.limits,
        rag_store=rag_store,
    )
    try:
        return await project_client.index_workspace(
            max_files=payload.max_files,
            paths=payload.paths,
        )
    finally:
        await project_client.close()


def resolve_workspace_data_dir(
    payload: AgentTurnRequest | WorkspaceIndexRequest,
) -> Path | None:
    if payload.workspace_data_dir:
        return Path(payload.workspace_data_dir).expanduser().resolve()
    return None


def build_rag_store(
    settings: Settings,
    workspace_data_dir: Path | None,
    project_root: Path,
    embedding_config: LLMProviderConfig | None = None,
    *,
    provider_set: ProviderSet | None = None,
) -> RagStore | None:
    embedding_model, embedding_base_url, embedding_api_key = resolve_embedding_config(
        settings, embedding_config, provider_set=provider_set
    )
    if not embedding_model:
        return None

    if workspace_data_dir is not None:
        db_path = workspace_data_dir / "memory.db"
    else:
        db_path = project_root / ".workproba" / "memory.db"

    return RagStore(
        db_path=db_path,
        embedding_model=embedding_model,
        embedding_base_url=embedding_base_url,
        embedding_api_key=embedding_api_key,
    )


def resolve_embedding_config(
    settings: Settings,
    embedding_config: LLMProviderConfig | None,
    *,
    provider_set: ProviderSet | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Priorise le set actif, puis la config par tour, puis les env du sidecar."""
    if provider_set is not None:
        set_embed = resolve_embeddings_from_set(provider_set)
        if set_embed is not None and set_embed.model:
            model = set_embed.model
            if "/" not in model and set_embed.provider:
                model = resolve_litellm_model(set_embed.provider, model)
            api_key = (
                set_embed.api_key.get_secret_value()
                if set_embed.api_key
                else None
            )
            return model, set_embed.base_url, api_key

    if embedding_config is not None and embedding_config.model:
        model = embedding_config.model
        if "/" not in model and embedding_config.provider:
            model = resolve_litellm_model(embedding_config.provider, model)
        api_key = (
            embedding_config.api_key.get_secret_value()
            if embedding_config.api_key
            else None
        )
        return model, embedding_config.base_url, api_key

    if not settings.llm_embedding_model:
        return None, None, None

    model = settings.llm_embedding_model
    if "/" not in model and settings.llm_embedding_provider:
        model = resolve_litellm_model(settings.llm_embedding_provider, model)
    return model, settings.llm_embedding_base_url, settings.llm_embedding_api_key


def resolve_project_root(settings: Settings, payload: AgentTurnRequest) -> Path:
    return _resolve_root(settings, payload.project_path, payload.project_id)


def _resolve_root(settings: Settings, project_path: str | None, project_id: str) -> Path:
    if project_path:
        return Path(project_path).expanduser().resolve()

    project_id_path = Path(project_id).expanduser()
    if project_id_path.is_absolute():
        return project_id_path.resolve()

    if settings.project_root is not None:
        return settings.project_root

    return Path.cwd()


@app.get("/documents/preview", response_model=DocumentPreviewResponse)
async def documents_preview(
    request: Request,
    path: str,
    workspace_data_dir: str,
    project_path: str | None = None,
) -> DocumentPreviewResponse:
    """Aperçu HTML léger d'un document de l'espace (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)

    workspace_root = Path(workspace_data_dir).expanduser().resolve()
    if project_path:
        base = Path(project_path).expanduser().resolve()
        if not base.is_relative_to(workspace_root):
            raise HTTPException(status_code=403, detail="Project path outside workspace")
    else:
        base = workspace_root

    normalized = path.replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]

    base_resolved = base.resolve()
    target = (base / normalized).resolve()
    if not target.is_relative_to(base_resolved):
        raise HTTPException(status_code=403, detail="Path outside workspace")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    preview = await render_preview(target, limits=settings.limits)
    return DocumentPreviewResponse.model_validate(preview)


@app.post("/documents/preview-change", response_model=PreviewChangeResponse)
async def documents_preview_change(
    request: Request,
    payload: PreviewChangeRequest,
) -> PreviewChangeResponse:
    """Diff technique avant écriture (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)

    workspace_root = Path(payload.workspace_data_dir).expanduser().resolve()
    project_root = Path(payload.project_path).expanduser().resolve()

    normalized = payload.file_path.replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    target = (project_root / normalized).resolve()
    if not target.is_relative_to(project_root.resolve()):
        raise HTTPException(status_code=403, detail="Path outside workspace")

    try:
        result = preview_change(
            workspace_data_dir=workspace_root,
            project_root=project_root,
            file_path=payload.file_path,
            proposed_content=payload.proposed_content,
            locale=payload.locale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return PreviewChangeResponse.model_validate(result)


@app.get("/versions", response_model=VersionListResponse)
async def list_file_versions(
    request: Request,
    workspace_data_dir: str,
    file_path: str,
    locale: str = "fr",
) -> VersionListResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    ws_dir = Path(workspace_data_dir).expanduser().resolve()
    entries = list_versions(workspace_data_dir=ws_dir, file_path=file_path)
    versions = [
        VersionInfo(
            version_id=str(item["version_id"]),
            created_at=str(item["created_at"]),
            size=int(item.get("size", 0)),
            file_path=str(item.get("file_path", file_path)),
            label=t(
                locale,
                "versions.snapshot_label",
                file=item.get("file_path", file_path),
            ),
        )
        for item in entries
    ]
    return VersionListResponse(versions=versions)


@app.post("/versions/restore", response_model=VersionRestoreResponse)
async def restore_file_version(
    request: Request,
    payload: VersionRestoreRequest,
) -> VersionRestoreResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    ws_dir = Path(payload.workspace_data_dir).expanduser().resolve()
    project_root = Path(payload.project_path).expanduser().resolve()
    result = restore_version(
        workspace_data_dir=ws_dir,
        project_root=project_root,
        file_path=payload.file_path,
        version_id=payload.version_id,
        label=t(payload.locale, "versions.restore_label", file=payload.file_path),
    )
    return VersionRestoreResponse.model_validate(result)


def to_sse_event(event: BaseModel) -> dict[str, str]:
    return {
        "event": str(getattr(event, "type", "message")),
        "data": event.model_dump_json(),
    }


def require_internal_secret(request: Request, settings: Settings) -> None:
    expected_secret = settings.internal_secret
    if not expected_secret:
        raise HTTPException(
            status_code=503,
            detail="Internal service secret is not configured.",
        )
    provided_secret = request.headers.get(INTERNAL_SECRET_HEADER)
    if not provided_secret or not compare_digest(provided_secret, expected_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid internal service secret.",
        )


class ReprocessAttachmentRequest(BaseModel):
    workspace_data_dir: str
    project_path: str
    attachment_id: str
    file_path: str
    mime_type: str
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    content_base64: str | None = None
    persist_only: bool = False


class ReprocessAttachmentResponse(BaseModel):
    status_key: str
    label_locale: str
    extracted_text: str | None = None


@app.post("/agent/reprocess-attachment", response_model=ReprocessAttachmentResponse)
async def agent_reprocess_attachment(
    request: Request,
    payload: ReprocessAttachmentRequest,
) -> ReprocessAttachmentResponse:
    """Re-traite une pièce jointe stockée avec le set actif (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)

    workspace_root = Path(payload.workspace_data_dir).expanduser().resolve()

    from app.agent.attachments import (
        persist_attachment_file,
        reprocess_attachment,
    )
    from app.provider_set import resolve_provider_set

    provider_set = resolve_provider_set(payload.provider_set)
    ui_mode = "locked" if provider_set and provider_set.ui_mode_locked else "guided"

    if payload.content_base64:
        try:
            raw = base64.b64decode(payload.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 content") from exc
        path_parts = payload.file_path.replace("\\", "/").split("/")
        session_id = (
            path_parts[1]
            if len(path_parts) >= 2 and path_parts[0] == "attachments"
            else payload.attachment_id
        )
        file_name = Path(payload.file_path).name
        try:
            persist_attachment_file(
                workspace_root,
                session_id=session_id,
                attachment_id=payload.attachment_id,
                file_name=file_name,
                content=raw,
                file_path=payload.file_path,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if payload.persist_only:
            return ReprocessAttachmentResponse(
                status_key="stored",
                label_locale="",
            )

    file_name = Path(payload.file_path).name
    try:
        result = await reprocess_attachment(
            workspace_data_dir=workspace_root,
            attachment_id=payload.attachment_id,
            file_path=payload.file_path,
            file_name=file_name,
            mime_type=payload.mime_type or None,
            limits=settings.limits,
            locale=normalize_locale(payload.locale),
            provider_set=provider_set,
            ui_mode=ui_mode,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return ReprocessAttachmentResponse(
        status_key=result.status_key,
        label_locale=result.label_locale,
        extracted_text=result.extracted_text,
    )


class ProjetProjectsResponse(BaseModel):
    projects: list[dict[str, Any]]


class ProjetCreateProjectRequest(BaseModel):
    plugin_data_dir: str
    name: str
    locale: str = "fr"


class ProjetCreateProjectResponse(BaseModel):
    project: dict[str, Any]


class ProjetPublishRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    name: str
    source_path: str | None = None
    content: str | None = None
    workspace_data_dir: str | None = None
    project_path: str | None = None
    locale: str = "fr"


class ProjetPublishResponse(BaseModel):
    artefact: dict[str, Any]


class ProjetArtefactsResponse(BaseModel):
    artefacts: list[dict[str, Any]]


def _resolve_plugin_data_dir(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _resolve_workspace_root(payload: ProjetPublishRequest) -> Path:
    if payload.workspace_data_dir is None:
        raise HTTPException(status_code=400, detail="workspace_data_dir required")
    if payload.project_path:
        root = Path(payload.project_path).expanduser().resolve()
        workspace_root = Path(payload.workspace_data_dir).expanduser().resolve()
        if not root.is_relative_to(workspace_root):
            raise HTTPException(status_code=403, detail="Project path outside workspace")
        return root
    return Path(payload.workspace_data_dir).expanduser().resolve()


@app.get("/plugins/projet/projects", response_model=ProjetProjectsResponse)
async def projet_list_projects(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> ProjetProjectsResponse:
    """Liste les projets du plugin projet (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_projet import storage as projet_storage

    projects = projet_storage.load_projects(_resolve_plugin_data_dir(plugin_data_dir))
    return ProjetProjectsResponse(projects=projects)


@app.post("/plugins/projet/projects", response_model=ProjetCreateProjectResponse)
async def projet_create_project(
    request: Request,
    payload: ProjetCreateProjectRequest,
) -> ProjetCreateProjectResponse:
    """Crée un projet collaboratif (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_projet import storage as projet_storage

    try:
        project = projet_storage.create_project(
            _resolve_plugin_data_dir(payload.plugin_data_dir),
            payload.name,
        )
    except ValueError as exc:
        if str(exc) == "invalid_project_name":
            raise HTTPException(
                status_code=400,
                detail=t(locale, "errors.invalid_project_name"),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjetCreateProjectResponse(project=project)


@app.post("/plugins/projet/publish", response_model=ProjetPublishResponse)
async def projet_publish_artifact(
    request: Request,
    payload: ProjetPublishRequest,
) -> ProjetPublishResponse:
    """Publie un document de l'espace vers un projet (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_projet import storage as projet_storage

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    has_source = bool(payload.source_path and payload.source_path.strip())
    has_content = payload.content is not None
    if has_source and has_content:
        raise HTTPException(
            status_code=400,
            detail=t(locale, "errors.ambiguous_publish_source"),
        )
    if not has_source and not has_content:
        raise HTTPException(
            status_code=400,
            detail=t(locale, "errors.missing_publish_source"),
        )
    workspace_root = _resolve_workspace_root(payload) if has_source else None
    try:
        artefact = projet_storage.publish_artifact(
            plugin_data_dir=plugin_dir,
            workspace_root=workspace_root,
            source_path=payload.source_path,
            content=payload.content,
            project_id=payload.project_id,
            name=payload.name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=t(locale, "errors.source_not_found", path=payload.source_path or ""),
        ) from exc
    except ValueError as exc:
        code = str(exc)
        detail = t(locale, f"errors.{code}")
        if detail == f"errors.{code}":
            detail = code
        if code == "project_not_found":
            status = 404
        elif code == "content_too_large":
            status = 413
        else:
            status = 403
        raise HTTPException(status_code=status, detail=detail) from exc
    return ProjetPublishResponse(artefact=artefact)


@app.get("/plugins/projet/artefacts", response_model=ProjetArtefactsResponse)
async def projet_list_artefacts(
    request: Request,
    plugin_data_dir: str,
    project_id: str,
    locale: str = "fr",
) -> ProjetArtefactsResponse:
    """Liste les documents publiés d'un projet (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_projet import storage as projet_storage

    try:
        artefacts = projet_storage.list_artefacts(
            _resolve_plugin_data_dir(plugin_data_dir),
            project_id,
        )
    except ValueError as exc:
        if str(exc) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail=t(locale, "errors.project_not_found", project_id=project_id),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjetArtefactsResponse(artefacts=artefacts)


class PersonasSetsResponse(BaseModel):
    sets: list[dict[str, Any]]


class PersonasSetPayload(BaseModel):
    id: str | None = None
    name: str
    personas: list[dict[str, Any]]


class PersonasSetResponse(BaseModel):
    set: dict[str, Any]


class PersonasAskRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    question: str
    context: str = ""
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    workspace_data_dir: str | None = None
    include_memory: bool = False


class PersonasMeetingRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    topic: str
    rounds: int = 3
    context: str = ""
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    workspace_data_dir: str | None = None
    include_memory: bool = False
    meeting_id: str | None = None


class PersonasDiscussRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    discussion_id: str | None = None
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    workspace_data_dir: str | None = None
    include_memory: bool = False


class PersonasMeetingsListResponse(BaseModel):
    meetings: list[dict[str, Any]]


class PersonasMeetingDetailResponse(BaseModel):
    meeting: dict[str, Any]


class PersonasDiscussionsListResponse(BaseModel):
    discussions: list[dict[str, Any]]


class PersonasDiscussionDetailResponse(BaseModel):
    discussion: dict[str, Any]


class MemoryItemsResponse(BaseModel):
    memories: list[dict[str, Any]]
    memory_scope: Literal["user", "project"] = "project"


class MemoryAddRequest(BaseModel):
    workspace_data_dir: str
    memory_scope: Literal["user", "project"] = "project"
    content: str
    tags: list[str] = Field(default_factory=list)
    locale: str = "fr"


class MemoryAddResponse(BaseModel):
    memory: dict[str, Any]


class MemoryForgetRequest(BaseModel):
    workspace_data_dir: str
    memory_id: str
    memory_scope: Literal["user", "project"] = "project"
    locale: str = "fr"


class MemoryClearRequest(BaseModel):
    workspace_data_dir: str
    scope: Literal["all", "memories", "conversations"] = "all"
    memory_scope: Literal["user", "project"] = "project"
    confirmed: bool = False
    locale: str = "fr"


class MemorySearchResponse(BaseModel):
    results: list[dict[str, Any]]
    memory_scope: Literal["user", "project", "all"] = "project"


class OkResponse(BaseModel):
    ok: bool = True
    detail: str = ""


def _resolve_workspace_data_dir_path(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace data directory not found")
    return path


def _memory_store_for_workspace(
    settings: Settings,
    workspace_data_dir: Path,
    provider_set: ProviderSet | None = None,
) -> RagStore:
    from app.rag.store import open_memory_store

    rag = build_rag_store(
        settings,
        workspace_data_dir,
        workspace_data_dir,
        provider_set=provider_set,
    )
    if rag is not None:
        return rag
    return open_memory_store(workspace_data_dir / "memory.db")


def _memory_store_for_scope(
    settings: Settings,
    workspace_data_dir: Path,
    memory_scope: str,
    provider_set: ProviderSet | None = None,
) -> RagStore:
    """Ouvre le store de mémoire adapté au scope (user global ou project)."""
    from app.memory_stores import VALID_SCOPES, open_memory_store_for_scope

    if memory_scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid memory scope")
    if memory_scope == "user":
        return open_memory_store_for_scope("user", workspace_data_dir)
    return _memory_store_for_workspace(settings, workspace_data_dir, provider_set)


@app.get("/plugins/personas/sets", response_model=PersonasSetsResponse)
async def personas_list_sets(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasSetsResponse:
    """Liste les sets de personas (builtin + custom)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    sets = personas_storage.list_sets(_resolve_plugin_data_dir(plugin_data_dir))
    return PersonasSetsResponse(sets=sets)


@app.post("/plugins/personas/sets", response_model=PersonasSetResponse)
async def personas_save_set(
    request: Request,
    payload: PersonasSetPayload,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasSetResponse:
    """Crée ou met à jour un set personas custom (persisté dans sets.json)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    plugin_dir = _resolve_plugin_data_dir(plugin_data_dir)
    try:
        saved = personas_storage.upsert_custom_set(
            plugin_dir,
            {
                "id": payload.id,
                "name": payload.name,
                "personas": payload.personas,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PersonasSetResponse(set=saved)


@app.delete("/plugins/personas/sets/{set_id}", response_model=OkResponse)
async def personas_delete_set(
    request: Request,
    set_id: str,
    plugin_data_dir: str,
    locale: str = "fr",
) -> OkResponse:
    """Supprime un set personas custom (le set builtin est protégé)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    plugin_dir = _resolve_plugin_data_dir(plugin_data_dir)
    if not personas_storage.delete_custom_set(plugin_dir, set_id):
        raise HTTPException(status_code=404, detail="Set not found")
    return OkResponse(ok=True)


def _personas_sse_stream(
    generator: Any,
) -> Any:
    async def event_stream() -> AsyncIterator[dict[str, str]]:
        async for event in generator:
            yield {
                "event": str(event.get("type", "message")),
                "data": json.dumps(event, ensure_ascii=False),
            }

    return event_stream


@app.post("/plugins/personas/ask")
async def personas_ask(request: Request, payload: PersonasAskRequest) -> EventSourceResponse:
    """Demander l'avis de personas (SSE, un bloc par persona)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_personas import orchestrator as personas_orchestrator

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(settings, ws_dir, payload.provider_set)

    stream = personas_orchestrator.stream_ask(
        plugin_data_dir=plugin_dir,
        persona_ids=payload.persona_ids,
        question=payload.question,
        context=payload.context,
        settings=settings,
        provider_set=payload.provider_set,
        locale=locale,
        rag_store=rag_store,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream)(),
        media_type="text/event-stream",
    )


@app.post("/plugins/personas/meeting")
async def personas_meeting(
    request: Request,
    payload: PersonasMeetingRequest,
) -> EventSourceResponse:
    """Simuler une réunion entre personas (SSE)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_personas import orchestrator as personas_orchestrator

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(settings, ws_dir, payload.provider_set)

    stream = personas_orchestrator.stream_meeting(
        plugin_data_dir=plugin_dir,
        persona_ids=payload.persona_ids,
        topic=payload.topic,
        rounds=payload.rounds,
        context=payload.context,
        settings=settings,
        provider_set=payload.provider_set,
        locale=locale,
        rag_store=rag_store,
        meeting_id=payload.meeting_id,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream)(),
        media_type="text/event-stream",
    )


@app.post("/plugins/personas/discuss")
async def personas_discuss(
    request: Request,
    payload: PersonasDiscussRequest,
) -> EventSourceResponse:
    """Discuter avec un ou plusieurs personas (SSE)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_personas import orchestrator as personas_orchestrator

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(settings, ws_dir, payload.provider_set)

    stream = personas_orchestrator.stream_discuss(
        plugin_data_dir=plugin_dir,
        persona_ids=payload.persona_ids,
        message=payload.message,
        history=payload.history,
        discussion_id=payload.discussion_id,
        settings=settings,
        provider_set=payload.provider_set,
        locale=locale,
        rag_store=rag_store,
        include_memory=payload.include_memory,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream)(),
        media_type="text/event-stream",
    )


@app.get("/plugins/personas/meetings", response_model=PersonasMeetingsListResponse)
async def personas_list_meetings(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasMeetingsListResponse:
    """Liste les réunions personas persistées (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    meetings = personas_storage.list_meetings(_resolve_plugin_data_dir(plugin_data_dir))
    return PersonasMeetingsListResponse(meetings=meetings)


@app.get("/plugins/personas/meetings/{meeting_id}", response_model=PersonasMeetingDetailResponse)
async def personas_get_meeting(
    request: Request,
    meeting_id: str,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasMeetingDetailResponse:
    """Détail d'une réunion personas avec transcript (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    meeting = personas_storage.get_meeting(_resolve_plugin_data_dir(plugin_data_dir), meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return PersonasMeetingDetailResponse(meeting=meeting)


@app.get("/plugins/personas/discussions", response_model=PersonasDiscussionsListResponse)
async def personas_list_discussions(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasDiscussionsListResponse:
    """Liste les discussions personas persistées (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    discussions = personas_storage.list_discussions(_resolve_plugin_data_dir(plugin_data_dir))
    return PersonasDiscussionsListResponse(discussions=discussions)


@app.get(
    "/plugins/personas/discussions/{discussion_id}",
    response_model=PersonasDiscussionDetailResponse,
)
async def personas_get_discussion(
    request: Request,
    discussion_id: str,
    plugin_data_dir: str,
    locale: str = "fr",
) -> PersonasDiscussionDetailResponse:
    """Détail d'une discussion personas avec messages (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_personas import storage as personas_storage

    discussion = personas_storage.get_discussion(
        _resolve_plugin_data_dir(plugin_data_dir),
        discussion_id,
    )
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return PersonasDiscussionDetailResponse(discussion=discussion)


@app.get("/memory/items", response_model=MemoryItemsResponse)
async def memory_list_items(
    request: Request,
    workspace_data_dir: str,
    memory_scope: Literal["user", "project"] = "project",
    locale: str = "fr",
) -> MemoryItemsResponse:
    """Liste les souvenirs explicites (user global ou project)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)
    ws_dir = _resolve_workspace_data_dir_path(workspace_data_dir)
    store = _memory_store_for_scope(settings, ws_dir, memory_scope)
    try:
        memories = store.list_memories()
    finally:
        store.close()
    return MemoryItemsResponse(memories=memories, memory_scope=memory_scope)


@app.get("/memory/search", response_model=MemorySearchResponse)
async def memory_search(
    request: Request,
    workspace_data_dir: str,
    query: str,
    memory_scope: Literal["user", "project", "all"] = "project",
    limit: int = 8,
    locale: str = "fr",
) -> MemorySearchResponse:
    """Recherche dans la mémoire (RAG projet + souvenirs explicites).

    `memory_scope`:
    - `project`: RAG + souvenirs explicites du workspace.
    - `user`: souvenirs explicites globaux (pas de RAG).
    - `all`: fusion cohérente user + project.
    """
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)
    ws_dir = _resolve_workspace_data_dir_path(workspace_data_dir)

    async def _search_one(scope: str) -> list[dict[str, Any]]:
        store = _memory_store_for_scope(settings, ws_dir, scope)
        try:
            return await store.search_combined(query=query, limit=limit)
        finally:
            store.close()

    if memory_scope == "all":
        user_hits = await _search_one("user")
        project_hits = await _search_one("project")
        results = [
            {**hit, "memory_scope": "user"}
            for hit in user_hits
        ] + [
            {**hit, "memory_scope": "project"}
            for hit in project_hits
        ]
    else:
        results = await _search_one(memory_scope)
    return MemorySearchResponse(results=results, memory_scope=memory_scope)


@app.post("/memory/add", response_model=MemoryAddResponse)
async def memory_add(
    request: Request,
    payload: MemoryAddRequest,
) -> MemoryAddResponse:
    """Ajoute un souvenir explicite (user global ou project)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(payload.locale)
    ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
    store = _memory_store_for_scope(settings, ws_dir, payload.memory_scope)
    try:
        memory = store.add_memory(
            content=payload.content,
            source="manual",
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        store.close()
    return MemoryAddResponse(memory=memory)


@app.post("/memory/forget", response_model=OkResponse)
async def memory_forget(
    request: Request,
    payload: MemoryForgetRequest,
) -> OkResponse:
    """Oublie un souvenir explicite (user global ou project)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
    store = _memory_store_for_scope(settings, ws_dir, payload.memory_scope)
    try:
        removed = store.forget_memory(payload.memory_id)
    finally:
        store.close()
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=t(locale, "memory.forget_not_found"),
        )
    return OkResponse(ok=True, detail=t(locale, "memory.forget_done"))


@app.delete("/memory", response_model=OkResponse)
async def memory_clear(
    request: Request,
    payload: MemoryClearRequest,
) -> OkResponse:
    """Efface la mémoire selon le scope (gate confirmation côté back).

    `memory_scope` sélectionne la base (user global ou project) ; `scope` conserve
    sa sémantique de granularité (all/memories/conversations, project uniquement).
    """
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    if not payload.confirmed:
        raise HTTPException(
            status_code=400,
            detail=t(locale, "memory.clear_confirm_required"),
        )

    from app.rag.store import clear_conversations

    ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
    detail = t(locale, "memory.clear_done_all")
    app_data = resolve_app_data_dir(ws_dir)

    if payload.memory_scope == "user":
        store = _memory_store_for_scope(settings, ws_dir, "user")
        try:
            store.clear_all(actor="user", scope="memories")
        finally:
            store.close()
        detail = t(locale, "memory.clear_done_memories")
        return OkResponse(ok=True, detail=detail)

    if payload.scope in {"all", "memories"}:
        store = _memory_store_for_scope(settings, ws_dir, "project")
        try:
            store.clear_all(actor="user", scope=payload.scope)
        finally:
            store.close()
        if payload.scope == "memories":
            detail = t(locale, "memory.clear_done_memories")

    if payload.scope in {"all", "conversations"}:
        clear_conversations(ws_dir)
        if payload.scope == "conversations":
            detail = t(locale, "memory.clear_done_conversations")
        if payload.scope == "conversations":
            log_event(
                app_data,
                "memory.forget_all",
                "user",
                {"scope": payload.scope},
            )

    return OkResponse(ok=True, detail=detail)


class BrowserNavigateRequest(BaseModel):
    plugin_data_dir: str
    url: str
    locale: str = "fr"
    settings_locked: bool = False
    permissions_network: bool = True


class BrowserSnapshotRequest(BaseModel):
    plugin_data_dir: str
    locale: str = "fr"
    settings_locked: bool = False
    permissions_network: bool = True


class BrowserActionRequest(BaseModel):
    plugin_data_dir: str
    action: Literal[
        "click", "type", "scroll", "press", "back", "forward", "extract"
    ]
    ref: str | None = None
    text: str | None = None
    selector: str | None = None
    key: str | None = None
    direction: Literal["up", "down", "left", "right"] | None = None
    locale: str = "fr"
    settings_locked: bool = False
    permissions_network: bool = True


class BrowserCloseRequest(BaseModel):
    plugin_data_dir: str
    locale: str = "fr"


class BrowserNavigateResponse(BaseModel):
    title: str
    url: str
    snapshot_yaml: str
    screenshot_b64: str


class BrowserSnapshotResponse(BaseModel):
    snapshot_yaml: str
    screenshot_b64: str
    title: str
    url: str


class BrowserActionResponse(BaseModel):
    snapshot_yaml: str
    screenshot_b64: str
    title: str = ""
    url: str = ""
    extracted: str | None = None


class BrowserStatusResponse(BaseModel):
    active: bool
    url: str
    title: str


class PersonasEstimateCostRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    mode: Literal["ask", "meeting", "discuss"]
    rounds: int = 3
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    settings_locked: bool = False


class PersonasEstimateCostResponse(BaseModel):
    estimated_tokens: int
    estimated_calls: int
    warning: str | None = None


def _assert_browser_allowed(
    *,
    settings_locked: bool,
    permissions_network: bool,
    locale: str,
) -> None:
    if settings_locked and not permissions_network:
        raise HTTPException(
            status_code=403,
            detail=t(locale, "errors.browser_locked"),
        )


def _browser_http_error(exc: Exception, locale: str) -> HTTPException:
    from app.plugins.workproba_browser.browser import BrowserError, browser_error_detail

    if isinstance(exc, BrowserError):
        code = str(exc)
        status = 400
        if code == "browser_session_inactive":
            status = 409
        if code == "browser_not_available":
            status = 503
        return HTTPException(status_code=status, detail=browser_error_detail(code, locale))
    return HTTPException(status_code=500, detail=str(exc))


@app.post("/plugins/browser/navigate", response_model=BrowserNavigateResponse)
async def browser_navigate_endpoint(
    request: Request,
    payload: BrowserNavigateRequest,
) -> BrowserNavigateResponse:
    """Navigation browser (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    _assert_browser_allowed(
        settings_locked=payload.settings_locked,
        permissions_network=payload.permissions_network,
        locale=locale,
    )

    from app.plugins.workproba_browser import browser as browser_mod

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    engine = browser_mod.get_engine(plugin_dir)
    try:
        result = await engine.navigate(
            payload.url,
            locale=locale,
            audit_app_data=resolve_app_data_dir(plugin_dir.parent),
            audit_actor="user",
        )
    except Exception as exc:  # noqa: BLE001
        raise _browser_http_error(exc, locale) from exc
    return BrowserNavigateResponse(**result)


@app.post("/plugins/browser/snapshot", response_model=BrowserSnapshotResponse)
async def browser_snapshot_endpoint(
    request: Request,
    payload: BrowserSnapshotRequest,
) -> BrowserSnapshotResponse:
    """Capture l'état courant du browser."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    _assert_browser_allowed(
        settings_locked=payload.settings_locked,
        permissions_network=payload.permissions_network,
        locale=locale,
    )

    from app.plugins.workproba_browser import browser as browser_mod

    engine = browser_mod.get_engine(_resolve_plugin_data_dir(payload.plugin_data_dir))
    try:
        result = await engine.snapshot(locale=locale)
    except Exception as exc:  # noqa: BLE001
        raise _browser_http_error(exc, locale) from exc
    return BrowserSnapshotResponse(**result)


@app.post("/plugins/browser/action", response_model=BrowserActionResponse)
async def browser_action_endpoint(
    request: Request,
    payload: BrowserActionRequest,
) -> BrowserActionResponse:
    """Action browser (click, type, scroll, etc.)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    _assert_browser_allowed(
        settings_locked=payload.settings_locked,
        permissions_network=payload.permissions_network,
        locale=locale,
    )

    from app.plugins.workproba_browser import browser as browser_mod

    engine = browser_mod.get_engine(_resolve_plugin_data_dir(payload.plugin_data_dir))
    try:
        if payload.action == "click":
            if not payload.ref:
                raise browser_mod.BrowserError("browser_ref_missing")
            result = await engine.click(payload.ref, locale=locale)
        elif payload.action == "type":
            if not payload.ref:
                raise browser_mod.BrowserError("browser_ref_missing")
            result = await engine.type_text(payload.ref, payload.text or "", locale=locale)
        elif payload.action == "scroll":
            direction = payload.direction or "down"
            result = await engine.scroll(payload.ref, direction, locale=locale)
        elif payload.action == "press":
            result = await engine.press(payload.key or "Enter", locale=locale)
        elif payload.action == "back":
            result = await engine.back(locale=locale)
        elif payload.action == "forward":
            result = await engine.forward(locale=locale)
        elif payload.action == "extract":
            if not payload.selector:
                raise browser_mod.BrowserError("browser_selector_missing")
            result = await engine.extract(payload.selector, locale=locale)
        else:
            raise HTTPException(status_code=400, detail="Unknown browser action")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _browser_http_error(exc, locale) from exc
    return BrowserActionResponse(**result)


@app.post("/plugins/browser/close", response_model=OkResponse)
async def browser_close_endpoint(
    request: Request,
    payload: BrowserCloseRequest,
) -> OkResponse:
    """Ferme la session browser pour un plugin_data_dir."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(payload.locale)

    from app.plugins.workproba_browser import browser as browser_mod

    browser_mod.close_engine(_resolve_plugin_data_dir(payload.plugin_data_dir))
    return OkResponse(ok=True)


@app.get("/plugins/browser/status", response_model=BrowserStatusResponse)
async def browser_status_endpoint(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> BrowserStatusResponse:
    """Statut de la session browser."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_browser import browser as browser_mod

    engine = browser_mod.get_engine(_resolve_plugin_data_dir(plugin_data_dir))
    status = engine.status()
    return BrowserStatusResponse(**status)


@app.post("/plugins/personas/estimate-cost", response_model=PersonasEstimateCostResponse)
async def personas_estimate_cost(
    request: Request,
    payload: PersonasEstimateCostRequest,
) -> PersonasEstimateCostResponse:
    """Estime le coût d'une session personas avant lancement."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_personas import estimate as personas_estimate

    _ = payload.provider_set  # réservé affinage futur par profil moteur
    _ = _resolve_plugin_data_dir(payload.plugin_data_dir)
    result = personas_estimate.estimate_personas_cost(
        persona_ids=payload.persona_ids,
        mode=payload.mode,
        rounds=payload.rounds,
        settings_locked=payload.settings_locked,
        locale=locale,
    )
    return PersonasEstimateCostResponse(
        estimated_tokens=result["estimated_tokens"],
        estimated_calls=result["estimated_calls"],
        warning=result.get("warning"),
    )


class AuditEntriesResponse(BaseModel):
    entries: list[dict[str, Any]]
    total: int


class AuditConfigResponse(BaseModel):
    retention_days: int
    enabled: bool


class AuditConfigUpdateRequest(BaseModel):
    workspace_data_dir: str
    retention_days: int | None = None
    enabled: bool | None = None
    settings_locked: bool = False
    locale: str = "fr"


class CloudStatusResponse(BaseModel):
    configured: bool
    mount_path: str | None = None
    last_sync: str | None = None
    synced_count: int = 0


class CloudConfigRequest(BaseModel):
    plugin_data_dir: str
    mount_path: str
    locale: str = "fr"


class CloudSyncRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    mount_path: str | None = None
    locale: str = "fr"


class CloudSyncResponse(BaseModel):
    synced: list[str]
    mount_path: str | None = None
    last_sync: str | None = None


def _resolve_app_data_from_workspace(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Workspace data directory not found")
    return resolve_app_data_dir(path)


@app.get("/audit", response_model=AuditEntriesResponse)
async def audit_list_entries(
    request: Request,
    workspace_data_dir: str,
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
    event: str | None = None,
    limit: int = 100,
    locale: str = "fr",
) -> AuditEntriesResponse:
    """Liste le journal d'audit local (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)
    app_data = _resolve_app_data_from_workspace(workspace_data_dir)
    entries, total = read_audit(
        app_data,
        from_ts=from_ts,
        to_ts=to_ts,
        event=event,
        limit=limit,
    )
    return AuditEntriesResponse(entries=entries, total=total)


@app.get("/audit/export")
async def audit_export(
    request: Request,
    workspace_data_dir: str,
    from_ts: str | None = Query(None, alias="from"),
    to_ts: str | None = Query(None, alias="to"),
    event: str | None = None,
    format: str = Query("csv", alias="format"),
    locale: str = "fr",
) -> Response:
    """Exporte le journal d'audit local en CSV (loopback + secret)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(locale)
    if format != "csv":
        raise HTTPException(
            status_code=400,
            detail=t(locale, "audit.export.unsupported_format", format=format),
        )
    app_data = _resolve_app_data_from_workspace(workspace_data_dir)
    csv_body = export_audit_csv(
        app_data,
        from_ts=from_ts,
        to_ts=to_ts,
        event=event,
        limit=0,
    )
    filename = t(locale, "audit.export.filename")
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/audit/config", response_model=AuditConfigResponse)
async def audit_get_config(
    request: Request,
    workspace_data_dir: str,
    audit_retention_days: int | None = None,
    audit_enabled: bool | None = None,
    locale: str = "fr",
) -> AuditConfigResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)
    app_data = _resolve_app_data_from_workspace(workspace_data_dir)
    config = get_audit_config(
        app_data,
        preset_retention_days=audit_retention_days,
        preset_enabled=audit_enabled,
    )
    return AuditConfigResponse(**config)


@app.post("/audit/config", response_model=AuditConfigResponse)
async def audit_update_config(
    request: Request,
    payload: AuditConfigUpdateRequest,
) -> AuditConfigResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    if payload.settings_locked:
        raise HTTPException(
            status_code=403,
            detail=t(locale, "audit.config_readonly"),
        )
    app_data = _resolve_app_data_from_workspace(payload.workspace_data_dir)
    config = save_audit_config(
        app_data,
        retention_days=payload.retention_days,
        enabled=payload.enabled,
    )
    return AuditConfigResponse(**config)


@app.get("/plugins/cloud/status", response_model=CloudStatusResponse)
async def cloud_status_endpoint(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> CloudStatusResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.registry import PLUGIN_WORKPROBA_PROJET, resolve_plugin_data_dir
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = _resolve_plugin_data_dir(plugin_data_dir)
    projet_dir = resolve_plugin_data_dir(PLUGIN_WORKPROBA_PROJET, cloud_dir)
    if projet_dir is None:
        projet_dir = cloud_dir.parent / PLUGIN_WORKPROBA_PROJET
    result = cloud_storage.status(cloud_dir, projet_dir)
    return CloudStatusResponse(**result)


@app.post("/plugins/cloud/config", response_model=OkResponse)
async def cloud_config_endpoint(
    request: Request,
    payload: CloudConfigRequest,
) -> OkResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    cloud_storage.save_config(cloud_dir, {"mount_path": payload.mount_path})
    return OkResponse(ok=True, detail=t(locale, "cloud.configured"))


@app.post("/plugins/cloud/sync", response_model=CloudSyncResponse)
async def cloud_sync_endpoint(
    request: Request,
    payload: CloudSyncRequest,
) -> CloudSyncResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.registry import PLUGIN_WORKPROBA_PROJET, resolve_plugin_data_dir
    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    projet_dir = resolve_plugin_data_dir(PLUGIN_WORKPROBA_PROJET, cloud_dir)
    if projet_dir is None:
        projet_dir = cloud_dir.parent / PLUGIN_WORKPROBA_PROJET
    try:
        result = cloud_storage.sync_project(
            plugin_data_dir=cloud_dir,
            projet_plugin_dir=projet_dir,
            project_id=payload.project_id,
            mount_path=payload.mount_path,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "project_not_found":
            detail = t(locale, "errors.project_not_found", project_id=payload.project_id)
            status = 404
        elif code == "cloud_not_configured":
            detail = t(locale, "cloud.not_configured")
            status = 400
        else:
            detail = code
            status = 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return CloudSyncResponse(
        synced=list(result.get("synced") or []),
        mount_path=result.get("mount_path"),
        last_sync=result.get("last_sync"),
    )
