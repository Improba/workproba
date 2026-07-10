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

/** Liste ordonnée des segments d'un message, pour respecter le flux réel :
 * texte -> outil -> texte -> ... */
export type ChatMessagePart = ChatTextPart | ChatToolCallPart;

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
  | 'tool_call_start'
  | 'confirmation_request'
  | 'tool_call_result'
  | 'done'
  | 'error';

export interface ChatStreamEvent {
  type: ChatStreamEventType;
  data: Record<string, unknown>;
}
