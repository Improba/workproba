import type {
  ChatConfirmation,
  ChatError,
  ChatMessage,
  ChatMessagePart,
  ChatMessageRole,
  ChatToolCall,
  ToolCallStatus,
} from '#types';
import { normalizeChatErrorCode } from '#types';

const VALID_ROLES = new Set<ChatMessageRole>(['user', 'assistant']);
const VALID_TOOL_STATUSES = new Set<ToolCallStatus>([
  'pending',
  'running',
  'awaiting_confirmation',
  'success',
  'error',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function normalizeToolCall(raw: unknown): ChatToolCall | null {
  if (!isRecord(raw)) return null;
  const id = asString(raw.id).trim();
  const name = asString(raw.name).trim();
  if (!id || !name) return null;

  const statusRaw = asString(raw.status, 'success');
  const status = VALID_TOOL_STATUSES.has(statusRaw as ToolCallStatus)
    ? (statusRaw as ToolCallStatus)
    : 'success';

  const toolCall: ChatToolCall = { id, name, status };
  if (isRecord(raw.args)) toolCall.args = raw.args;
  if (raw.result !== undefined) toolCall.result = raw.result;
  if (typeof raw.startedAt === 'number') toolCall.startedAt = raw.startedAt;
  if (typeof raw.endedAt === 'number') toolCall.endedAt = raw.endedAt;
  if (typeof raw.filePath === 'string') toolCall.filePath = raw.filePath;
  if (typeof raw.snapshotPath === 'string') toolCall.snapshotPath = raw.snapshotPath;
  if (typeof raw.humanSummary === 'string') toolCall.humanSummary = raw.humanSummary;
  return toolCall;
}

function normalizePart(raw: unknown, messageId: string, index: number): ChatMessagePart | null {
  if (!isRecord(raw) || typeof raw.type !== 'string') return null;

  const id = asString(raw.id).trim() || `${messageId}__part_${index}`;

  if (raw.type === 'text') {
    return { type: 'text', id, content: asString(raw.content) };
  }
  if (raw.type === 'tool_call') {
    const toolCallId = asString(raw.toolCallId).trim();
    if (!toolCallId) return null;
    return { type: 'tool_call', id, toolCallId };
  }
  if (raw.type === 'thinking') {
    const thinkingId = asString(raw.thinkingId).trim() || `think-${index}`;
    return {
      type: 'thinking',
      id,
      thinkingId,
      content: asString(raw.content),
      done: Boolean(raw.done),
    };
  }
  return null;
}

function normalizeConfirmation(raw: unknown): ChatConfirmation | null {
  if (!isRecord(raw)) return null;
  const confirmationId = asString(raw.confirmationId).trim();
  const toolCallId = asString(raw.toolCallId).trim();
  const toolName = asString(raw.toolName).trim();
  const proposedPath = asString(raw.proposedPath).trim();
  if (!confirmationId || !toolCallId || !toolName) return null;

  return {
    confirmationId,
    toolCallId,
    toolName,
    action: raw.action === 'modify' ? 'modify' : 'create',
    proposedPath,
    humanSummary: asString(raw.humanSummary),
  };
}

function normalizeError(raw: unknown): ChatError | null {
  if (!isRecord(raw)) return null;
  const message = asString(raw.message).trim();
  if (!message) return null;
  return {
    code: normalizeChatErrorCode(asString(raw.code, 'unknown')),
    message,
    retryable: Boolean(raw.retryable),
  };
}

/** Valide et normalise un message chargé depuis le stockage local ou Tauri. */
export function normalizeChatMessage(raw: unknown): ChatMessage | null {
  if (!isRecord(raw)) return null;

  const id = asString(raw.id).trim();
  const roleRaw = asString(raw.role);
  if (!id || !VALID_ROLES.has(roleRaw as ChatMessageRole)) return null;

  const message: ChatMessage = {
    id,
    role: roleRaw as ChatMessageRole,
    content: asString(raw.content),
    createdAt: asString(raw.createdAt, new Date().toISOString()),
  };

  if (raw.parentId === null || typeof raw.parentId === 'string') {
    message.parentId = raw.parentId;
  }
  if (typeof raw.thinking === 'string') message.thinking = raw.thinking;
  if (raw.streaming === true) message.streaming = true;

  if (Array.isArray(raw.toolCalls)) {
    const toolCalls = raw.toolCalls
      .map((tc) => normalizeToolCall(tc))
      .filter((tc): tc is ChatToolCall => tc != null);
    if (toolCalls.length) message.toolCalls = toolCalls;
  }

  if (Array.isArray(raw.parts)) {
    const parts = raw.parts
      .map((part, index) => normalizePart(part, id, index))
      .filter((part): part is ChatMessagePart => part != null);
    if (parts.length) message.parts = parts;
  }

  const pendingConfirmation = normalizeConfirmation(raw.pendingConfirmation);
  if (pendingConfirmation) message.pendingConfirmation = pendingConfirmation;

  const error = normalizeError(raw.error);
  if (error) message.error = error;

  return message;
}

/** Filtre les entrées malformées sans faire planter le chargement de session. */
export function normalizeChatMessages(raw: unknown): ChatMessage[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => normalizeChatMessage(item))
    .filter((item): item is ChatMessage => item != null);
}
