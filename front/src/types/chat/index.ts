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
}

/** Codes d'erreur connus émis par le sidecar ou détectés côté front. */
export type ChatErrorCode =
  | 'idle_timeout'
  | 'sidecar_unreachable'
  | 'no_project'
  | 'max_iterations_reached'
  | 'agent_model_error'
  | 'agent_error'
  | (string & {});

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
  | 'token'
  | 'thinking_start'
  | 'thinking_delta'
  | 'thinking_end'
  | 'tool_call_start'
  | 'confirmation_request'
  | 'tool_call_result'
  | 'done'
  | 'error';

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

export type ChatStreamEventData =
  | { type: 'token'; token: string }
  | ({ type: 'thinking_start' } & ChatStreamThinkingStartData)
  | ({ type: 'thinking_delta' } & ChatStreamThinkingDeltaData)
  | ({ type: 'thinking_end' } & ChatStreamThinkingEndData)
  | Record<string, unknown>;

export interface ChatStreamEvent {
  type: ChatStreamEventType;
  data: Record<string, unknown>;
}
