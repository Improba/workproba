from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

from app.config import ProviderName


JsonDict = dict[str, Any]

UiMode = Literal["guided", "advanced", "locked"]
ReasoningEffort = Literal["none", "low", "medium", "high"]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: JsonDict = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    thinking: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class DocumentReference(BaseModel):
    id: str
    name: str
    mime_type: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class LLMProviderConfig(BaseModel):
    provider: ProviderName
    model: str
    base_url: str | None = None
    api_key: SecretStr | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: ReasoningEffort | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)


class AgentTurnRequest(BaseModel):
    # Réservé pour une future isolation multi-tenant ; non appliqué côté local_client.
    tenant_id: str | None = None
    project_id: str
    project_path: str | None = None
    workspace_data_dir: str | None = None
    session_id: str
    # Identifiant de tour optionnel ; généré côté serveur si absent (event turn_start).
    turn_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    message: str
    llm_provider_config: LLMProviderConfig | None = None
    context_window: int | None = None
    auto_compact: bool = True
    # Config embeddings RAG par tour (gérée depuis l'app). Si absente, repli
    # sur les variables d'environnement LLM_EMBEDDING_* du sidecar.
    embedding_config: LLMProviderConfig | None = None
    documents: list[DocumentReference] = Field(default_factory=list)
    ui_mode: UiMode = "guided"

    @field_validator("history")
    @classmethod
    def validate_history_size(cls, history: list[ChatMessage]) -> list[ChatMessage]:
        from app.config import get_settings

        max_messages = get_settings().max_history_messages
        if len(history) > max_messages:
            raise ValueError(
                f"history exceeds maximum of {max_messages} messages "
                f"(got {len(history)})"
            )
        return history

    @field_validator("message")
    @classmethod
    def validate_message_size(cls, message: str) -> str:
        from app.config import get_settings

        max_length = get_settings().max_user_message_length
        if len(message) > max_length:
            raise ValueError(
                f"message exceeds maximum length of {max_length} characters "
                f"(got {len(message)})"
            )
        return message


class UtilityTitleRequest(BaseModel):
    first_user_message: str
    first_assistant_reply: str
    llm_provider_config: LLMProviderConfig | None = None
    utility_llm_config: LLMProviderConfig | None = None


class UtilityTitleResponse(BaseModel):
    title: str


class UtilitySummarizeRequest(BaseModel):
    messages: list[ChatMessage]
    llm_provider_config: LLMProviderConfig | None = None
    utility_llm_config: LLMProviderConfig | None = None
    focus: str | None = None


class UtilitySummarizeResponse(BaseModel):
    summary: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    content: str


class ThinkingStartEvent(BaseModel):
    type: Literal["thinking_start"] = "thinking_start"
    thinking_id: str


class ThinkingDeltaEvent(BaseModel):
    type: Literal["thinking_delta"] = "thinking_delta"
    thinking_id: str
    content: str


class ThinkingEndEvent(BaseModel):
    type: Literal["thinking_end"] = "thinking_end"
    thinking_id: str


class ToolCallStartEvent(BaseModel):
    type: Literal["tool_call_start"] = "tool_call_start"
    tool_call_id: str
    tool_name: str
    arguments: JsonDict = Field(default_factory=dict)
    human_summary: str = ""


class ToolCallResultEvent(BaseModel):
    type: Literal["tool_call_result"] = "tool_call_result"
    tool_call_id: str
    tool_name: str
    result: JsonDict = Field(default_factory=dict)
    is_error: bool = False
    human_summary: str = ""


class ConfirmationRequestEvent(BaseModel):
    type: Literal["confirmation_request"] = "confirmation_request"
    turn_id: str
    confirmation_id: str
    tool_call_id: str
    tool_name: str
    action: Literal["create", "modify"]
    proposed_path: str
    human_summary: str


class AgentConfirmRequest(BaseModel):
    session_id: str
    confirmation_id: str
    decision: Literal["approve", "deny"]
    # Rétrocompat : si absent, résolution sur la gate la plus récente de la session.
    turn_id: str | None = None


class CapabilitiesResponse(BaseModel):
    docker: bool
    sandbox_available: bool


class CompactionEvent(BaseModel):
    type: Literal["compaction"] = "compaction"
    dropped_count: int
    kept_count: int
    summary_tokens: int | None = None
    truncated: bool = False
    summary_failed: bool = False


class TurnStartEvent(BaseModel):
    type: Literal["turn_start"] = "turn_start"
    turn_id: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ErrorEvent(BaseModel):
    """Erreur SSE stable pour le front.

    Codes documentés :
    - internal_error : exception serveur non prévue (LLM, réseau, bug outil).
    - turn_timeout : dépassement du délai global du tour (LLM + outils + confirmation).
    - confirmation_timeout : l'utilisateur n'a pas répondu à temps à une confirmation.
    - usage_limit_exceeded : plafond d'itérations agent atteint.
    - unexpected_model_behavior : réponse modèle invalide (Pydantic AI).
    - turn_in_progress : un autre tour est déjà actif pour cette session (HTTP 409).
    - input_too_large : historique ou message utilisateur trop volumineux (HTTP 422).
    - agent_error : code générique historique (éviter pour les nouveaux cas).
    """

    type: Literal["error"] = "error"
    message: str
    code: str = "agent_error"


AgentEvent = Annotated[
    TokenEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallResultEvent
    | ConfirmationRequestEvent
    | CompactionEvent
    | TurnStartEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: JsonDict


class ToolResult(BaseModel):
    payload: JsonDict = Field(default_factory=dict)
    is_error: bool = False


class KnowledgeSearchResult(BaseModel):
    document_id: str
    chunk_id: str | None = None
    title: str | None = None
    content: str
    score: float | None = None
    metadata: JsonDict = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult] = Field(default_factory=list)


class DocumentContent(BaseModel):
    document_id: str
    name: str
    mime_type: str | None = None
    text: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class FileEntry(BaseModel):
    path: str
    name: str
    is_dir: bool = False
    size_bytes: int = 0
    kind: str = "file"


class FileListResponse(BaseModel):
    root: str
    entries: list[FileEntry] = Field(default_factory=list)
    truncated: bool = False
    truncation_reason: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class GeneratedFile(BaseModel):
    path: str
    mime_type: str | None = None
    content_base64: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class SandboxResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    files: list[GeneratedFile] = Field(default_factory=list)
    plots: list[GeneratedFile] = Field(default_factory=list)
    timed_out: bool = False
    metadata: JsonDict = Field(default_factory=dict)


class VersionSnapshotInfo(BaseModel):
    original_path: str
    snapshot_path: str
    timestamp: str
    session_id: str


class VersionListResponse(BaseModel):
    snapshots: list[VersionSnapshotInfo] = Field(default_factory=list)


class VersionRestoreRequest(BaseModel):
    project_path: str
    session_id: str
    snapshot_path: str


class VersionRestoreResponse(BaseModel):
    restored_path: str
    snapshot_path: str
    session_id: str


class WorkspaceIndexRequest(BaseModel):
    """Demande d'indexation RAG bulk du dossier de travail.

    `project_path` / `project_id` suivent la même résolution que `/agent/turn`.
    `embedding_config` prioritaire sur les env `LLM_EMBEDDING_*` du sidecar.
    `max_files` plafonne le nombre de fichiers indexés (borné par les limites).
    """

    project_path: str | None = None
    project_id: str = ""
    workspace_data_dir: str | None = None
    embedding_config: LLMProviderConfig | None = None
    max_files: int | None = None
    # Restreint l'indexation à une liste de chemins relatifs (re-index
    # incrémental déclenché par le watcher FS). None = passe complète.
    paths: list[str] | None = None


class WorkspaceIndexReport(BaseModel):
    """Rapport d'une passe d'indexation RAG du workspace."""

    project_root: str
    db_path: str | None = None
    enabled: bool = False
    scanned: int = 0
    indexed: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    total_chars: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    indexed_paths: list[str] = Field(default_factory=list)
    skipped_paths: list[str] = Field(default_factory=list)
    error_paths: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)
