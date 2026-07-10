export type ChatMessageRole = 'user' | 'assistant';

export type ToolCallStatus =
  | 'pending'
  | 'running'
  | 'awaiting_confirmation'
  | 'success'
  | 'error';

export interface ChatConfirmation {
  confirmationId: string;
  toolCallId: string;
  toolName: string;
  action: 'create' | 'modify';
  proposedPath: string;
  humanSummary: string;
  /** Identifiant de tour backend, pour isoler la confirmation (résolution fine). */
  turnId?: string | null;
}

/** Codes d'erreur stables émis par le sidecar, le backend ou le front. */
export type ChatErrorCode =
  | 'idle_timeout'
  | 'sidecar_unreachable'
  | 'no_project'
  | 'confirm_failed'
  | 'max_iterations_reached'
  | 'agent_model_error'
  | 'agent_error'
  | 'internal_error'
  | 'turn_timeout'
  | 'confirmation_timeout'
  | 'usage_limit_exceeded'
  | 'unexpected_model_behavior'
  | 'turn_in_progress'
  | 'input_too_large'
  | 'parse_error'
  | 'unknown';

const KNOWN_CHAT_ERROR_CODES = new Set<string>([
  'idle_timeout',
  'sidecar_unreachable',
  'no_project',
  'confirm_failed',
  'max_iterations_reached',
  'agent_model_error',
  'agent_error',
  'internal_error',
  'turn_timeout',
  'confirmation_timeout',
  'usage_limit_exceeded',
  'unexpected_model_behavior',
  'turn_in_progress',
  'input_too_large',
  'parse_error',
  'unknown',
]);

export function normalizeChatErrorCode(code: string): ChatErrorCode {
  return KNOWN_CHAT_ERROR_CODES.has(code) ? (code as ChatErrorCode) : 'unknown';
}

export interface ChatError {
  /** Code machine (max_iterations_reached, sidecar_unreachable, …). */
  code: ChatErrorCode;
  /** Message localisé affichable. */
  message: string;
  /** true si l'utilisateur peut tenter un retry. */
  retryable: boolean;
}

export interface ChatToolCall {
  id: string;
  name: string;
  status: ToolCallStatus;
  args?: Record<string, unknown>;
  result?: unknown;
  startedAt?: number;
  endedAt?: number;
  filePath?: string;
  snapshotPath?: string;
  humanSummary?: string;
}

/** Segment texte d'un message assistant (rendu markdown). */
export interface ChatTextPart {
  type: 'text';
  id: string;
  content: string;
}

/** Segment « appel d'outil » inséré dans le flux du message (par id de tool call). */
export interface ChatToolCallPart {
  type: 'tool_call';
  id: string;
  toolCallId: string;
}

/** Segment « raisonnement » (thinking) inséré dans le flux du message assistant. */
export interface ChatThinkingPart {
  type: 'thinking';
  id: string;
  thinkingId: string;
  content: string;
  done: boolean;
}

export type ReasoningEffort = 'none' | 'low' | 'medium' | 'high';

/** Liste ordonnée des segments d'un message, pour respecter le flux réel :
 * texte -> outil -> texte -> ... */
export type ChatMessagePart = ChatTextPart | ChatToolCallPart | ChatThinkingPart;

export interface ChatMessage {
  id: string;
  parentId?: string | null;
  role: ChatMessageRole;
  content: string;
  toolCalls?: ChatToolCall[];
  /** Segments ordonnés (texte + appels d'outil) pour le rendu interleaved. */
  parts?: ChatMessagePart[];
  /** Erreur attachée au tour (timeout, sidecar down, erreur agent). */
  error?: ChatError | null;
  /** Demande de confirmation avant écriture fichier (flux de confiance). */
  pendingConfirmation?: ChatConfirmation | null;
  /** Texte de raisonnement persisté (rejoué au backend lors des tours suivants). */
  thinking?: string | null;
  streaming?: boolean;
  /** Compteur interne pour le virtual scroller pendant le streaming. */
  _contentRev?: number;
  createdAt: string;
}

export interface ChatSession {
  id: string;
  title: string;
  projectId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface WorkspaceDocument {
  id: string;
  name: string;
  mimeType: string;
  sizeBytes: number;
  updatedAt: string;
}

export interface CreateSessionPayload {
  title?: string;
  projectId?: string;
}

export interface SendMessagePayload {
  content: string;
  parentId?: string | null;
}

export type ChatStreamEventType =
  | 'turn_start'
  | 'token'
  | 'thinking_start'
  | 'thinking_delta'
  | 'thinking_end'
  | 'tool_call_start'
  | 'confirmation_request'
  | 'tool_call_result'
  | 'compaction'
  | 'done'
  | 'error';

export interface ChatStreamTokenData {
  token: string;
}

export interface ChatStreamTurnStartData {
  turnId: string;
}

export interface ChatStreamThinkingStartData {
  thinkingId: string;
}

export interface ChatStreamThinkingDeltaData {
  thinkingId: string;
  content: string;
}

export interface ChatStreamThinkingEndData {
  thinkingId: string;
}

export interface ChatStreamToolCallStartData {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  humanSummary?: string;
  filePath?: string;
}

export interface ChatStreamToolCallResultData {
  id: string;
  name: string;
  result?: unknown;
  error?: unknown;
  status?: ToolCallStatus;
  humanSummary?: string;
  filePath?: string;
}

export interface ChatStreamConfirmationRequestData {
  confirmationId: string;
  toolCallId: string;
  toolName: string;
  action: 'create' | 'modify';
  proposedPath: string;
  humanSummary: string;
  turnId?: string | null;
}

export interface ChatStreamErrorData {
  code: ChatErrorCode;
  message: string;
}

export interface ChatUsage {
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
}

export interface ChatCompactionInfo {
  droppedCount: number;
  keptCount: number;
  summaryTokens: number | null;
  truncated: boolean;
}

export interface ChatStreamDoneData {
  content: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
}

export interface ChatStreamCompactionData {
  dropped_count: number;
  kept_count: number;
  summary_tokens?: number | null;
  truncated?: boolean;
}

export type ChatStreamEvent =
  | { type: 'turn_start'; data: ChatStreamTurnStartData }
  | { type: 'token'; data: ChatStreamTokenData }
  | { type: 'thinking_start'; data: ChatStreamThinkingStartData }
  | { type: 'thinking_delta'; data: ChatStreamThinkingDeltaData }
  | { type: 'thinking_end'; data: ChatStreamThinkingEndData }
  | { type: 'tool_call_start'; data: ChatStreamToolCallStartData }
  | { type: 'tool_call_result'; data: ChatStreamToolCallResultData }
  | { type: 'confirmation_request'; data: ChatStreamConfirmationRequestData }
  | { type: 'compaction'; data: ChatStreamCompactionData }
  | { type: 'done'; data: ChatStreamDoneData }
  | { type: 'error'; data: ChatStreamErrorData };

/** Event SSE brut avant normalisation Python -> front. */
export interface RawChatStreamEvent {
  type: ChatStreamEventType | string;
  data: Record<string, unknown>;
}
