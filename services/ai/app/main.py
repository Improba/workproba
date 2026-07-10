import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.responses import JSONResponse

from app.agent.compaction import compact_history_if_needed
from app.agent.confirmation import confirmation_registry
from app.agent.loop import AgentLoop
from app.agent.tools import build_agent
from app.auth import INTERNAL_SECRET_HEADER, internal_secret_middleware
from app.capabilities import Capabilities, detect_capabilities
from app.config import Settings, get_settings
from app.local_client import LocalProjectClient
from app.llm.config import build_model, build_model_settings, resolve_llm_config
from app.llm.provider import resolve_litellm_model
from app.llm.utility import generate_title, summarize_conversation
from app.rag.store import RagStore
from app.sandbox.runner import SandboxRunner
from app.schemas import (
    AgentConfirmRequest,
    AgentTurnRequest,
    CapabilitiesResponse,
    CompactionEvent,
    ErrorEvent,
    LLMProviderConfig,
    TurnStartEvent,
    UtilitySummarizeRequest,
    UtilitySummarizeResponse,
    UtilityTitleRequest,
    UtilityTitleResponse,
    VersionListResponse,
    VersionRestoreRequest,
    VersionRestoreResponse,
    VersionSnapshotInfo,
    WorkspaceIndexReport,
    WorkspaceIndexRequest,
)
from app.turn_manager import turn_manager
from app.versions import list_snapshots, restore_snapshot


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
            detail="Confirmation introuvable ou expirée.",
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
                "message": "Un tour agent est déjà en cours pour cette session.",
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
        ),
    )
    sandbox_runner = SandboxRunner(timeout_seconds=settings.sandbox_timeout_seconds, limits=limits)

    caps: Capabilities = request.app.state.capabilities
    cancel_event = asyncio.Event()

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
        try:
            yield to_sse_event(TurnStartEvent(turn_id=turn_id))

            llm_config = resolve_llm_config(payload.llm_provider_config, settings)
            compaction_event: CompactionEvent | None = None
            if payload.context_window and payload.auto_compact:
                payload.history, compaction_event = await compact_history_if_needed(
                    payload.history,
                    payload.context_window,
                    payload.auto_compact,
                    llm_config,
                    settings,
                )
            model = build_model(llm_config)
            agent = build_agent(
                model,
                ui_mode=payload.ui_mode,
                sandbox_available=caps.sandbox_available,
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
                        message=(
                            "Le tour agent a dépassé le délai maximal autorisé "
                            f"({settings.turn_timeout_seconds}s)."
                        ),
                    )
                )
        except Exception:
            yield to_sse_event(
                ErrorEvent(
                    code="internal_error",
                    message="Une erreur interne est survenue. Veuillez réessayer.",
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
) -> RagStore | None:
    embedding_model, embedding_base_url, embedding_api_key = resolve_embedding_config(
        settings, embedding_config
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
) -> tuple[str | None, str | None, str | None]:
    """Priorise la config par tour (app), puis les env du sidecar."""
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


@app.get("/versions", response_model=VersionListResponse)
async def list_file_versions(
    request: Request,
    project_path: str,
    session_id: str,
    file_path: str,
) -> VersionListResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    root = Path(project_path).expanduser().resolve()
    snapshots = list_snapshots(
        project_root=root,
        session_id=session_id,
        file_path=file_path,
    )
    return VersionListResponse(
        snapshots=[VersionSnapshotInfo.model_validate(item) for item in snapshots]
    )


@app.post("/versions/restore", response_model=VersionRestoreResponse)
async def restore_file_version(
    request: Request,
    payload: VersionRestoreRequest,
) -> VersionRestoreResponse:
    settings: Settings = request.app.state.settings
    require_internal_secret(request, settings)
    root = Path(payload.project_path).expanduser().resolve()
    result = restore_snapshot(
        project_root=root,
        session_id=payload.session_id,
        snapshot_path=payload.snapshot_path,
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
