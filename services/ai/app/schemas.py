from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, SecretStr

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
    tenant_id: str
    project_id: str
    project_path: str | None = None
    workspace_data_dir: str | None = None
    session_id: str
    history: list[ChatMessage] = Field(default_factory=list)
    message: str
    llm_provider_config: LLMProviderConfig | None = None
    # Config embeddings RAG par tour (gérée depuis l'app). Si absente, repli
    # sur les variables d'environnement LLM_EMBEDDING_* du sidecar.
    embedding_config: LLMProviderConfig | None = None
    documents: list[DocumentReference] = Field(default_factory=list)
    ui_mode: UiMode = "guided"


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


class CapabilitiesResponse(BaseModel):
    docker: bool
    sandbox_available: bool


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    content: str


class ErrorEvent(BaseModel):
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
