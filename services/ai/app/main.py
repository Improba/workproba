import asyncio
import base64
import binascii
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse, Response

from app.agent.compaction import (
    compact_history_if_needed,
    estimate_documents_overhead,
    estimate_memory_overhead,
)
from app.agent.memory_consolidation import promote_session_summary
from app.agent.confirmation import confirmation_registry
from app.agent.loop import AgentLoop
from app.agent.work_events import audit_details_with_work_id, work_id_for_turn
from app.agent.plan import plan_registry
from app.agent.tools import build_agent
from app.auth import INTERNAL_SECRET_HEADER, internal_secret_middleware
from app.capabilities import Capabilities, detect_capabilities
from app.config import Settings, get_settings
from app.local_client import LocalProjectClient
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.llm.cloud_errors import cloud_llm_error_message, parse_cloud_llm_error_code
from app.llm.fallback import FallbackableProviderError
from app.llm.provider import resolve_litellm_model
from app.llm.provider_sets import (
    CloudNotEnrolledError,
    MissingApiKeyError,
    ocr_is_supported,
    resolve_chat_from_set,
    resolve_embeddings_from_set,
    resolve_fallback_chat_config,
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
    FallbackEvent,
    LLMProviderConfig,
    PreviewChangeRequest,
    PreviewChangeResponse,
    ProviderSet,
    ProviderSetTestRequest,
    ProviderSetTestResponse,
    TurnStartEvent,
    WorkFailedEvent,
    UtilitySummarizeRequest,
    UtilitySummarizeResponse,
    UtilityTitleRequest,
    UtilityTitleResponse,
    VersionInfo,
    VersionListResponse,
    VersionPurgeRequest,
    VersionPurgeResponse,
    VersionRestoreRequest,
    VersionRestoreResponse,
    WorkspaceIndexReport,
    WorkspaceIndexRequest,
)
from app.i18n import normalize_locale, t
from app.turn_manager import turn_manager
from app.versions import list_versions, purge_versions, restore_version

logger = logging.getLogger(__name__)
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
async def llm_sets_test(payload: ProviderSetTestRequest) -> ProviderSetTestResponse:
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

    provider_set = ProviderSet.model_validate(
        payload.model_dump(exclude={"cloud_plugin_data_dir", "plugin_data_dir"})
    )
    cloud_dir = payload.cloud_plugin_data_dir
    plugin_dir = payload.plugin_data_dir

    try:
        chat_cfg = resolve_chat_from_set(
            provider_set,
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
        )
        chat_result_raw = await llm_test(chat_cfg)
        model_ids: list[str] | None = None
        if chat_result_raw.ok and chat_result_raw.model_count is not None:
            model_ids = []
        chat_result = ProviderSetTestChatResult(
            ok=chat_result_raw.ok,
            detail=chat_result_raw.detail,
            models=model_ids,
        )
    except CloudNotEnrolledError:
        chat_result = ProviderSetTestChatResult(
            ok=False,
            detail="Poste non connecté à Improba Cloud",
        )
    except MissingApiKeyError as exc:
        chat_result = ProviderSetTestChatResult(ok=False, detail=str(exc))
    except ValueError as exc:
        chat_result = ProviderSetTestChatResult(ok=False, detail=str(exc))

    try:
        embed_cfg = resolve_embeddings_from_set(
            provider_set,
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
        )
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
    except CloudNotEnrolledError:
        embed_result = ProviderSetTestEmbeddingsResult(
            ok=False,
            detail="Poste non connecté à Improba Cloud",
        )
    except MissingApiKeyError as exc:
        embed_result = ProviderSetTestEmbeddingsResult(ok=False, detail=str(exc))
    except ValueError as exc:
        embed_result = ProviderSetTestEmbeddingsResult(ok=False, detail=str(exc))

    ocr_supported = ocr_is_supported(provider_set)
    ocr_ok = False
    ocr_detail = "OCR absent ou désactivé"
    if ocr_supported:
        from app.ocr.mistral import MistralOcrClient, resolve_ocr_api_key

        try:
            MistralOcrClient(
                provider_set=provider_set,
                cloud_plugin_data_dir=cloud_dir,
                plugin_data_dir=plugin_dir,
            )
            if resolve_ocr_api_key(
                provider_set,
                cloud_plugin_data_dir=cloud_dir,
                plugin_data_dir=plugin_dir,
            ):
                ocr_ok = True
                ocr_detail = "OCR configuré"
            else:
                ocr_detail = "Clé API OCR manquante"
        except CloudNotEnrolledError:
            ocr_detail = "Poste non connecté à Improba Cloud"
        except ValueError as exc:
            ocr_detail = str(exc)
    ocr_result = ProviderSetTestOcrResult(
        ok=ocr_ok,
        supported=ocr_supported,
        detail=ocr_detail,
    )

    vision_supported = vision_is_supported(provider_set)
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
    except MissingApiKeyError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "api_key_missing", "message": str(exc)},
        ) from exc
    except CloudNotEnrolledError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "cloud_not_enrolled", "message": str(exc)},
        ) from exc
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
    except MissingApiKeyError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "api_key_missing", "message": str(exc)},
        ) from exc
    except CloudNotEnrolledError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "cloud_not_enrolled", "message": str(exc)},
        ) from exc
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


def _provider_set_cloud_dirs(payload: AgentTurnRequest) -> tuple[Path | None, Path | None]:
    plugin_dir = (
        Path(payload.plugin_data_dir).expanduser().resolve()
        if payload.plugin_data_dir
        else None
    )
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    return cloud_dir, plugin_dir


def _raise_provider_set_resolution_error(exc: Exception) -> None:
    if isinstance(exc, CloudNotEnrolledError):
        raise HTTPException(
            status_code=401,
            detail={"code": "cloud_not_enrolled", "message": str(exc)},
        ) from exc
    if isinstance(exc, MissingApiKeyError):
        raise HTTPException(
            status_code=400,
            detail={"code": "api_key_missing", "message": str(exc)},
        ) from exc
    raise exc


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

    cloud_dir, plugin_dir = _provider_set_cloud_dirs(payload)
    try:
        resolve_llm_config(
            payload.llm_provider_config,
            settings,
            provider_set=payload.provider_set,
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
        )
    except (MissingApiKeyError, CloudNotEnrolledError) as exc:
        await turn_manager.release(payload.session_id, turn_id)
        _raise_provider_set_resolution_error(exc)

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
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
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
                cloud_plugin_data_dir=cloud_dir,
                plugin_data_dir=plugin_dir,
            )
            compaction_event: CompactionEvent | None = None
            if payload.context_window and payload.auto_compact:
                overhead = (
                    settings.compaction_static_overhead
                    + estimate_memory_overhead(payload.workspace_data_dir)
                    + estimate_documents_overhead(payload.documents)
                )
                payload.history, compaction_event = await compact_history_if_needed(
                    payload.history,
                    payload.context_window,
                    payload.auto_compact,
                    llm_config,
                    settings,
                    locale=payload.locale,
                    overhead_tokens=overhead,
                )
            if compaction_event is not None:
                yield to_sse_event(compaction_event)

            fallback_config = (
                resolve_fallback_chat_config(
                    payload.provider_set,
                    cloud_plugin_data_dir=cloud_dir,
                    plugin_data_dir=plugin_dir,
                )
                if payload.provider_set
                else None
            )
            attempt_configs: list[tuple[LLMProviderConfig, bool]] = [
                (llm_config, False),
            ]
            if fallback_config is not None:
                attempt_configs.append((fallback_config, True))
            fallback_reason = ""

            try:
                async with asyncio.timeout(settings.turn_timeout_seconds):
                    for attempt_index, (config, strip_thinking) in enumerate(
                        attempt_configs
                    ):
                        cancel_event.clear()
                        if attempt_index == 1:
                            yield to_sse_event(
                                FallbackEvent(
                                    turn_id=turn_id,
                                    from_provider=llm_config.provider,
                                    to_provider=config.provider,
                                    from_model=llm_config.model,
                                    to_model=config.model,
                                    reason=fallback_reason,
                                )
                            )
                            audit_base = (
                                workspace_data_dir
                                if workspace_data_dir is not None
                                else (
                                    Path(payload.plugin_data_dir).expanduser().resolve()
                                    if payload.plugin_data_dir
                                    else project_root
                                )
                            )
                            log_event(
                                resolve_app_data_dir(audit_base),
                                "provider.fallback",
                                "agent",
                                audit_details_with_work_id(
                                    {
                                        "turn_id": turn_id,
                                        "from_provider": llm_config.provider,
                                        "to_provider": config.provider,
                                        "from_model": llm_config.model,
                                        "to_model": config.model,
                                        "reason": fallback_reason,
                                    },
                                    work_id_for_turn(turn_id),
                                    turn_id=turn_id,
                                    session_id=payload.session_id,
                                ),
                                enabled=payload.audit_enabled,
                            )
                            logger.info(
                                "Chat provider fallback (turn_id=%s from=%s/%s to=%s/%s reason=%s)",
                                turn_id,
                                llm_config.provider,
                                llm_config.model,
                                config.provider,
                                config.model,
                                fallback_reason,
                            )

                        model = build_model(config)
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
                            model_settings=build_model_settings(config, payload.provider_set),
                            project_root=project_root,
                            limits=limits,
                        )
                        try:
                            async for event in agent_loop.run_turn(
                                payload,
                                turn_id=turn_id,
                                cancel_event=cancel_event,
                                strip_thinking=strip_thinking,
                                is_fallback_attempt=attempt_index == 1,
                            ):
                                if await _client_disconnected(request):
                                    cancel_event.set()
                                    break
                                if cancel_event.is_set():
                                    break
                                yield to_sse_event(event)
                            break
                        except FallbackableProviderError as exc:
                            cloud_code = parse_cloud_llm_error_code(exc)
                            if cloud_code:
                                cloud_message = cloud_llm_error_message(
                                    cloud_code,
                                    payload.locale,
                                )
                                yield to_sse_event(
                                    WorkFailedEvent(
                                        work_id=work_id_for_turn(turn_id),
                                        code=cloud_code,
                                        message=cloud_message,
                                    )
                                )
                                yield to_sse_event(
                                    ErrorEvent(
                                        code=cloud_code,
                                        message=cloud_message,
                                    )
                                )
                                break
                            fallback_reason = exc.reason
                            if (
                                attempt_index == 0
                                and fallback_config is not None
                                and len(attempt_configs) > 1
                            ):
                                if await _client_disconnected(request):
                                    cancel_event.set()
                                    break
                                continue
                            provider_message = t(
                                payload.locale,
                                "loop.provider_unavailable",
                            )
                            yield to_sse_event(
                                WorkFailedEvent(
                                    work_id=work_id_for_turn(turn_id),
                                    code="provider_unavailable",
                                    message=provider_message,
                                )
                            )
                            yield to_sse_event(
                                ErrorEvent(
                                    code="provider_unavailable",
                                    message=provider_message,
                                )
                            )
                            break
            except TimeoutError:
                cancel_event.set()
                timeout_message = t(
                    payload.locale,
                    "main.turn_timeout",
                    seconds=settings.turn_timeout_seconds,
                )
                yield to_sse_event(
                    WorkFailedEvent(
                        work_id=work_id_for_turn(turn_id),
                        code="turn_timeout",
                        message=timeout_message,
                    )
                )
                yield to_sse_event(
                    ErrorEvent(
                        code="turn_timeout",
                        message=timeout_message,
                    )
                )
        except Exception:
            internal_message = t(payload.locale, "main.internal_error")
            yield to_sse_event(
                WorkFailedEvent(
                    work_id=work_id_for_turn(turn_id),
                    code="internal_error",
                    message=internal_message,
                )
            )
            yield to_sse_event(
                ErrorEvent(
                    code="internal_error",
                    message=internal_message,
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
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    plugin_dir = (
        Path(payload.plugin_data_dir).expanduser().resolve()
        if payload.plugin_data_dir
        else None
    )
    try:
        rag_store = build_rag_store(
            settings,
            workspace_data_dir,
            project_root,
            payload.embedding_config,
            provider_set=payload.provider_set,
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
        )
    except MissingApiKeyError:
        return WorkspaceIndexReport(
            project_root=project_root.as_posix(),
            enabled=False,
            metadata={"reason": "api_key_missing"},
        )
    except CloudNotEnrolledError:
        return WorkspaceIndexReport(
            project_root=project_root.as_posix(),
            enabled=False,
            metadata={"reason": "cloud_not_enrolled"},
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
    cloud_plugin_data_dir: Path | None = None,
    plugin_data_dir: Path | None = None,
) -> RagStore | None:
    embedding_model, embedding_base_url, embedding_api_key = resolve_embedding_config(
        settings,
        embedding_config,
        provider_set=provider_set,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
        plugin_data_dir=plugin_data_dir,
    )
    if not embedding_model:
        return None

    if workspace_data_dir is not None:
        from app.memory_stores import resolve_project_memory_db_path

        db_path = resolve_project_memory_db_path(workspace_data_dir)
    else:
        db_path = project_root / ".workproba" / "memory.db"

    return RagStore(
        db_path=db_path,
        embedding_model=embedding_model,
        embedding_base_url=embedding_base_url,
        embedding_api_key=embedding_api_key,
        embedding_batch_size=settings.limits.embedding_batch_size,
        embedding_batch_max_chars=settings.limits.embedding_batch_max_chars,
    )


def resolve_embedding_config(
    settings: Settings,
    embedding_config: LLMProviderConfig | None,
    *,
    provider_set: ProviderSet | None = None,
    cloud_plugin_data_dir: Path | None = None,
    plugin_data_dir: Path | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Priorise le set actif, puis la config par tour, puis les env du sidecar."""
    if provider_set is not None:
        set_embed = resolve_embeddings_from_set(
            provider_set,
            cloud_plugin_data_dir=cloud_plugin_data_dir,
            plugin_data_dir=plugin_data_dir,
        )
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

    # folder_path (project_path) et workspace_data_dir (.workproba) sont distincts en desktop.
    if project_path:
        base = Path(project_path).expanduser().resolve()
    else:
        base = Path(workspace_data_dir).expanduser().resolve()

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
            tool_name=payload.tool_name,
            tool_args=payload.tool_args,
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


@app.post("/versions/purge", response_model=VersionPurgeResponse)
async def purge_file_versions(
    request: Request,
    payload: VersionPurgeRequest,
) -> VersionPurgeResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    ws_dir = Path(payload.workspace_data_dir).expanduser().resolve()
    try:
        result = purge_versions(
            workspace_data_dir=ws_dir,
            file_path=payload.file_path,
            keep_last=payload.keep_last,
            older_than_days=payload.older_than_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VersionPurgeResponse.model_validate(result)


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
    cloud_plugin_data_dir: str | None = None
    plugin_data_dir: str | None = None


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
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    plugin_dir = (
        Path(payload.plugin_data_dir).expanduser().resolve()
        if payload.plugin_data_dir
        else None
    )
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
            cloud_plugin_data_dir=cloud_dir,
            plugin_data_dir=plugin_dir,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CloudNotEnrolledError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "cloud_not_enrolled", "message": str(exc)},
        ) from exc
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


class ProjetArtefactSyncStatusResponse(BaseModel):
    items: list[dict[str, Any]]


def _resolve_plugin_data_dir(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _resolve_workspace_root(payload: ProjetPublishRequest) -> Path:
    if payload.workspace_data_dir is None:
        raise HTTPException(status_code=400, detail="workspace_data_dir required")
    if payload.project_path:
        return Path(payload.project_path).expanduser().resolve()
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

    from app.plugins.workproba_projet.publish_route import (
        cloud_dir_for,
        cloud_publish_enabled,
        publish_artefact_routed,
    )

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    cloud_mode = cloud_publish_enabled(cloud_dir_for(plugin_dir))
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
        artefact = await publish_artefact_routed(
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
    except Exception as exc:  # noqa: BLE001
        if cloud_mode:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        raise
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


@app.get("/plugins/projet/artefacts/sync-status", response_model=ProjetArtefactSyncStatusResponse)
async def projet_artefacts_sync_status(
    request: Request,
    plugin_data_dir: str,
    project_id: str,
    cloud_plugin_data_dir: str | None = None,
    locale: str = "fr",
) -> ProjetArtefactSyncStatusResponse:
    """Statut mount/cloud par document publié."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
    from app.plugins.workproba_cloud.sync_service import list_artefact_sync_status

    plugins_root = _resolve_plugin_data_dir(plugin_data_dir).parent
    cloud_dir = (
        _resolve_plugin_data_dir(cloud_plugin_data_dir)
        if cloud_plugin_data_dir
        else plugins_root / "workproba.cloud"
    )
    try:
        sync_port = open_sync_port_for_cloud(plugins_root)
        items = await list_artefact_sync_status(
            cloud_dir=cloud_dir,
            sync_port=sync_port,
            project_id=project_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "project_not_found":
            raise HTTPException(
                status_code=404,
                detail=t(locale, "errors.project_not_found", project_id=project_id),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjetArtefactSyncStatusResponse(items=items)


class PersonasSetsResponse(BaseModel):
    sets: list[dict[str, Any]]


class PersonasSetPayload(BaseModel):
    id: str | None = None
    name: str
    personas: list[dict[str, Any]]


class PersonasSetResponse(BaseModel):
    set: dict[str, Any]


class ManagedRegardsInstallRequest(BaseModel):
    plugin_data_dir: str
    signed_bundle: dict[str, Any]
    locale: str = "fr"


class ManagedRegardsActivateRequest(BaseModel):
    plugin_data_dir: str
    catalog_id: str
    version: str | None = None
    locale: str = "fr"


class ManagedRegardsListResponse(BaseModel):
    catalogs: list[dict[str, Any]]
    status: dict[str, Any]


class ManagedRegardsInstallResponse(BaseModel):
    installed: dict[str, Any]


class ManagedRegardsActivateResponse(BaseModel):
    activated: dict[str, Any]


class PersonasAskRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    question: str
    context: str = ""
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    workspace_data_dir: str | None = None
    include_memory: bool = False
    cloud_plugin_data_dir: str | None = None


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
    cloud_plugin_data_dir: str | None = None


class PersonasDiscussRequest(BaseModel):
    plugin_data_dir: str
    persona_ids: list[str]
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    discussion_id: str | None = None
    context: str = ""
    provider_set: ProviderSet | None = None
    locale: str = "fr"
    workspace_data_dir: str | None = None
    include_memory: bool = False
    cloud_plugin_data_dir: str | None = None


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


class MemoryPromoteSessionRequest(BaseModel):
    workspace_data_dir: str
    session_id: str
    summary: str
    llm_provider_config: LLMProviderConfig | None = None
    utility_llm_config: LLMProviderConfig | None = None
    provider_set: ProviderSet | None = None
    cloud_plugin_data_dir: str | None = None
    locale: str = "fr"


class MemoryPromoteSessionResponse(BaseModel):
    session_id: str
    facts: list[str]
    results: list[dict[str, Any]]
    counts: dict[str, int]
    pruned: int = 0


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
    *,
    cloud_plugin_data_dir: Path | None = None,
) -> RagStore:
    from app.rag.store import open_memory_store

    rag = build_rag_store(
        settings,
        workspace_data_dir,
        workspace_data_dir,
        provider_set=provider_set,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
    )
    if rag is not None:
        return rag
    from app.memory_stores import resolve_project_memory_db_path

    return open_memory_store(resolve_project_memory_db_path(workspace_data_dir))


def _memory_store_for_scope(
    settings: Settings,
    workspace_data_dir: Path,
    memory_scope: str,
    provider_set: ProviderSet | None = None,
    *,
    cloud_plugin_data_dir: Path | None = None,
) -> RagStore:
    """Ouvre le store de mémoire adapté au scope (user global ou project)."""
    from app.memory_stores import VALID_SCOPES, open_memory_store_for_scope

    if memory_scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid memory scope")
    if memory_scope == "user":
        return open_memory_store_for_scope("user", workspace_data_dir)
    return _memory_store_for_workspace(
        settings,
        workspace_data_dir,
        provider_set,
        cloud_plugin_data_dir=cloud_plugin_data_dir,
    )


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

    plugin_dir = _resolve_plugin_data_dir(plugin_data_dir)
    sets = personas_storage.list_sets(plugin_dir)
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


@app.get("/plugins/personas/managed", response_model=ManagedRegardsListResponse)
async def personas_list_managed(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> ManagedRegardsListResponse:
    """Liste les catalogues Regards administrés installés localement."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.ports.managed_regards import create_personas_managed_port

    plugin_dir = _resolve_plugin_data_dir(plugin_data_dir)
    port = create_personas_managed_port(plugin_dir)
    return ManagedRegardsListResponse(
        catalogs=port.list_managed_catalogs(),
        status=port.get_catalog_status(),
    )


@app.post("/plugins/personas/managed/install", response_model=ManagedRegardsInstallResponse)
async def personas_install_managed(
    request: Request,
    payload: ManagedRegardsInstallRequest,
) -> ManagedRegardsInstallResponse:
    """Installe une version de catalogue signée dans le namespace personas."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(payload.locale)

    from app.plugins.ports.managed_regards import SignedBundle, create_personas_managed_port

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    port = create_personas_managed_port(plugin_dir)
    try:
        installed = port.install_catalog_version(SignedBundle.from_dict(payload.signed_bundle))
    except ValueError as exc:
        code = str(exc)
        status = 400
        if code == "invalid_signature":
            status = 403
        raise HTTPException(status_code=status, detail=code) from exc
    return ManagedRegardsInstallResponse(installed=installed)


@app.post(
    "/plugins/personas/managed/{catalog_id}/activate",
    response_model=ManagedRegardsActivateResponse,
)
async def personas_activate_managed(
    request: Request,
    catalog_id: str,
    payload: ManagedRegardsActivateRequest,
) -> ManagedRegardsActivateResponse:
    """Active un catalogue Regards administré installé."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(payload.locale)

    from app.plugins.ports.managed_regards import create_personas_managed_port

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    port = create_personas_managed_port(plugin_dir)
    try:
        activated = port.activate_catalog(catalog_id, payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ManagedRegardsActivateResponse(activated=activated)


@app.delete("/plugins/personas/managed/{catalog_id}/{version}", response_model=OkResponse)
async def personas_remove_managed_version(
    request: Request,
    catalog_id: str,
    version: str,
    plugin_data_dir: str,
    locale: str = "fr",
) -> OkResponse:
    """Supprime une version révoquée d'un catalogue administré."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(locale)

    from app.plugins.ports.managed_regards import create_personas_managed_port

    plugin_dir = _resolve_plugin_data_dir(plugin_data_dir)
    port = create_personas_managed_port(plugin_dir)
    if not port.remove_revoked_version(catalog_id, version):
        raise HTTPException(status_code=404, detail="catalog_version_not_found")
    return OkResponse(ok=True)


def _personas_sse_stream(
    generator: Any,
    rag_store: Any | None = None,
) -> Any:
    async def event_stream() -> AsyncIterator[dict[str, str]]:
        try:
            async for event in generator:
                yield {
                    "event": str(event.get("type", "message")),
                    "data": json.dumps(event, ensure_ascii=False),
                }
        finally:
            if rag_store is not None:
                rag_store.close()

    return event_stream


@app.post("/plugins/personas/ask")
async def personas_ask(request: Request, payload: PersonasAskRequest) -> EventSourceResponse:
    """Demander l'avis de personas (SSE, un bloc par persona)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_personas import orchestrator as personas_orchestrator

    plugin_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(
            settings,
            ws_dir,
            payload.provider_set,
            cloud_plugin_data_dir=cloud_dir,
        )

    stream = personas_orchestrator.stream_ask(
        plugin_data_dir=plugin_dir,
        persona_ids=payload.persona_ids,
        question=payload.question,
        context=payload.context,
        settings=settings,
        provider_set=payload.provider_set,
        locale=locale,
        rag_store=rag_store,
        cloud_plugin_data_dir=cloud_dir,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream, rag_store)(),
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
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(
            settings,
            ws_dir,
            payload.provider_set,
            cloud_plugin_data_dir=cloud_dir,
        )

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
        cloud_plugin_data_dir=cloud_dir,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream, rag_store)(),
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
    cloud_dir = (
        Path(payload.cloud_plugin_data_dir).expanduser().resolve()
        if payload.cloud_plugin_data_dir
        else None
    )
    rag_store = None
    if payload.include_memory and payload.workspace_data_dir:
        ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
        rag_store = _memory_store_for_workspace(
            settings,
            ws_dir,
            payload.provider_set,
            cloud_plugin_data_dir=cloud_dir,
        )

    stream = personas_orchestrator.stream_discuss(
        plugin_data_dir=plugin_dir,
        persona_ids=payload.persona_ids,
        message=payload.message,
        history=payload.history,
        discussion_id=payload.discussion_id,
        context=payload.context,
        settings=settings,
        provider_set=payload.provider_set,
        locale=locale,
        rag_store=rag_store,
        include_memory=payload.include_memory,
        cloud_plugin_data_dir=cloud_dir,
    )
    return EventSourceResponse(
        _personas_sse_stream(stream, rag_store)(),
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
        from app.agent.memory_consolidation import apply_explicit_memory_heuristic

        memory, _operation = apply_explicit_memory_heuristic(
            store,
            payload.content,
            source="manual",
            tags=payload.tags,
            update_threshold=settings.memory_promotion_overlap_threshold,
        )
        if payload.memory_scope == "project" and settings.memory_project_max_entries > 0:
            store.trim_memories_to_cap(
                settings.memory_project_max_entries,
                actor="system",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        store.close()
    return MemoryAddResponse(memory=memory)


@app.post("/memory/promote-session", response_model=MemoryPromoteSessionResponse)
async def memory_promote_session(
    request: Request,
    payload: MemoryPromoteSessionRequest,
) -> MemoryPromoteSessionResponse:
    """Promouvoit un résumé de session vers la mémoire project (extraction + consolidation)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)
    ws_dir = _resolve_workspace_data_dir_path(payload.workspace_data_dir)
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(status_code=400, detail="empty_summary")

    store = _memory_store_for_scope(settings, ws_dir, "project")
    try:
        chat_cfg = payload.llm_provider_config
        utility_cfg = payload.utility_llm_config
        if payload.provider_set is not None:
            chat_cfg = resolve_chat_from_set(
                payload.provider_set,
                cloud_plugin_data_dir=payload.cloud_plugin_data_dir,
            )
            utility_cfg = None
        result = await promote_session_summary(
            store,
            summary=summary,
            session_id=payload.session_id,
            workspace_data_dir=ws_dir,
            locale=locale,
            settings=settings,
            utility_llm_config=utility_cfg,
            chat_llm_config=chat_cfg,
            max_facts=settings.memory_promotion_max_facts,
            update_threshold=settings.memory_promotion_overlap_threshold,
            contradiction_enabled=settings.memory_promotion_contradiction_enabled,
            max_entries=settings.memory_project_max_entries,
        )
    except CloudNotEnrolledError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "cloud_not_enrolled", "message": str(exc)},
        ) from exc
    except MissingApiKeyError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "api_key_missing", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        store.close()

    return MemoryPromoteSessionResponse(
        session_id=str(result.get("session_id") or payload.session_id),
        facts=list(result.get("facts") or []),
        results=list(result.get("results") or []),
        counts=dict(result.get("counts") or {}),
        pruned=int(result.get("pruned") or 0),
    )


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


class BrowserBBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class BrowserViewport(BaseModel):
    width: int
    height: int


class BrowserNavigateResponse(BaseModel):
    title: str
    url: str
    snapshot_yaml: str
    screenshot_b64: str
    viewport: BrowserViewport | None = None


class BrowserSnapshotResponse(BaseModel):
    snapshot_yaml: str
    screenshot_b64: str
    title: str
    url: str
    viewport: BrowserViewport | None = None


class BrowserActionResponse(BaseModel):
    snapshot_yaml: str
    screenshot_b64: str
    title: str = ""
    url: str = ""
    extracted: str | None = None
    action_ref: str | None = None
    action_bbox: BrowserBBox | None = None
    viewport: BrowserViewport | None = None


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

    await browser_mod.close_engine_async(_resolve_plugin_data_dir(payload.plugin_data_dir))
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
    base_url: str | None = None
    enrolled: bool = False
    has_token: bool = False
    org_id: str | None = None
    org_label: str | None = None


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
    metadata_pushed: list[str] | None = None
    blobs_uploaded: list[str] | None = None
    skipped: list[str] | None = None


class CloudPullRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    locale: str = "fr"


class CloudPullResponse(BaseModel):
    pulled: list[str]
    skipped: list[str] | None = None
    errors: list[str] | None = None


class CloudEnrollRequest(BaseModel):
    plugin_data_dir: str
    base_url: str
    bearer_token: str | None = None
    device_code: str | None = None
    join_token: str | None = None
    org_id: str | None = None
    device_name: str | None = None
    locale: str = "fr"


class CloudEnrollResponse(BaseModel):
    authenticated: bool
    method: str | None = None
    pending: bool = False
    org_id: str | None = None


class CloudDisconnectRequest(BaseModel):
    plugin_data_dir: str
    locale: str = "fr"


class CloudSyncRegardsRequest(BaseModel):
    plugin_data_dir: str
    org_id: str | None = None
    locale: str = "fr"


class CloudSyncRegardsResponse(BaseModel):
    installed: list[dict[str, Any]]
    activated: dict[str, Any] | None = None
    count: int = 0


class CloudConnectorItem(BaseModel):
    id: str
    name: str
    runtime: str = "managed"
    description: str = ""


class CloudConnectorsResponse(BaseModel):
    connectors: list[CloudConnectorItem]
    enrolled: bool = False


class CloudLlmQuotaResponse(BaseModel):
    enabled: bool
    period_key: str
    tokens_used: int = 0
    tokens_limit: int = 0
    requests_count: int = 0
    requests_limit: int = 0
    remaining_tokens: int = 0
    remaining_requests: int = 0
    enrolled: bool = False


class CloudArtefactsResponse(BaseModel):
    artefacts: list[dict[str, Any]]


class CloudPublishArtefactRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    name: str
    source_path: str | None = None
    content: str | None = None
    workspace_data_dir: str | None = None
    project_path: str | None = None
    locale: str = "fr"


class CloudPublishArtefactResponse(BaseModel):
    artefact: dict[str, Any]


class CloudOpenArtefactRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    artefact_id: str
    locale: str = "fr"


class CloudOpenArtefactResponse(BaseModel):
    local_path: str
    artefact_id: str
    version: str
    filename: str


class CloudRepublishArtefactRequest(BaseModel):
    plugin_data_dir: str
    project_id: str
    artefact_id: str
    cache_path: str | None = None
    locale: str = "fr"


class CloudRepublishArtefactResponse(BaseModel):
    artefact: dict[str, Any]


def _resolve_cloud_publish_workspace(payload: CloudPublishArtefactRequest) -> Path:
    if payload.workspace_data_dir is None:
        raise HTTPException(status_code=400, detail="workspace_data_dir required")
    if payload.project_path:
        return Path(payload.project_path).expanduser().resolve()
    return Path(payload.workspace_data_dir).expanduser().resolve()


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

    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = _resolve_plugin_data_dir(plugin_data_dir)
    result = cloud_storage.status(cloud_dir)
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

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
    from app.plugins.workproba_cloud.sync_service import (
        is_cloud_enrolled,
        is_mount_configured,
        push_project_artefacts_to_cloud,
    )

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    if is_cloud_enrolled(cloud_dir):
        raise HTTPException(
            status_code=400,
            detail=t(locale, "cloud.use_cloud_sot_not_mirror_sync"),
        )
    has_mount = is_mount_configured(cloud_dir) or bool(
        payload.mount_path and payload.mount_path.strip()
    )
    if not has_mount and not is_cloud_enrolled(cloud_dir):
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    try:
        sync_port = open_sync_port_for_cloud(cloud_dir.parent)
        result: dict[str, Any] = {"synced": [], "mount_path": None, "last_sync": None}

        if is_mount_configured(cloud_dir) or (
            payload.mount_path and payload.mount_path.strip()
        ):
            result = cloud_storage.sync_project(
                plugin_data_dir=cloud_dir,
                sync_port=sync_port,
                project_id=payload.project_id,
                mount_path=payload.mount_path,
            )
        else:
            artefacts = sync_port.list_artefacts(payload.project_id)
            result["synced"] = [
                str(artefact.get("id"))
                for artefact in artefacts
                if artefact.get("id")
            ]

        base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
        if is_cloud_enrolled(cloud_dir) and base_url:
            client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
            push_result = await push_project_artefacts_to_cloud(
                cloud_dir=cloud_dir,
                sync_port=sync_port,
                project_id=payload.project_id,
                client=client,
            )
            result.update(push_result)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
        metadata_pushed=result.get("metadata_pushed"),
        blobs_uploaded=result.get("blobs_uploaded"),
        skipped=result.get("skipped"),
    )


@app.post("/plugins/cloud/pull", response_model=CloudPullResponse)
async def cloud_pull_endpoint(
    request: Request,
    payload: CloudPullRequest,
) -> CloudPullResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
    from app.plugins.workproba_cloud.sync_service import (
        is_cloud_enrolled,
        pull_project_artefacts_from_cloud,
    )

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    if is_cloud_enrolled(cloud_dir):
        raise HTTPException(
            status_code=400,
            detail=t(locale, "cloud.use_cloud_sot_not_mirror_sync"),
        )
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    try:
        sync_port = open_sync_port_for_cloud(cloud_dir.parent)
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        result = await pull_project_artefacts_from_cloud(
            cloud_dir=cloud_dir,
            sync_port=sync_port,
            project_id=payload.project_id,
            client=client,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        code = str(exc)
        if code == "project_not_found":
            detail = t(locale, "errors.project_not_found", project_id=payload.project_id)
            status = 404
        else:
            detail = code
            status = 400
        raise HTTPException(status_code=status, detail=detail) from exc

    return CloudPullResponse(
        pulled=list(result.get("pulled") or []),
        skipped=result.get("skipped"),
        errors=result.get("errors"),
    )


@app.get("/plugins/cloud/artefacts", response_model=CloudArtefactsResponse)
async def cloud_list_artefacts_endpoint(
    request: Request,
    plugin_data_dir: str,
    project_id: str,
    locale: str = "fr",
) -> CloudArtefactsResponse:
    """Liste les artefacts cloud d'un projet (source de vérité enrollé)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import (
        is_cloud_enrolled,
        list_cloud_artefacts_for_project,
    )

    cloud_dir = _resolve_plugin_data_dir(plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not is_cloud_enrolled(cloud_dir) or not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    artefacts = await list_cloud_artefacts_for_project(
        client=client,
        project_id=project_id,
        cloud_dir=cloud_dir,
    )
    return CloudArtefactsResponse(artefacts=artefacts)


@app.post("/plugins/cloud/artefacts/open", response_model=CloudOpenArtefactResponse)
async def cloud_open_artefact_endpoint(
    request: Request,
    payload: CloudOpenArtefactRequest,
) -> CloudOpenArtefactResponse:
    """Télécharge un artefact cloud dans le cache jetable et retourne le chemin local."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.cache_service import open_cloud_artefact_to_cache
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import is_cloud_enrolled

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not is_cloud_enrolled(cloud_dir) or not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    try:
        result = await open_cloud_artefact_to_cache(
            cloud_dir=cloud_dir,
            project_id=payload.project_id,
            artefact_id=payload.artefact_id,
            client=client,
        )
    except ValueError as exc:
        detail_key = {
            "artefact_not_found": "cloud.artefact_not_found",
            "artefact_not_confirmed": "cloud.artefact_not_confirmed",
            "missing_download_url": "cloud.download_failed",
            "checksum_mismatch": "cloud.download_failed",
            "size_mismatch": "cloud.download_failed",
            "invalid_remote_list": "cloud.download_failed",
        }.get(str(exc), "cloud.download_failed")
        raise HTTPException(status_code=400, detail=t(locale, detail_key)) from exc

    return CloudOpenArtefactResponse(
        local_path=str(result["local_path"]),
        artefact_id=str(result["artefact_id"]),
        version=str(result["version"]),
        filename=str(result["filename"]),
    )


@app.post("/plugins/cloud/artefacts/publish", response_model=CloudPublishArtefactResponse)
async def cloud_publish_artefact_endpoint(
    request: Request,
    payload: CloudPublishArtefactRequest,
) -> CloudPublishArtefactResponse:
    """Publie un artefact directement dans le cloud (projet enrollé)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.registry import PLUGIN_WORKPROBA_PROJET
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import (
        is_cloud_enrolled,
        publish_shared_artefact_to_cloud,
    )
    from app.plugins.workproba_projet import storage as projet_storage

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not is_cloud_enrolled(cloud_dir) or not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    projet_dir = cloud_dir.parent / PLUGIN_WORKPROBA_PROJET
    if projet_storage.find_project(projet_dir, payload.project_id) is None:
        raise HTTPException(
            status_code=404,
            detail=t(locale, "errors.project_not_found", project_id=payload.project_id),
        )

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

    try:
        if has_content:
            encoded = payload.content.encode("utf-8")
            if len(encoded) > projet_storage.MAX_PUBLISH_CONTENT_BYTES:
                raise ValueError("content_too_large")
            filename = projet_storage._sanitize_artefact_name(payload.name, markdown=True)
            content = encoded
        else:
            filename = projet_storage._sanitize_artefact_name(payload.name)
            workspace_root = _resolve_cloud_publish_workspace(payload)
            source = projet_storage.resolve_source_in_workspace(
                workspace_root,
                payload.source_path or "",
            )
            content = source.read_bytes()
            if len(content) > projet_storage.MAX_PUBLISH_CONTENT_BYTES:
                raise ValueError("content_too_large")
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
        if code == "content_too_large":
            status = 413
        else:
            status = 400
        raise HTTPException(status_code=status, detail=detail) from exc

    try:
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        artefact = await publish_shared_artefact_to_cloud(
            cloud_dir=cloud_dir,
            client=client,
            project_id=payload.project_id,
            filename=filename,
            content=content,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return CloudPublishArtefactResponse(artefact=artefact)


@app.post("/plugins/cloud/artefacts/republish", response_model=CloudRepublishArtefactResponse)
async def cloud_republish_artefact_endpoint(
    request: Request,
    payload: CloudRepublishArtefactRequest,
) -> CloudRepublishArtefactResponse:
    """Republie un artefact modifié depuis le cache local vers le cloud."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.cache_service import republish_cloud_artefact_from_cache
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import is_cloud_enrolled

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not is_cloud_enrolled(cloud_dir) or not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    try:
        artefact = await republish_cloud_artefact_from_cache(
            cloud_dir=cloud_dir,
            project_id=payload.project_id,
            artefact_id=payload.artefact_id,
            client=client,
            cache_path=payload.cache_path,
        )
    except ValueError as exc:
        detail_key = {
            "cache_not_found": "cloud.cache_not_found",
            "cache_path_outside_cache": "cloud.cache_not_found",
        }.get(str(exc), "cloud.republish_failed")
        raise HTTPException(status_code=400, detail=t(locale, detail_key)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return CloudRepublishArtefactResponse(artefact=artefact)


@app.post("/plugins/cloud/enroll", response_model=CloudEnrollResponse)
async def cloud_enroll_endpoint(
    request: Request,
    payload: CloudEnrollRequest,
) -> CloudEnrollResponse:
    """Enrôle le poste auprès du plan de contrôle cloud (bearer ou device code stub)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

    import socket

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    cloud_storage.save_config(cloud_dir, {"base_url": payload.base_url.rstrip("/")})
    client = CloudControlPlaneClient(
        base_url=payload.base_url,
        plugin_data_dir=cloud_dir,
    )
    try:
        if payload.join_token:
            resolved_name = (
                (payload.device_name or "").strip()
                or socket.gethostname()
                or "workproba-desktop"
            )
            join_payload = await client.join_with_token(
                token=payload.join_token,
                device_name=resolved_name,
            )
            tokens = client.load_tokens()
            result = {
                **join_payload,
                "authenticated": bool(tokens.get("access_token")),
                "method": "join_token",
                "org_id": tokens.get("org_id"),
            }
        elif payload.bearer_token:
            result = await client.authenticate(
                bearer_token=payload.bearer_token,
                device_code=None,
                org_id=payload.org_id,
            )
        elif payload.device_code:
            result = await client.authenticate(
                bearer_token=None,
                device_code=payload.device_code,
                org_id=payload.org_id,
            )
        elif payload.org_id:
            raise ValueError("join_token_required")
        else:
            raise ValueError("cloud_auth_required")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ = locale
    return CloudEnrollResponse(
        authenticated=bool(result.get("authenticated")),
        method=str(result.get("method")) if result.get("method") else None,
        pending=bool(result.get("pending")),
        org_id=str(result.get("org_id")) if result.get("org_id") else None,
    )


@app.post("/plugins/cloud/disconnect", response_model=OkResponse)
async def cloud_disconnect_endpoint(
    request: Request,
    payload: CloudDisconnectRequest,
) -> OkResponse:
    """Déconnecte le poste du cloud (suppression locale des jetons)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    _ = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    cloud_storage.clear_enrollment(cloud_dir)
    return OkResponse(ok=True)


@app.post("/plugins/cloud/sync-regards", response_model=CloudSyncRegardsResponse)
async def cloud_sync_regards_endpoint(
    request: Request,
    payload: CloudSyncRegardsRequest,
) -> CloudSyncRegardsResponse:
    """Télécharge les catalogues signés et les installe via ManagedRegardsPort."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    locale = normalize_locale(payload.locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.regards_access import open_managed_regards_port_for_cloud

    cloud_dir = _resolve_plugin_data_dir(payload.plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url:
        raise HTTPException(status_code=400, detail=t(locale, "cloud.not_configured"))

    try:
        client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
        port = open_managed_regards_port_for_cloud(cloud_dir.parent)
        result = await client.pull_and_install_regards(port, org_id=payload.org_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CloudSyncRegardsResponse(
        installed=list(result.get("installed") or []),
        activated=result.get("activated"),
        count=int(result.get("count") or 0),
    )


@app.get("/plugins/cloud/connectors", response_model=CloudConnectorsResponse)
async def cloud_list_connectors_endpoint(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> CloudConnectorsResponse:
    """Liste les connecteurs managés autorisés pour le poste enrollé (Mode A)."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    loc = normalize_locale(locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import is_cloud_enrolled

    cloud_dir = _resolve_plugin_data_dir(plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url or not is_cloud_enrolled(cloud_dir):
        return CloudConnectorsResponse(connectors=[], enrolled=False)

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    # Auth via DeviceBearer (access_token) : pas d'exigence de device_id local.

    try:
        payload = await client.list_connectors()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=t(loc, "cloud.connectors_auth_failed"),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        detail = t(loc, "cloud.connectors_load_failed")
        if detail == "cloud.connectors_load_failed":
            detail = f"connectors_unavailable:{exc}"
        raise HTTPException(status_code=502, detail=detail) from exc

    raw = payload.get("connectors") if isinstance(payload, dict) else None
    items: list[CloudConnectorItem] = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            items.append(
                CloudConnectorItem(
                    id=str(entry.get("id")),
                    name=str(entry.get("name") or entry.get("id")),
                    runtime=str(entry.get("runtime") or "managed"),
                    description=str(entry.get("description") or ""),
                )
            )
    return CloudConnectorsResponse(connectors=items, enrolled=True)


@app.get("/plugins/cloud/llm-quota", response_model=CloudLlmQuotaResponse)
async def cloud_llm_quota_endpoint(
    request: Request,
    plugin_data_dir: str,
    locale: str = "fr",
) -> CloudLlmQuotaResponse:
    """Consulte le quota LLM cloud pour le poste enrollé."""
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    loc = normalize_locale(locale)

    from app.plugins.workproba_cloud import storage as cloud_storage
    from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
    from app.plugins.workproba_cloud.sync_service import is_cloud_enrolled

    cloud_dir = _resolve_plugin_data_dir(plugin_data_dir)
    base_url = cloud_storage.get_control_plane_base_url(cloud_dir)
    if not base_url or not is_cloud_enrolled(cloud_dir):
        return CloudLlmQuotaResponse(
            enabled=False,
            period_key="",
            enrolled=False,
        )

    client = CloudControlPlaneClient(base_url=base_url, plugin_data_dir=cloud_dir)
    # DeviceBearer suffit pour /llm/v1/quota : pas d'exigence de device_id local
    # (l'enrôlement bearer ne le persiste pas toujours, contrairement au join).

    try:
        payload = await client.get_llm_quota()
    except PermissionError as exc:
        detail = str(exc).strip()
        if detail in ("invalid_device_token", "cloud_not_enrolled", "bearer_token_required"):
            raise HTTPException(status_code=401, detail=detail) from exc
        if detail in (
            "not_subscribed",
            "device_organization_required",
            "quota_exceeded",
            "org_id_required",
        ):
            status = 429 if detail == "quota_exceeded" else 403
            raise HTTPException(status_code=status, detail=detail) from exc
        raise HTTPException(
            status_code=403,
            detail=t(loc, "cloud.connectors_auth_failed"),
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="cloud_unreachable",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        detail = t(loc, "cloud.quota_load_failed")
        if detail == "cloud.quota_load_failed":
            detail = f"quota_unavailable:{exc}"
        raise HTTPException(status_code=502, detail=detail) from exc

    return CloudLlmQuotaResponse(
        enabled=bool(payload.get("enabled")),
        period_key=str(payload.get("periodKey") or payload.get("period_key") or ""),
        tokens_used=int(payload.get("tokensUsed") or payload.get("tokens_used") or 0),
        tokens_limit=int(payload.get("tokensLimit") or payload.get("tokens_limit") or 0),
        requests_count=int(
            payload.get("requestsCount") or payload.get("requests_count") or 0
        ),
        requests_limit=int(
            payload.get("requestsLimit") or payload.get("requests_limit") or 0
        ),
        remaining_tokens=int(
            payload.get("remainingTokens") or payload.get("remaining_tokens") or 0
        ),
        remaining_requests=int(
            payload.get("remainingRequests") or payload.get("remaining_requests") or 0
        ),
        enrolled=True,
    )
