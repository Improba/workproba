from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

from app.config import ProviderName
from app.i18n import DEFAULT_LOCALE, normalize_locale


JsonDict = dict[str, Any]

UiMode = Literal["guided", "advanced", "locked"]
Locale = Literal["fr", "en"]
ReasoningEffort = Literal["none", "low", "medium", "high"]
ProviderSetChatReasoning = Literal["auto", "none", "low", "medium", "high"]
ProviderSetOcrProvider = Literal["mistral", "mistral_ocr", "docling", "none"]
ProviderSetOcrMode = Literal["auto", "none"]
ProviderSetVisionMode = Literal["chat", "none"]
ProviderSetCapabilitiesReasoning = Literal["low", "medium", "high"]


def _coerce_locale(value: Any) -> str:
    if value is None:
        return DEFAULT_LOCALE
    return normalize_locale(str(value))


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
    # Contenu inline encodé base64 (pièces jointes au message depuis le chat).
    # Quand absent, le document est supposé exister sur disque (projet) et est
    # lu via l'outil read_document par son id/chemin relatif.
    content_base64: str | None = None
    kind: str | None = None
    size_bytes: int | None = None
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


class ProviderSetChat(BaseModel):
    provider: ProviderName
    model: str
    api_key_ref: str | None = None
    api_key: SecretStr | None = None
    base_url: str | None = None
    reasoning: ProviderSetChatReasoning = "auto"


class ProviderSetEmbeddings(BaseModel):
    provider: ProviderName
    model: str
    api_key_ref: str | None = None
    api_key: SecretStr | None = None
    base_url: str | None = None


class ProviderSetOcr(BaseModel):
    provider: ProviderSetOcrProvider | str = "none"
    mode: ProviderSetOcrMode = "auto"
    base_url: str | None = None
    api_key_ref: str | None = None
    api_key: SecretStr | None = None
    model: str | None = None

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_ocr_provider(cls, value: Any) -> Any:
        if value is None:
            return "none"
        normalized = str(value).strip().lower()
        if normalized == "mistral_ocr":
            return "mistral"
        return normalized


class ProviderSetVision(BaseModel):
    mode: ProviderSetVisionMode = "none"


class ProviderSetCapabilities(BaseModel):
    reasoning: ProviderSetCapabilitiesReasoning = "medium"
    vision: bool = False
    tools: bool = True


class ProviderSet(BaseModel):
    """Ensemble de providers IA (chat, embeddings, OCR, vision).

    ``chat_fallback`` : repli chat optionnel en cas d'indisponibilité du
    provider primaire (timeout, connexion, 5xx, 429). À configurer
    explicitement avec un provider que l'utilisateur sait disponible ;
    aucun repli automatique n'est appliqué sur les sets intégrés.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    badges: list[str] = Field(default_factory=list)
    chat: ProviderSetChat | None = None
    chat_fallback: ProviderSetChat | None = None
    embeddings: ProviderSetEmbeddings | None = None
    ocr: ProviderSetOcr | None = None
    vision: ProviderSetVision = Field(default_factory=ProviderSetVision)
    capabilities: ProviderSetCapabilities = Field(default_factory=ProviderSetCapabilities)
    is_default: bool = False
    is_builtin: bool = False
    ui_mode_locked: bool = False


class ProviderSetTestChatResult(BaseModel):
    ok: bool
    detail: str = ""
    models: list[str] | None = None


class ProviderSetTestEmbeddingsResult(BaseModel):
    ok: bool
    detail: str = ""


class ProviderSetTestOcrResult(BaseModel):
    ok: bool
    supported: bool
    detail: str = ""


class ProviderSetTestVisionResult(BaseModel):
    ok: bool
    supported: bool
    detail: str = ""


class ProviderSetTestResponse(BaseModel):
    chat: ProviderSetTestChatResult
    embeddings: ProviderSetTestEmbeddingsResult
    ocr: ProviderSetTestOcrResult
    vision: ProviderSetTestVisionResult


class AgentTurnRequest(BaseModel):
    # Réservé pour une future isolation multi-tenant ; non appliqué côté local_client.
    tenant_id: str | None = None
    project_id: str
    project_path: str | None = None
    workspace_data_dir: str | None = None
    workspace_title: str | None = None
    session_id: str
    # Identifiant de tour optionnel ; généré côté serveur si absent (event turn_start).
    turn_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    message: str
    llm_provider_config: LLMProviderConfig | None = None
    provider_set: ProviderSet | None = None
    context_window: int | None = None
    auto_compact: bool = True
    # Config embeddings RAG par tour (gérée depuis l'app). Si absente, repli
    # sur les variables d'environnement LLM_EMBEDDING_* du sidecar.
    embedding_config: LLMProviderConfig | None = None
    documents: list[DocumentReference] = Field(default_factory=list)
    ui_mode: UiMode = "guided"
    locale: Locale = "fr"
    active_plugins: list[str] | None = None
    plugin_data_dir: str | None = None
    settings_locked: bool = False
    permissions_network: bool = True
    code_execute: bool = True
    audit_retention_days: int | None = None
    audit_enabled: bool | None = None

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)

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
    locale: Locale = "fr"

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)


class UtilityTitleResponse(BaseModel):
    title: str


class UtilitySummarizeRequest(BaseModel):
    messages: list[ChatMessage]
    llm_provider_config: LLMProviderConfig | None = None
    utility_llm_config: LLMProviderConfig | None = None
    focus: str | None = None
    prior_summary: str | None = None
    locale: Locale = "fr"

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)


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


class PlanStepInfo(BaseModel):
    tool: str
    summary: str
    target: str = ""


class PlanProposedEvent(BaseModel):
    type: Literal["plan_proposed"] = "plan_proposed"
    session_id: str
    plan_id: str
    steps: list[PlanStepInfo] = Field(default_factory=list)
    rationale: str = ""


class AgentPlanApproveRequest(BaseModel):
    session_id: str
    plan_id: str
    approved: bool
    modifications: list[PlanStepInfo] | None = None
    turn_id: str | None = None
    locale: Locale = "fr"

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)


class AgentConfirmRequest(BaseModel):
    session_id: str
    confirmation_id: str
    decision: Literal["approve", "deny"]
    # Rétrocompat : si absent, résolution sur la gate la plus récente de la session.
    turn_id: str | None = None
    locale: Locale | None = None

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _coerce_locale(value)


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
    summary: str | None = None


class TurnStartEvent(BaseModel):
    type: Literal["turn_start"] = "turn_start"
    turn_id: str


class AttachmentStatusEvent(BaseModel):
    type: Literal["attachment_status"] = "attachment_status"
    message_id: str = ""
    attachment_id: str
    status_key: str
    label_locale: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class FallbackEvent(BaseModel):
    type: Literal["fallback"] = "fallback"
    turn_id: str
    from_provider: str
    to_provider: str
    from_model: str | None = None
    to_model: str | None = None
    reason: str


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
    - provider_unavailable : fournisseur IA indisponible (timeout, connexion, 5xx, 429).
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
    | PlanProposedEvent
    | CompactionEvent
    | TurnStartEvent
    | FallbackEvent
    | AttachmentStatusEvent
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


class DocumentPreviewResponse(BaseModel):
    type: Literal["docx", "xlsx", "pdf", "text", "image", "unsupported"]
    title: str
    html: str


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


class VersionInfo(BaseModel):
    version_id: str
    created_at: str
    size: int
    label: str = ""
    file_path: str = ""


class VersionListResponse(BaseModel):
    versions: list[VersionInfo] = Field(default_factory=list)


class VersionRestoreRequest(BaseModel):
    workspace_data_dir: str
    project_path: str
    file_path: str
    version_id: str
    locale: Locale = "fr"

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)


class VersionRestoreResponse(BaseModel):
    ok: bool = True
    restored_path: str
    version_id: str
    file_path: str


class PreviewChangeRequest(BaseModel):
    workspace_data_dir: str
    project_path: str
    file_path: str
    proposed_content: str
    locale: Locale = "fr"

    @field_validator("locale", mode="before")
    @classmethod
    def coerce_locale_field(cls, value: Any) -> str:
        return _coerce_locale(value)


class PreviewChangeResponse(BaseModel):
    is_new: bool
    is_binary: bool
    diff_html: str
    message: str = ""
    old_size: int = 0
    new_size: int = 0


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
    provider_set: ProviderSet | None = None


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
