export type ChatMessageRole = 'user' | 'assistant' | 'system';

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
  effect?: string | null;
  targets?: string[];
  headline?: string;
  protectionLabels?: string[];
}

export interface ChatPlanStep {
  tool: string;
  summary: string;
  target: string;
}

export interface ChatProposedPlan {
  planId: string;
  steps: ChatPlanStep[];
  rationale: string;
  /** approved | rejected | pending */
  status?: 'pending' | 'approved' | 'rejected';
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
  | 'api_key_missing'
  | 'no_model'
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
  'api_key_missing',
  'no_model',
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

/** Nature d'un fichier joint, pour piloter rendu et transport. */
export type ChatAttachmentKind = 'image' | 'document' | 'text';

/** État de lecture d'une pièce jointe (encodage base64 / génération aperçu). */
export type ChatAttachmentStatus = 'reading' | 'ready' | 'error';

/**
 * Pièce jointe à un message utilisateur.
 *
 * Le contenu binaire est transporté vers le sidecar sous forme de `contentBase64`
 * (sans préfixe `data:`). `previewUrl` (URL d'objet) ne sert que pour l'aperçu
 * image côté UI et n'est jamais sérialisé ni persisté.
 */
export interface ChatAttachment {
  id: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  kind: ChatAttachmentKind;
  contentBase64?: string;
  /** URL d'objet pour l'aperçu image (non persistée). */
  previewUrl?: string;
  status: ChatAttachmentStatus;
  error?: string;
}

/** Variante persistée : on ne conserve que les métadonnées, pas les bytes. */
export type ChatAttachmentSnapshot = Omit<
  ChatAttachment,
  'contentBase64' | 'previewUrl'
>;

/** Liste ordonnée des segments d'un message, pour respecter le flux réel :
 * texte -> outil -> texte -> ... */
export type ChatMessagePart =
  | ChatTextPart
  | ChatToolCallPart
  | ChatThinkingPart;

export interface ChatMessage {
  id: string;
  parentId?: string | null;
  role: ChatMessageRole;
  /** Nature spéciale du message (ex. résumé de compaction). */
  messageKind?: 'compaction';
  content: string;
  toolCalls?: ChatToolCall[];
  /** Segments ordonnés (texte + appels d'outil) pour le rendu interleaved. */
  parts?: ChatMessagePart[];
  /** Erreur attachée au tour (timeout, sidecar down, erreur agent). */
  error?: ChatError | null;
  /** Demande de confirmation avant écriture fichier (flux de confiance). */
  pendingConfirmation?: ChatConfirmation | null;
  /** Plan proposé par l'agent (mode planification). */
  pendingPlan?: ChatProposedPlan | null;
  /** Texte de raisonnement persisté (rejoué au backend lors des tours suivants). */
  thinking?: string | null;
  /** Pièces jointes au message (côté user). Snapshots métadonnées après envoi. */
  attachments?: ChatAttachmentSnapshot[];
  streaming?: boolean;
  /** Carte d'avis personas (mode 1, distincte du message assistant). */
  personasOpinion?: PersonasOpinionCard | null;
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
  attachments?: ChatAttachment[];
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
  | 'plan_proposed'
  | 'compaction'
  | 'fallback'
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
  effect?: string | null;
  targets?: string[];
  headline?: string;
  protectionLabels?: string[];
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
  summary?: string | null;
  summaryFailed?: boolean;
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
  summary?: string | null;
  summary_failed?: boolean;
}

export interface ChatStreamFallbackData {
  turnId: string;
  fromProvider: string;
  toProvider: string;
  fromModel?: string | null;
  toModel?: string | null;
  reason: string;
}

export interface ChatStreamPlanProposedData {
  planId: string;
  steps: ChatPlanStep[];
  rationale: string;
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
  | { type: 'plan_proposed'; data: ChatStreamPlanProposedData }
  | { type: 'compaction'; data: ChatStreamCompactionData }
  | { type: 'fallback'; data: ChatStreamFallbackData }
  | { type: 'done'; data: ChatStreamDoneData }
  | { type: 'error'; data: ChatStreamErrorData };

/** Event SSE brut avant normalisation Python -> front. */
export interface RawChatStreamEvent {
  type: ChatStreamEventType | string;
  data: Record<string, unknown>;
}

/** Bloc d'avis d'un persona (mode « Demander l'avis »). */
export interface PersonasOpinionBlock {
  personaId: string;
  personaName: string;
  personaRole: string;
  avatarColor: string;
  avatarIcon?: string;
  content: string;
  memoryCitations?: string[];
  memoryCited?: boolean;
  streaming?: boolean;
}

/** Carte d'avis personas inline dans le chat. */
export interface PersonasOpinionCard {
  id: string;
  question: string;
  opinions: PersonasOpinionBlock[];
  streaming?: boolean;
}
