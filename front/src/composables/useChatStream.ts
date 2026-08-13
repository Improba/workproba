import { ref, type Ref } from 'vue';
import { Notify } from 'quasar';
import type {
  ChatCompactionInfo,
  ChatConfirmation,
  ChatError,
  ChatMessage,
  ChatMessagePart,
  ChatPlanStep,
  ChatProposedPlan,
  MemoryCitation,
  ChatStreamCompactionData,
  ChatStreamErrorData,
  ChatStreamEvent,
  ChatStreamFallbackData,
  ChatToolCall,
  ChatUsage,
  RawChatStreamEvent,
  ReasoningEffort,
  SendMessagePayload,
  StreamCorrelation,
} from '#types';
import { normalizeChatErrorCode } from '#types';
import type { LocalDocumentEntry } from '@composables/useDesktop.types';
import {
  buildAgentTurnPayload,
  buildSidecarSecurityContext,
  chatAttachmentRelativePath,
  getAiSidecarUrl,
  getDesktopSecret,
  approveAgentPlan,
  SidecarHttpError,
  reprocessAttachment as callReprocessAttachment,
  type UiMode,
} from '@services/aiSidecar';
import {
  buildActiveLlmConfigs,
  buildActiveProviderSet,
  useAppSettings,
  type LlmConfigPayload,
} from '@composables/useAppSettings';
import {
  BROWSER_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
  PROJET_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  usePlugins,
} from '@composables/usePlugins';
import type { LlmProviderName } from '@composables/useDesktop.types';
import { mergeLlmConfigsWithSessionReasoning } from '@utils/llmRouting';
import { isBrowserAgentTool, type BrowserAgentToolName } from '@utils/browserTools';
import { ensureProviderSetChatReady, chatErrorCodeForReadiness, chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import { isMistralOutageCode, isNonRetryableCloudLlmCode } from '@utils/chatCloudErrors';
import { createIncidentId, sanitizeErrorDetail } from '@utils/errorReport';
import { contextWindowForSet } from '@utils/providerSetModels';
import { contextWindowFor } from '@utils/modelCatalog';
import { t } from '@utils/i18nT';
import { extractProposedPath, isFileWriteTool } from '@utils/fileWriteTools';
import {
  deriveThinkingSubject,
  deriveThinkingSubjectDone,
  deriveThinkingSummary,
} from '@utils/thinkingPresentation';
import {
  applyPersonasOpinionFromToolResult,
  appendSpecialistHandoffThinking,
  appendSpecialistHandoffToken,
  createRunningSpecialistHandoff,
  endSpecialistHandoffThinking,
  initStreamingPersonasOpinion,
  markPersonasOpinionAsError,
  markRunningSpecialistHandoffAsError,
  markSpecialistHandoffAsPending,
  markSpecialistHandoffAsRunning,
  rehydratePerspectiveCards,
  toolResultToSpecialistHandoff,
  upsertSpecialistNestedTool,
  type SpecialistMeta,
} from '@utils/specialistHandoff';
import { usePersonas } from '@composables/usePersonas';
import { useCloud } from '@composables/useCloud';
import {
  usesDeviceBearerAuth,
  validateProviderSetChatReady,
} from '@utils/providerSetValidation';

/** Délai sans aucune donnée SSE avant de déclarer le stream mort (ms). */
const IDLE_TIMEOUT_MS = 30_000;
/** Intervalle de regroupement des tokens avant mutation réactive (ms). */
const FLUSH_THROTTLE_MS = 50;
/** Délai entre deux dérivations de subject pendant thinking_delta (ms). */
const THINKING_SUBJECT_THROTTLE_MS = 275;

const thinkingSubjectThrottleTimers = new Map<string, ReturnType<typeof setTimeout>>();

function findThinkingPart(
  parts: ChatMessagePart[],
  thinkingId: string,
): Extract<ChatMessagePart, { type: 'thinking' }> | undefined {
  for (let i = parts.length - 1; i >= 0; i -= 1) {
    const part = parts[i];
    if (part.type === 'thinking' && part.thinkingId === thinkingId) {
      return part;
    }
  }
  return undefined;
}

function throttleThinkingSubject(
  messageId: string,
  thinkingId: string,
  part: Extract<ChatMessagePart, { type: 'thinking' }>,
): void {
  const key = `${messageId}:${thinkingId}`;
  if (thinkingSubjectThrottleTimers.has(key)) return;
  const timer = setTimeout(() => {
    thinkingSubjectThrottleTimers.delete(key);
    const subject = deriveThinkingSubject(part.content);
    if (subject) part.subject = subject;
  }, THINKING_SUBJECT_THROTTLE_MS);
  thinkingSubjectThrottleTimers.set(key, timer);
}

function clearAllThinkingSubjectThrottles(): void {
  for (const timer of thinkingSubjectThrottleTimers.values()) {
    clearTimeout(timer);
  }
  thinkingSubjectThrottleTimers.clear();
}

function clearThinkingSubjectThrottle(
  messageId: string,
  thinkingId: string,
): void {
  const key = `${messageId}:${thinkingId}`;
  const timer = thinkingSubjectThrottleTimers.get(key);
  if (!timer) return;
  clearTimeout(timer);
  thinkingSubjectThrottleTimers.delete(key);
}

/** Levée quand le stream SSE reste inactif au-delà de IDLE_TIMEOUT_MS. */
class StreamIdleTimeoutError extends Error {
  constructor() {
    super('Stream idle timeout');
    this.name = 'StreamIdleTimeoutError';
  }
}

function parseSseChunk(buffer: string): {
  events: RawChatStreamEvent[];
  rest: string;
} {
  const events: RawChatStreamEvent[] = [];
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = normalized.split('\n\n');
  const rest = blocks.pop() ?? '';

  for (const block of blocks) {
    const lines = block.split('\n');
    let eventType = 'message';
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (!dataLines.length) continue;

    try {
      const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>;
      const resolvedType =
        eventType !== 'message'
          ? eventType
          : typeof data.type === 'string' && data.type.trim()
            ? data.type.trim()
            : eventType;
      events.push({
        type: resolvedType,
        data,
      });
    } catch {
      events.push({
        type: 'error',
        data: { message: dataLines.join('\n') },
      });
    }
  }

  return { events, rest };
}

function extractHumanSummary(data: Record<string, unknown>): string {
  return String(data.human_summary ?? data.humanSummary ?? '');
}

function parseOptionalInt(value: unknown): number | null {
  if (value == null) return null;
  const n = typeof value === 'number' ? value : parseInt(String(value), 10);
  return Number.isFinite(n) ? n : null;
}

function parsePlanSteps(raw: unknown): ChatPlanStep[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const step = item as Record<string, unknown>;
      const tool = String(step.tool ?? '');
      const summary = String(step.summary ?? '');
      const target = String(step.target ?? '');
      if (!tool && !summary) return null;
      return { tool, summary, target };
    })
    .filter((s): s is ChatPlanStep => s !== null);
}

function parseMemoryCitations(raw: unknown): MemoryCitation[] {
  if (!Array.isArray(raw)) return [];
  const citations: MemoryCitation[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const record = item as Record<string, unknown>;
    const id = String(record.id ?? '').trim();
    const snippet = String(record.snippet ?? '').trim();
    if (!id || !snippet) continue;
    const scope = record.scope === 'user' ? 'user' : 'project';
    citations.push({
      id,
      snippet,
      source: typeof record.source === 'string' ? record.source : undefined,
      scope,
    });
  }
  return citations;
}

/** Extrait parent_tool_call_id depuis un payload SSE Python. */
function extractParentToolCallId(data: Record<string, unknown>): string | null {
  const raw = data.parent_tool_call_id ?? data.parentToolCallId;
  if (raw == null) return null;
  const value = String(raw).trim();
  return value || null;
}

function routesToSpecialistHandoff(
  assistant: ChatMessage,
  parentToolCallId: string | null | undefined,
): boolean {
  return Boolean(
    parentToolCallId &&
      assistant.specialistHandoff?.toolCallId === parentToolCallId,
  );
}

/** Mappe un event SSE Python vers le format interne du front (testable). */
export function mapPythonSseEvent(
  event: RawChatStreamEvent,
): ChatStreamEvent | null {
  const data = event.data;
  const parentToolCallId = extractParentToolCallId(data);

  switch (event.type) {
    case 'turn_start':
      return {
        type: 'turn_start',
        data: { turnId: String(data.turn_id ?? '') },
      };
    case 'token':
      return {
        type: 'token',
        data: {
          token: String(data.content ?? data.token ?? ''),
          parentToolCallId,
        },
      };
    case 'tool_call_start':
      return {
        type: 'tool_call_start',
        data: {
          id: String(data.tool_call_id ?? data.id ?? ''),
          name: String(data.tool_name ?? data.name ?? 'tool'),
          args: (data.arguments ?? data.args ?? {}) as Record<string, unknown>,
          humanSummary: extractHumanSummary(data),
          parentToolCallId,
        },
      };
    case 'tool_call_result': {
      const isError = Boolean(data.is_error ?? data.error);
      return {
        type: 'tool_call_result',
        data: {
          id: String(data.tool_call_id ?? data.id ?? ''),
          name: String(data.tool_name ?? data.name ?? 'tool'),
          result: data.result,
          error: isError ? (data.result ?? true) : null,
          status: isError ? 'error' : 'success',
          humanSummary: extractHumanSummary(data),
          filePath:
            typeof data.file_path === 'string'
              ? data.file_path
              : typeof data.filePath === 'string'
                ? data.filePath
                : undefined,
          parentToolCallId,
        },
      };
    }
    case 'confirmation_preparing':
      return {
        type: 'confirmation_preparing',
        data: {
          toolCallId: String(data.tool_call_id ?? ''),
          toolName: String(data.tool_name ?? ''),
          connectorId: String(data.connector_id ?? ''),
          action: String(data.action ?? ''),
        },
      };
    case 'confirmation_request':
      return {
        type: 'confirmation_request',
        data: {
          confirmationId: String(data.confirmation_id ?? ''),
          toolCallId: String(data.tool_call_id ?? ''),
          toolName: String(data.tool_name ?? ''),
          action: data.action === 'modify' ? 'modify' : 'create',
          proposedPath: String(data.proposed_path ?? ''),
          humanSummary: extractHumanSummary(data),
          turnId: data.turn_id != null ? String(data.turn_id) : null,
          effect: typeof data.effect === 'string' ? data.effect : null,
          targets: Array.isArray(data.targets) ? data.targets : [],
          headline: String(data.headline ?? ''),
          protectionLabels: Array.isArray(data.protection_labels)
            ? data.protection_labels.map(String)
            : Array.isArray(data.protectionLabels)
              ? data.protectionLabels.map(String)
              : [],
          trustKey:
            typeof data.trust_key === 'string' && data.trust_key.trim()
              ? data.trust_key.trim()
              : typeof data.trustKey === 'string' && data.trustKey.trim()
                ? data.trustKey.trim()
                : null,
        },
      };
    case 'tool_auto_approved':
      return {
        type: 'tool_auto_approved',
        data: {
          toolCallId: String(data.tool_call_id ?? ''),
          toolName: String(data.tool_name ?? ''),
          trustKey: String(data.trust_key ?? data.trustKey ?? ''),
        },
      };
    case 'thinking_start':
      return {
        type: 'thinking_start',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
          parentToolCallId,
        },
      };
    case 'thinking_delta':
      return {
        type: 'thinking_delta',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
          content: String(data.content ?? ''),
          parentToolCallId,
        },
      };
    case 'thinking_end':
      return {
        type: 'thinking_end',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
          parentToolCallId,
        },
      };
    case 'memory_citations':
      return {
        type: 'memory_citations',
        data: {
          citations: parseMemoryCitations(data.citations),
        },
      };
    case 'done':
      return {
        type: 'done',
        data: {
          content: String(data.content ?? ''),
          input_tokens: parseOptionalInt(data.input_tokens ?? data.inputTokens),
          output_tokens: parseOptionalInt(
            data.output_tokens ?? data.outputTokens,
          ),
          total_tokens: parseOptionalInt(data.total_tokens ?? data.totalTokens),
        },
      };
    case 'compaction':
      return {
        type: 'compaction',
        data: {
          dropped_count: Number(data.dropped_count ?? 0) || 0,
          kept_count: Number(data.kept_count ?? 0) || 0,
          summary_tokens: parseOptionalInt(
            data.summary_tokens ?? data.summaryTokens,
          ),
          truncated: Boolean(data.truncated ?? false),
          summary:
            data.summary != null ? String(data.summary) : null,
          summary_failed: Boolean(data.summary_failed ?? data.summaryFailed ?? false),
        },
      };
    case 'fallback':
      return {
        type: 'fallback',
        data: {
          turnId: String(data.turn_id ?? ''),
          fromProvider: String(data.from_provider ?? ''),
          toProvider: String(data.to_provider ?? ''),
          fromModel:
            data.from_model != null ? String(data.from_model) : null,
          toModel: data.to_model != null ? String(data.to_model) : null,
          reason: String(data.reason ?? ''),
        },
      };
    case 'error': {
      const code = normalizeChatErrorCode(String(data.code ?? 'agent_error'));
      const rawMessage = String(data.message ?? '');
      const localizedMessage = localizeAgentError(code, rawMessage);
      const sanitizedRaw = rawMessage.trim()
        ? sanitizeErrorDetail(rawMessage)
        : '';
      const detail =
        sanitizedRaw && sanitizedRaw !== localizedMessage ? sanitizedRaw : null;
      return {
        type: 'error',
        data: {
          code,
          message: localizedMessage,
          detail,
          turnId: data.turn_id != null ? String(data.turn_id) : null,
          workId: data.work_id != null ? String(data.work_id) : null,
          sessionId: data.session_id != null ? String(data.session_id) : null,
          incidentId: data.incident_id != null ? String(data.incident_id) : null,
        },
      };
    }
    case 'plan_proposed':
      return {
        type: 'plan_proposed',
        data: {
          planId: String(data.plan_id ?? ''),
          steps: parsePlanSteps(data.steps),
          rationale: String(data.rationale ?? ''),
        },
      };
    case 'work_started':
      return {
        type: 'work_started',
        data: {
          workId: String(data.work_id ?? ''),
          objective:
            data.objective != null ? String(data.objective) : undefined,
        },
      };
    case 'work_contribution':
      if (import.meta.env.DEV) {
        console.debug('[useChatStream] work event', event.type, {
          turnId: data.turn_id != null ? String(data.turn_id) : null,
          workId: data.work_id != null ? String(data.work_id) : null,
        });
      }
      return null;
    case 'work_completed':
    case 'work_failed':
      return {
        type: 'work_terminal',
        data: {
          workId: String(data.work_id ?? ''),
        },
      };
    default:
      return null;
  }
}

function createMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function createPartId(): string {
  return `part_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/** Applique la compaction côté client : retire les anciens messages et insère le résumé. */
export function applyCompactionToMessages(
  messages: ChatMessage[],
  data: ChatStreamCompactionData,
): void {
  const droppedCount = Number(data.dropped_count ?? 0) || 0;
  if (droppedCount <= 0 && !data.summary?.trim()) return;

  const prefix = messages.slice(0, -2);
  const drop = Math.min(droppedCount, prefix.length);
  const priorCompaction = prefix.find((m) => m.messageKind === 'compaction');
  const kept = prefix.slice(drop);
  const tail = messages.slice(-2);
  const summary = data.summary?.trim() ?? '';

  const keptWithoutCompaction = summary
    ? kept.filter((message) => message.messageKind !== 'compaction')
    : kept;
  const next = [...keptWithoutCompaction, ...tail];

  if (summary) {
    const prefixI18n = t('chat.compactionContentPrefix');
    next.unshift({
      id: createMessageId(),
      role: 'user',
      content: `${prefixI18n}${summary}`,
      messageKind: 'compaction',
      createdAt: new Date().toISOString(),
    });
  } else if (
    priorCompaction &&
    !next.some((message) => message.id === priorCompaction.id)
  ) {
    // Fallback serveur sans nouveau résumé : conserver le résumé antérieur en tête.
    next.unshift(priorCompaction);
  }

  messages.splice(0, messages.length, ...next);
}

function compactionInfoFromEvent(data: ChatStreamCompactionData): ChatCompactionInfo {
  return {
    droppedCount: Number(data.dropped_count ?? 0) || 0,
    keptCount: Number(data.kept_count ?? 0) || 0,
    summaryTokens: parseOptionalInt(data.summary_tokens),
    truncated: Boolean(data.truncated ?? false),
    summary: data.summary ?? null,
    summaryFailed: Boolean(data.summary_failed ?? false),
  };
}

function notifyProviderFallback(data: ChatStreamFallbackData): void {
  const toModel = data.toModel?.trim();
  const message = toModel
    ? t('chat.providerFallbackWithModel', {
        toProvider: data.toProvider,
        toModel,
      })
    : t('chat.providerFallback', { toProvider: data.toProvider });
  Notify.create({ message, color: 'warning', timeout: 5000 });
}

/** Enrichit subject/summary d'une part thinking si absents mais content présent. */
function enrichThinkingPresentation(
  part: Extract<ChatMessagePart, { type: 'thinking' }>,
): void {
  if (!part.content.trim()) return;
  if (!part.subject) {
    const subject = deriveThinkingSubjectDone(part.content);
    if (subject) part.subject = subject;
  }
  if (!part.summary) {
    const summary = deriveThinkingSummary(part.content);
    if (summary) part.summary = summary;
  }
}

/** Reconstruit des `parts` ordonnées pour un message legacy sans parts. */
function buildLegacyParts(message: ChatMessage): ChatMessagePart[] {
  const parts: ChatMessagePart[] = [];
  if (message.thinking) {
    const thinkingPart: Extract<ChatMessagePart, { type: 'thinking' }> = {
      type: 'thinking',
      id: `${message.id}__thinking`,
      thinkingId: 'think-0',
      content: message.thinking,
      done: true,
    };
    enrichThinkingPresentation(thinkingPart);
    parts.push(thinkingPart);
  }
  if (message.content || message.streaming) {
    parts.push({
      type: 'text',
      id: `${message.id}__text`,
      content: message.content,
    });
  }
  for (const tc of message.toolCalls ?? []) {
    parts.push({
      type: 'tool_call',
      id: `${message.id}__tc_${tc.id}`,
      toolCallId: tc.id,
    });
  }
  return parts;
}

function bumpContentRev(message: ChatMessage): void {
  message._contentRev = (message._contentRev ?? 0) + 1;
}

function appendTextToParts(assistant: ChatMessage, text: string): void {
  if (!text) return;
  const parts = assistant.parts ?? (assistant.parts = []);
  const last = parts[parts.length - 1];
  if (last && last.type === 'text') {
    last.content += text;
  } else {
    // Le dernier segment est un appel d'outil : on ouvre un nouveau
    // segment texte pour la suite du flux.
    parts.push({ type: 'text', id: createPartId(), content: text });
  }
  if (assistant.streaming) bumpContentRev(assistant);
}

function syncContent(assistant: ChatMessage): void {
  assistant.content = (assistant.parts ?? [])
    .filter(
      (p): p is { type: 'text'; id: string; content: string } =>
        p.type === 'text',
    )
    .map((p) => p.content)
    .join('');
}

/** Traduit un code d'erreur agent en message affichable. */
function localizeAgentError(code: string, fallback: string): string {
  switch (code) {
    case 'max_iterations_reached':
      return t('errors.agentMaxIterations');
    case 'agent_model_error':
    case 'unexpected_model_behavior':
      return t('errors.agentModelError');
    case 'turn_timeout':
      return t('errors.agentTurnTimeout');
    case 'confirmation_timeout':
      return t('errors.agentConfirmationTimeout');
    case 'confirmation_not_found':
      return t('errors.confirmationNotFound');
    case 'stream_ended':
      return t('errors.streamEndedGate');
    case 'idle_timeout':
      return t('errors.idleTimeout');
    case 'plan_timeout':
      return t('errors.agentPlanTimeout');
    case 'usage_limit_exceeded':
      return t('errors.agentUsageLimit');
    case 'turn_in_progress':
      return t('errors.agentTurnInProgress');
    case 'input_too_large':
      return t('errors.agentInputTooLarge');
    case 'api_key_missing':
      return t('errors.apiKeyMissing');
    case 'cloud_not_enrolled':
      return t('errors.cloudNotEnrolled');
    case 'not_subscribed':
      return t('errors.cloudNotSubscribed');
    case 'quota_exceeded':
      return t('errors.cloudQuotaExceeded');
    case 'cloud_unreachable':
      return t('errors.cloudUnreachable');
    case 'mistral_unavailable':
    case 'mistral_timeout':
    case 'mistral_upstream_error':
      return t('errors.cloudServiceUnavailable');
    case 'unsupported_model':
      return t('errors.cloudUnsupportedModel');
    case 'bad_request':
      return t('errors.cloudBadRequest');
    case 'invalid_user_jwt':
      return t('errors.cloudSessionExpired');
    case 'bearer_token_required':
    case 'invalid_device_token':
    case 'device_organization_required':
    case 'org_id_required':
      return t('errors.cloudAuthRequired');
    case 'provider_unavailable':
      return t('errors.providerUnavailable');
    case 'internal_error':
    case 'parse_error':
      return t('errors.agentInternalError');
    default:
      return fallback || t('errors.agentGeneric');
  }
}

const NON_RETRYABLE_AGENT_CODES = new Set([
  'api_key_missing',
  'input_too_large',
  'no_project',
  'cloud_not_enrolled',
  'not_subscribed',
  'quota_exceeded',
  'cloud_unreachable',
  'unsupported_model',
  'bad_request',
  'invalid_user_jwt',
  'bearer_token_required',
  'invalid_device_token',
  'device_organization_required',
  'org_id_required',
  'confirmation_not_found',
]);

function isChatErrorRetryable(code: string): boolean {
  if (NON_RETRYABLE_AGENT_CODES.has(code)) return false;
  if (isNonRetryableCloudLlmCode(code)) return false;
  if (isMistralOutageCode(code)) return false;
  return true;
}

interface ChatCorrelationContext {
  turnId?: string | null;
  workId?: string | null;
  sessionId?: string | null;
  resolveSpecialistMeta?: (id: string) => SpecialistMeta | null;
}

function buildStreamChatError(
  data: ChatStreamErrorData,
  ctx?: ChatCorrelationContext,
): ChatError {
  return {
    code: data.code,
    message: data.message,
    detail: data.detail ?? null,
    retryable: isChatErrorRetryable(data.code),
    incidentId: data.incidentId ?? createIncidentId(),
    turnId: data.turnId ?? ctx?.turnId ?? null,
    workId: data.workId ?? ctx?.workId ?? null,
    sessionId: data.sessionId ?? ctx?.sessionId ?? null,
  };
}

function withChatCorrelation(
  err: Omit<ChatError, 'incidentId' | 'turnId' | 'workId' | 'sessionId'> &
    Partial<Pick<ChatError, 'incidentId' | 'turnId' | 'workId' | 'sessionId'>>,
  ctx?: ChatCorrelationContext,
): ChatError {
  return {
    ...err,
    incidentId: err.incidentId ?? createIncidentId(),
    turnId: err.turnId ?? ctx?.turnId ?? null,
    workId: err.workId ?? ctx?.workId ?? null,
    sessionId: err.sessionId ?? ctx?.sessionId ?? null,
  };
}

function isConfirmationNotFoundError(err: unknown): boolean {
  if (!(err instanceof SidecarHttpError)) return false;
  if (err.status === 404) return true;
  if (err.code === 'confirmation_not_found') return true;
  const normalized = err.message.toLowerCase();
  return (
    normalized.includes('confirmation') &&
    (normalized.includes('introuvable') ||
      normalized.includes('not found') ||
      normalized.includes('expired') ||
      normalized.includes('expir'))
  );
}

function chatErrorFromSidecarHttp(
  err: SidecarHttpError,
  ctx?: ChatCorrelationContext,
): ChatError {
  const rawCode = err.code ?? '';
  const code = err.code ? normalizeChatErrorCode(err.code) : 'sidecar_unreachable';
  if (code !== 'sidecar_unreachable' && code !== 'unknown') {
    return withChatCorrelation(
      {
        code,
        message: localizeAgentError(rawCode, err.message),
        retryable: isChatErrorRetryable(rawCode),
      },
      ctx,
    );
  }
  return withChatCorrelation(
    {
      code: 'sidecar_unreachable',
      message: t('errors.sidecarUnreachable', {
        detail: err.message
          ? t('errors.sidecarUnreachableDetail', { detail: err.message })
          : '',
      }),
      retryable: true,
    },
    ctx,
  );
}

function extractFilePathFromResult(result: unknown): string | undefined {
  if (!result || typeof result !== 'object') return undefined;
  const record = result as Record<string, unknown>;
  const metadata = record.metadata;
  if (metadata && typeof metadata === 'object') {
    const path = (metadata as Record<string, unknown>).path;
    if (typeof path === 'string' && path) return path;
  }
  if (typeof record.document_id === 'string' && record.document_id) {
    return record.document_id;
  }
  return undefined;
}

function extractSnapshotPathFromResult(result: unknown): string | undefined {
  if (!result || typeof result !== 'object') return undefined;
  const metadata = (result as Record<string, unknown>).metadata;
  if (!metadata || typeof metadata !== 'object') return undefined;
  const versionPath = (metadata as Record<string, unknown>).version_path;
  return typeof versionPath === 'string' && versionPath
    ? versionPath
    : undefined;
}

/** Finalise un tool interrompu (abort, timeout) avec un résultat synthétique. */
export function finalizeInterruptedTool(tool: ChatToolCall, reason: string): void {
  tool.status = 'error';
  if (tool.endedAt == null) {
    tool.endedAt = Date.now();
  }
  if (tool.result === undefined) {
    tool.result = { ok: false, error: 'interrupted', reason };
  }
}

const INTERRUPTIBLE_TOOL_STATUSES = new Set<ChatToolCall['status']>([
  'pending',
  'running',
  'pending_confirmation',
  'awaiting_confirmation',
]);

function shouldFinalizeIncompleteTool(tool: ChatToolCall): boolean {
  if (tool.result !== undefined) return false;
  if (tool.status === 'success') return false;
  return (
    !tool.status ||
    INTERRUPTIBLE_TOOL_STATUSES.has(tool.status) ||
    tool.status === 'error'
  );
}

/** Finalise les tools incomplets d'un message assistant et efface les human gates orphelines. */
export function finalizeIncompleteToolsOnMessage(
  message: ChatMessage,
  reason: string,
  humanSummary?: string,
): void {
  if (message.role !== 'assistant') return;

  for (const tool of message.toolCalls ?? []) {
    if (!shouldFinalizeIncompleteTool(tool)) continue;
    finalizeInterruptedTool(tool, reason);
    if (humanSummary != null) {
      tool.humanSummary = humanSummary;
    }
  }

  if (message.pendingConfirmation) {
    message.pendingConfirmation = null;
  }
  if (message.preparingConfirmation) {
    message.preparingConfirmation = null;
  }
  if (message.pendingPlan?.status === 'pending') {
    message.pendingPlan = null;
  }
  markRunningSpecialistHandoffAsError(message);
}

/** Efface les human gates orphelines après un abort utilisateur. */
export function clearHumanGatesOnAbort(messages: ChatMessage[]): void {
  const abortedSummary = t('errors.agentAborted');
  for (const message of messages) {
    if (message.role !== 'assistant') continue;
    finalizeIncompleteToolsOnMessage(message, 'aborted_by_user', abortedSummary);
  }
}

export function applyStreamEvent(
  messages: ChatMessage[],
  assistantMessageId: string,
  event: ChatStreamEvent,
  onConfirmationRequest?: () => void,
  ctx?: ChatCorrelationContext,
): void {
  const assistant = messages.find((m) => m.id === assistantMessageId);
  if (!assistant) return;

  switch (event.type) {
    case 'token': {
      if (routesToSpecialistHandoff(assistant, event.data.parentToolCallId)) {
        assistant.specialistHandoff = appendSpecialistHandoffToken(
          assistant.specialistHandoff!,
          event.data.token,
        );
        break;
      }
      appendTextToParts(assistant, event.data.token);
      syncContent(assistant);
      break;
    }
    case 'tool_call_start': {
      const startSummary = event.data.humanSummary?.trim() ?? '';
      const args = event.data.args ?? {};
      if (
        routesToSpecialistHandoff(assistant, event.data.parentToolCallId)
      ) {
        const handoff = assistant.specialistHandoff!;
        assistant.specialistHandoff = upsertSpecialistNestedTool(handoff, {
          id: event.data.id || createMessageId(),
          name: event.data.name || 'tool',
          humanSummary: startSummary || undefined,
          status: 'running',
        });
        break;
      }
      const fromArgs =
        isFileWriteTool(event.data.name || '')
          ? extractProposedPath(args)
          : null;
      const toolCall: ChatToolCall = {
        id: event.data.id || createMessageId(),
        name: event.data.name || 'tool',
        status: 'running',
        args,
        startedAt: Date.now(),
        filePath: event.data.filePath || fromArgs || undefined,
        humanSummary: startSummary || undefined,
      };
      assistant.toolCalls = [...(assistant.toolCalls ?? []), toolCall];
      const parts = assistant.parts ?? (assistant.parts = []);
      parts.push({
        type: 'tool_call',
        id: createPartId(),
        toolCallId: toolCall.id,
      });
      if (event.data.name === 'summon_specialist') {
        assistant.specialistHandoff = createRunningSpecialistHandoff(
          toolCall.id,
          args,
          ctx?.resolveSpecialistMeta,
        );
      } else if (event.data.name === 'ask_personas') {
        assistant.personasOpinion = initStreamingPersonasOpinion(
          String(args.question ?? ''),
        );
      }
      break;
    }
    case 'confirmation_preparing': {
      const toolId = event.data.toolCallId;
      if (
        assistant.specialistHandoff &&
        (assistant.specialistHandoff.status === 'running' ||
          assistant.specialistHandoff.streaming === true)
      ) {
        markSpecialistHandoffAsPending(assistant);
      }
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.status = 'pending_confirmation';
        if (tool.name === 'summon_specialist') {
          markSpecialistHandoffAsPending(assistant);
        }
      }
      assistant.preparingConfirmation = {
        toolCallId: toolId,
        toolName: event.data.toolName || undefined,
        connectorId: event.data.connectorId || undefined,
        action: event.data.action || undefined,
      };
      onConfirmationRequest?.();
      break;
    }
    case 'confirmation_request': {
      const toolId = event.data.toolCallId;
      if (
        assistant.specialistHandoff &&
        (assistant.specialistHandoff.status === 'running' ||
          assistant.specialistHandoff.streaming === true)
      ) {
        markSpecialistHandoffAsPending(assistant);
      }
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.status = 'awaiting_confirmation';
        if (!tool.filePath && event.data.proposedPath) {
          tool.filePath = event.data.proposedPath;
        }
        if (tool.name === 'summon_specialist') {
          markSpecialistHandoffAsPending(assistant);
        }
      }
      if (assistant.preparingConfirmation?.toolCallId === toolId) {
        assistant.preparingConfirmation = null;
      }
      const confirmation: ChatConfirmation = {
        confirmationId: event.data.confirmationId,
        toolCallId: toolId,
        toolName: event.data.toolName,
        action: event.data.action,
        proposedPath: event.data.proposedPath,
        humanSummary: event.data.humanSummary.trim(),
        turnId: event.data.turnId ?? null,
        effect: event.data.effect ?? null,
        targets: event.data.targets ?? [],
        headline: event.data.headline ?? '',
        protectionLabels: event.data.protectionLabels ?? [],
        trustKey: event.data.trustKey ?? null,
      };
      assistant.pendingConfirmation = confirmation;
      onConfirmationRequest?.();
      break;
    }
    case 'tool_auto_approved': {
      const toolId = event.data.toolCallId;
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        if (tool.status === 'pending_confirmation' || tool.status === 'awaiting_confirmation') {
          tool.status = 'running';
        }
        tool.autoApproved = true;
        if (tool.name === 'summon_specialist') {
          markSpecialistHandoffAsRunning(assistant);
        }
      }
      if (assistant.preparingConfirmation?.toolCallId === toolId) {
        assistant.preparingConfirmation = null;
      }
      if (assistant.pendingConfirmation?.toolCallId === toolId) {
        assistant.pendingConfirmation = null;
      }
      break;
    }
    case 'tool_call_result': {
      const toolId = event.data.id;
      if (
        routesToSpecialistHandoff(assistant, event.data.parentToolCallId)
      ) {
        const handoff = assistant.specialistHandoff!;
        const wasPending = handoff.status === 'pending';
        const resultSummary = event.data.humanSummary?.trim() ?? '';
        assistant.specialistHandoff = upsertSpecialistNestedTool(handoff, {
          id: toolId,
          name: event.data.name || 'tool',
          humanSummary: resultSummary || undefined,
          status:
            event.data.error != null || event.data.status === 'error'
              ? 'error'
              : 'success',
        });
        if (assistant.pendingConfirmation?.toolCallId === toolId) {
          assistant.pendingConfirmation = null;
        }
        if (assistant.preparingConfirmation?.toolCallId === toolId) {
          assistant.preparingConfirmation = null;
        }
        if (wasPending) {
          markSpecialistHandoffAsRunning(assistant);
        }
        break;
      }
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.result = event.data.result;
        tool.status =
          event.data.error != null ? 'error' : (event.data.status ?? 'success');
        tool.endedAt = Date.now();
        if (event.data.filePath) {
          tool.filePath = event.data.filePath;
        } else if (!tool.filePath) {
          const fromResult = extractFilePathFromResult(event.data.result);
          if (fromResult) tool.filePath = fromResult;
        }
        const snapshotPath = extractSnapshotPathFromResult(event.data.result);
        if (snapshotPath) {
          tool.snapshotPath = snapshotPath;
        }
        const resultSummary = event.data.humanSummary?.trim() ?? '';
        if (resultSummary) {
          tool.humanSummary = resultSummary;
        }
        if (assistant.pendingConfirmation?.toolCallId === toolId) {
          assistant.pendingConfirmation = null;
        }
        if (assistant.preparingConfirmation?.toolCallId === toolId) {
          assistant.preparingConfirmation = null;
        }
        if (tool.name === 'summon_specialist') {
          const resultPayload = event.data.result;
          const resultHasStructuredError =
            resultPayload != null &&
            typeof resultPayload === 'object' &&
            (resultPayload as Record<string, unknown>).error != null;
          const toolFailed =
            event.data.error != null || event.data.status === 'error';
          const handoff = toolResultToSpecialistHandoff(
            tool.id,
            tool.args ?? {},
            event.data.result,
            toolFailed && !resultHasStructuredError
              ? (event.data.error ?? event.data.result ?? true)
              : undefined,
            ctx?.resolveSpecialistMeta,
          );
          if (handoff) {
            const prev = assistant.specialistHandoff;
            const thinking = prev?.thinking ?? handoff.thinking;
            assistant.specialistHandoff = {
              ...handoff,
              id: prev?.id ?? handoff.id,
              thinking,
              thinkingDone: thinking
                ? true
                : (prev?.thinkingDone ?? handoff.thinkingDone),
              nestedTools: prev?.nestedTools ?? handoff.nestedTools,
              content:
                (handoff.content?.trim()
                  ? handoff.content
                  : prev?.content) ?? '',
            };
          } else {
            markRunningSpecialistHandoffAsError(assistant);
          }
        } else if (tool.name === 'ask_personas') {
          const toolFailed =
            event.data.error != null || event.data.status === 'error';
          if (toolFailed) {
            markPersonasOpinionAsError(assistant);
          } else {
            applyPersonasOpinionFromToolResult(
              assistant,
              tool.args ?? {},
              event.data.result,
            );
          }
        }
      }
      break;
    }
    case 'thinking_start': {
      const thinkingId = event.data.thinkingId;
      if (!thinkingId) break;
      if (
        routesToSpecialistHandoff(assistant, event.data.parentToolCallId)
      ) {
        const handoff = assistant.specialistHandoff!;
        assistant.specialistHandoff = {
          ...handoff,
          thinking: handoff.thinking ?? '',
          thinkingDone: false,
        };
        break;
      }
      const parts = assistant.parts ?? (assistant.parts = []);
      if (findThinkingPart(parts, thinkingId)) break;
      parts.push({
        type: 'thinking',
        id: createPartId(),
        thinkingId,
        content: '',
        done: false,
      });
      if (assistant.thinking == null) {
        assistant.thinking = '';
      }
      break;
    }
    case 'thinking_delta': {
      const thinkingId = event.data.thinkingId;
      const delta = event.data.content;
      if (!thinkingId || !delta) break;
      if (
        routesToSpecialistHandoff(assistant, event.data.parentToolCallId)
      ) {
        const handoff = assistant.specialistHandoff!;
        assistant.specialistHandoff = appendSpecialistHandoffThinking(
          handoff,
          delta,
        );
        break;
      }
      const parts = assistant.parts ?? (assistant.parts = []);
      let part = findThinkingPart(parts, thinkingId);
      // Défense : start manqué / thinkingId retardé → créer la part à la volée.
      if (!part) {
        part = {
          type: 'thinking',
          id: createPartId(),
          thinkingId,
          content: '',
          done: false,
        };
        parts.push(part);
      }
      part.content += delta;
      throttleThinkingSubject(assistantMessageId, thinkingId, part);
      assistant.thinking = (assistant.thinking ?? '') + delta;
      break;
    }
    case 'thinking_end': {
      const thinkingId = event.data.thinkingId;
      if (!thinkingId) break;
      if (
        routesToSpecialistHandoff(assistant, event.data.parentToolCallId)
      ) {
        const handoff = assistant.specialistHandoff!;
        assistant.specialistHandoff = endSpecialistHandoffThinking(handoff);
        break;
      }
      const parts = assistant.parts ?? (assistant.parts = []);
      let part = findThinkingPart(parts, thinkingId);
      if (!part) {
        const leftover = (assistant.thinking ?? '').trim();
        if (!leftover) break;
        part = {
          type: 'thinking',
          id: createPartId(),
          thinkingId,
          content: leftover,
          done: false,
        };
        parts.push(part);
      }
      clearThinkingSubjectThrottle(assistantMessageId, thinkingId);
      part.done = true;
      const doneSubject = deriveThinkingSubjectDone(part.content);
      if (doneSubject) part.subject = doneSubject;
      const summary = deriveThinkingSummary(part.content);
      if (summary) part.summary = summary;
      break;
    }
    case 'memory_citations': {
      if (event.data.citations.length) {
        assistant.memoryCitations = event.data.citations;
      }
      break;
    }
    case 'done': {
      assistant.streaming = false;
      const finalContent = event.data.content;
      // On ne remplace JAMAIS le contenu streamé : ce serait écraser le texte
      // produit avant les appels d'outil et casser le rendu interleaved. On
      // n'utilise done.content qu'en fallback quand rien n'a été streamé
      // (provider non streaming ou tour sans tokens).
      if (finalContent && !assistant.content) {
        const parts = assistant.parts ?? (assistant.parts = []);
        const firstText = parts.find(
          (p): p is { type: 'text'; id: string; content: string } =>
            p.type === 'text',
        );
        if (firstText) {
          firstText.content = finalContent;
        } else {
          parts.unshift({
            type: 'text',
            id: createPartId(),
            content: finalContent,
          });
        }
        syncContent(assistant);
      }
      break;
    }
    case 'error': {
      if (event.data.code === 'confirmation_timeout') {
        const pending = assistant.pendingConfirmation;
        if (pending) {
          const tool = assistant.toolCalls?.find((t) => t.id === pending.toolCallId);
          if (tool) {
            finalizeInterruptedTool(tool, 'confirmation_timeout');
            tool.humanSummary = localizeAgentError('confirmation_timeout', '');
          }
          assistant.pendingConfirmation = null;
        }
        if (assistant.preparingConfirmation) {
          assistant.preparingConfirmation = null;
        }
        markRunningSpecialistHandoffAsError(assistant);
        break;
      }
      if (event.data.code === 'plan_timeout') {
        if (assistant.pendingPlan) assistant.pendingPlan = null;
        break;
      }
      assistant.streaming = false;
      assistant.error = buildStreamChatError(event.data, ctx);
      break;
    }
    case 'plan_proposed': {
      const isReplan = Boolean(assistant.planSeenInTurn);
      assistant.planSeenInTurn = true;
      const plan: ChatProposedPlan = {
        planId: event.data.planId,
        steps: event.data.steps,
        rationale: event.data.rationale,
        status: 'pending',
        isReplan,
      };
      assistant.pendingPlan = plan;
      onConfirmationRequest?.();
      break;
    }
    default:
      break;
  }
}

async function consumeSseStream(
  response: Response,
  applyEvent: (event: ChatStreamEvent) => void,
  abortController: AbortController,
  idleState: { timedOut: boolean },
  idleControl: { isPaused: () => boolean },
  onAttachmentStatus?: (data: Record<string, unknown>) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error('Réponse streaming sans corps');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let idleTimer: ReturnType<typeof setTimeout> | null = null;

  const resetIdleTimer = (): void => {
    if (idleTimer) clearTimeout(idleTimer);
    if (idleControl.isPaused()) return;
    idleTimer = setTimeout(() => {
      idleState.timedOut = true;
      abortController.abort();
    }, IDLE_TIMEOUT_MS);
  };

  resetIdleTimer();

  try {
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch (err) {
        if (idleState.timedOut) throw new StreamIdleTimeoutError();
        throw err;
      }
      if (chunk.done) break;

      resetIdleTimer();
      buffer += decoder.decode(chunk.value, { stream: true });
      const { events, rest } = parseSseChunk(buffer);
      buffer = rest;

      for (const rawEvent of events) {
        if (rawEvent.type === 'attachment_status') {
          onAttachmentStatus?.(rawEvent.data);
          continue;
        }
        const mapped = mapPythonSseEvent(rawEvent);
        if (!mapped) continue;
        applyEvent(mapped);
        if (idleControl.isPaused()) {
          if (idleTimer) clearTimeout(idleTimer);
          idleTimer = null;
        } else {
          resetIdleTimer();
        }
      }
    }
  } finally {
    if (idleTimer) clearTimeout(idleTimer);
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

export interface UseChatStreamOptions {
  sessionId: Ref<string>;
  initialMessages?: ChatMessage[];
  projectPath?: Ref<string | null>;
  workspaceDataDir?: Ref<string | null>;
  workspaceTitle?: Ref<string | null>;
  documents?: Ref<LocalDocumentEntry[]>;
  uiMode?: Ref<UiMode | undefined>;
  /** Override du niveau de raisonnement pour la conversation active. */
  reasoningEffort?: Ref<ReasoningEffort | null | undefined>;
  /** Override du modèle pour la conversation active (persisté par session). */
  sessionModel?: Ref<string | null | undefined>;
  /** Callback outils personas après résultat (simulate_meeting ouverture vue). */
  onPersonasToolCall?: (
    toolName: 'ask_personas' | 'simulate_meeting' | 'summon_specialist',
    payload: { args: Record<string, unknown>; result: unknown; toolCallId?: string },
  ) => void;
  /** Callback outils browser après résultat. */
  onBrowserToolCall?: (
    toolName: BrowserAgentToolName,
    result: unknown,
  ) => void;
  /** Pilotage IA du navigateur en pause (bouton utilisateur). */
  browserPilotagePaused?: Ref<boolean>;
}

export { mergeLlmConfigsWithSessionReasoning } from '@utils/llmRouting';

export interface AttachmentStatusEntry {
  status_key: string;
  label_locale: string;
}

export interface UseChatStreamReturn {
  messages: Ref<ChatMessage[]>;
  streaming: Ref<boolean>;
  error: Ref<ChatError | null>;
  confirming: Ref<boolean>;
  approvingPlan: Ref<boolean>;
  lastUsage: Ref<ChatUsage>;
  completedTurns: Ref<number>;
  lastCompaction: Ref<ChatCompactionInfo | null>;
  attachmentStatuses: Ref<Record<string, AttachmentStatusEntry>>;
  streamCorrelation: Ref<StreamCorrelation>;
  send: (text: string, options?: Partial<SendMessagePayload>) => Promise<boolean>;
  confirm: (decision: 'approve' | 'deny' | 'approve_remaining') => Promise<void>;
  approvePlan: (approved: boolean) => Promise<void>;
  retry: () => Promise<void>;
  editAndResend: (userMessageId: string, newText: string) => Promise<void>;
  regenerateFrom: (assistantMessageId: string) => Promise<boolean>;
  abort: () => void;
  loadMessages: (items: ChatMessage[]) => void;
  reprocessAttachment: (
    attachmentId: string,
    meta: {
      fileName: string;
      mimeType: string;
      kind: import('#types').ChatAttachmentKind;
    },
  ) => Promise<void>;
}

/** Applique un event SSE `attachment_status` à la map réactive (testable). */
export function applyAttachmentStatusEvent(
  statuses: Record<string, AttachmentStatusEntry>,
  data: Record<string, unknown>,
): void {
  const attachmentId = String(data.attachment_id ?? '');
  const statusKey = String(data.status_key ?? '');
  const labelLocale = String(data.label_locale ?? '');
  if (!attachmentId || !statusKey) return;
  statuses[attachmentId] = {
    status_key: statusKey,
    label_locale: labelLocale || statusKey,
  };
}

/** Résout une dir plugin pour le tour agent (projet, personas ou browser). */
export async function resolveAgentPluginDataDir(
  activePluginIds: string[],
  getPluginDataDir: (id: string) => Promise<string | null>,
): Promise<string | null> {
  const priority = [PROJET_PLUGIN_ID, PERSONAS_PLUGIN_ID, BROWSER_PLUGIN_ID];
  for (const pluginId of priority) {
    if (!activePluginIds.includes(pluginId)) continue;
    const dir = await getPluginDataDir(pluginId);
    if (dir) return dir;
  }
  return null;
}

/** SSE via sidecar Python local (application bureau). */
export function useChatStream(
  options: UseChatStreamOptions,
): UseChatStreamReturn {
  const {
    locale,
    settingsLocked,
    permissionsNetwork,
    confirmBeforeWriteEffective,
    codeExecute,
    auditEnabled,
  } = useAppSettings();
  const { activePluginIds, getPluginDataDir } = usePlugins();
  const { findPersona, refresh: refreshPersonasCatalog } = usePersonas();
  const { providerReadiness, init: initCloud, refreshQuota } = useCloud();
  // ref (profond) : les objets messages sont réactifs, donc muter
  // `assistant.content` déclenche directement le rendu. Pas de clonage du
  // tableau à chaque token.
  const messages = ref<ChatMessage[]>(options.initialMessages ?? []);
  const streaming = ref(false);
  const error = ref<ChatError | null>(null);
  const confirming = ref(false);
  const approvingPlan = ref(false);
  const lastUsage = ref<ChatUsage>({
    inputTokens: null,
    outputTokens: null,
    totalTokens: null,
  });
  const completedTurns = ref(0);
  const lastCompaction = ref<ChatCompactionInfo | null>(null);
  const attachmentStatuses = ref<Record<string, AttachmentStatusEntry>>({});
  const streamCorrelation = ref<StreamCorrelation>({
    turnId: null,
    workId: null,
  });

  let abortController: AbortController | null = null;
  let currentAssistantId: string | null = null;
  let pendingTokens = '';
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let lastUserText = '';
  let lastPayload: Partial<SendMessagePayload> = {};
  let lastRegenerateUserId: string | null = null;
  let idlePaused = false;
  // Identifiant de tour fourni par le backend (event turn_start). Utilisé pour
  // isoler la résolution d'une confirmation parmi plusieurs tours concurrents.
  let currentTurnId: string | null = null;
  let currentWorkId: string | null = null;
  let fallbackNotifiedTurnId: string | null = null;
  // confirmation_id déjà accepté par POST /agent/confirm (filet anti-reclic).
  let submittedConfirmationId: string | null = null;

  function releaseConfirmingIfNoPendingGate(): void {
    const hasPendingConfirmation = messages.value.some((m) => m.pendingConfirmation);
    if (!hasPendingConfirmation) {
      confirming.value = false;
      submittedConfirmationId = null;
    }
  }

  function correlationContext(): ChatCorrelationContext {
    return {
      turnId: currentTurnId,
      workId: currentWorkId,
      sessionId: options.sessionId.value,
      resolveSpecialistMeta: (id: string): SpecialistMeta | null => {
        const persona = findPersona(id);
        if (!persona) return null;
        return {
          name: persona.name,
          avatarColor: persona.avatar_color,
          avatarIcon: persona.avatar_icon,
        };
      },
    };
  }

  function setIdlePaused(paused: boolean): void {
    idlePaused = paused;
  }

  function flushPendingTokens(): void {
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    if (!pendingTokens || !currentAssistantId) return;
    const assistant = messages.value.find((m) => m.id === currentAssistantId);
    if (assistant && assistant.streaming) {
      appendTextToParts(assistant, pendingTokens);
      syncContent(assistant);
    }
    pendingTokens = '';
  }

  function scheduleFlush(): void {
    if (flushTimer) return;
    flushTimer = setTimeout(flushPendingTokens, FLUSH_THROTTLE_MS);
  }

  function syncStreamCorrelation(): void {
    streamCorrelation.value = {
      turnId: currentTurnId,
      workId: currentWorkId,
    };
    if (import.meta.env.DEV && (currentTurnId || currentWorkId)) {
      console.debug('[useChatStream] correlation', streamCorrelation.value);
    }
  }

  function applyEvent(event: ChatStreamEvent): void {
    if (event.type === 'work_started') {
      currentWorkId = event.data.workId || currentWorkId;
      syncStreamCorrelation();
      return;
    }
    if (event.type === 'work_terminal') {
      currentWorkId = null;
      syncStreamCorrelation();
      return;
    }
    if (event.type === 'compaction') {
      applyCompactionToMessages(messages.value, event.data);
      lastCompaction.value = compactionInfoFromEvent(event.data);
      return;
    }
    if (event.type === 'fallback') {
      const turnId = event.data.turnId || currentTurnId;
      if (turnId && turnId !== fallbackNotifiedTurnId) {
        fallbackNotifiedTurnId = turnId;
        notifyProviderFallback(event.data);
      }
      return;
    }
    if (event.type === 'turn_start') {
      if (event.data.turnId) currentTurnId = event.data.turnId;
      currentWorkId = event.data.turnId || currentWorkId;
      fallbackNotifiedTurnId = null;
      syncStreamCorrelation();
      return;
    }
    if (!currentAssistantId) return;
    if (event.type === 'token') {
      if (event.data.parentToolCallId) {
        flushPendingTokens();
        const assistant = messages.value.find((m) => m.id === currentAssistantId);
        if (
          assistant?.specialistHandoff &&
          assistant.specialistHandoff.toolCallId === event.data.parentToolCallId
        ) {
          assistant.specialistHandoff = appendSpecialistHandoffToken(
            assistant.specialistHandoff,
            event.data.token,
          );
          return;
        }
      }
      pendingTokens += event.data.token;
      scheduleFlush();
      return;
    }
    // Non-token : on commit d'abord les tokens en attente, puis on applique.
    flushPendingTokens();
    if (event.type === 'tool_call_result') {
      const toolName = event.data.name;
      if (toolName === 'simulate_meeting') {
        const tool = messages.value
          .find((m) => m.id === currentAssistantId)
          ?.toolCalls?.find((t) => t.id === event.data.id);
        options.onPersonasToolCall?.(toolName, {
          args: tool?.args ?? {},
          result: event.data.result,
          toolCallId: event.data.id,
        });
      }
      if (isBrowserAgentTool(toolName) && event.data.error == null && event.data.status !== 'error') {
        options.onBrowserToolCall?.(toolName, event.data.result);
      }
    }
    if (event.type === 'done') {
      lastUsage.value = {
        inputTokens: parseOptionalInt(event.data.input_tokens),
        outputTokens: parseOptionalInt(event.data.output_tokens),
        totalTokens: parseOptionalInt(event.data.total_tokens),
      };
      completedTurns.value += 1;
      const active = buildActiveProviderSet(
        options.sessionModel?.value ?? null,
        options.reasoningEffort?.value ?? null,
      );
      if (active && usesDeviceBearerAuth(active)) {
        void refreshQuota();
      }
    }
    applyStreamEvent(
      messages.value,
      currentAssistantId,
      event,
      () => {
        setIdlePaused(true);
      },
      correlationContext(),
    );
    releaseConfirmingIfNoPendingGate();
    if (
      event.type === 'error' &&
      (event.data.code === 'confirmation_timeout' ||
        event.data.code === 'plan_timeout')
    ) {
      setIdlePaused(false);
    }
    if (event.type === 'tool_call_result') {
      setIdlePaused(false);
      if (
        event.data.name === 'sync_managed_regards' &&
        event.data.error == null &&
        event.data.status !== 'error'
      ) {
        void (async () => {
          const personasDir = await getPluginDataDir(PERSONAS_PLUGIN_ID);
          if (personasDir) {
            await refreshPersonasCatalog(personasDir);
          }
        })();
      }
    }
  }

  function hasActiveHumanGate(): boolean {
    if (confirming.value || approvingPlan.value) return true;
    return messages.value.some(
      (m) =>
        m.pendingConfirmation ||
        m.pendingPlan?.status === 'pending',
    );
  }

  function loadMessages(items: ChatMessage[]): void {
    flushPendingTokens();
    clearAllThinkingSubjectThrottles();
    currentAssistantId = null;
    currentTurnId = null;
    currentWorkId = null;
    syncStreamCorrelation();
    fallbackNotifiedTurnId = null;
    error.value = null;
    streaming.value = false;
    lastUserText = '';
    lastPayload = {};
    lastRegenerateUserId = null;
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    pendingTokens = '';
    // Normalise les messages sans `parts` (vieilles sessions) pour un rendu
    // uniforme : texte puis outils. Les messages déjà munis de parts gardent
    // leur ordre interleaved.
    messages.value = items.map((m) => {
      const withParts = m.parts?.length ? m : { ...m, parts: buildLegacyParts(m) };
      for (const part of withParts.parts ?? []) {
        if (part.type === 'thinking') {
          enrichThinkingPresentation(part);
        }
      }
      rehydratePerspectiveCards(withParts, correlationContext());
      return withParts;
    });
    lastUsage.value = {
      inputTokens: null,
      outputTokens: null,
      totalTokens: null,
    };
    completedTurns.value = 0;
    lastCompaction.value = null;
    attachmentStatuses.value = {};
  }

  function resetStreamingFlag(): void {
    if (!currentAssistantId) return;
    const assistant = messages.value.find((m) => m.id === currentAssistantId);
    if (assistant?.streaming) assistant.streaming = false;
  }

  function abort(): void {
    // Abort utilisateur (navigation, stop). Marqué non-idle : silencieux.
    setIdlePaused(false);
    abortController?.abort();
    abortController = null;
    flushPendingTokens();
    clearAllThinkingSubjectThrottles();
    resetStreamingFlag();
    clearHumanGatesOnAbort(messages.value);
    releaseConfirmingIfNoPendingGate();
    currentAssistantId = null;
    currentTurnId = null;
    currentWorkId = null;
    syncStreamCorrelation();
    fallbackNotifiedTurnId = null;
    streaming.value = false;
  }

  async function send(
    text: string,
    payload: Partial<SendMessagePayload> = {},
  ): Promise<boolean> {
    const trimmed = text.trim();
    if (!trimmed || streaming.value || hasActiveHumanGate()) return false;

    const projectPath = options.projectPath?.value;
    if (!projectPath) {
      error.value = withChatCorrelation(
        {
          code: 'no_project',
          message: t('errors.noSpaceOpen'),
          retryable: false,
        },
        correlationContext(),
      );
      return false;
    }

    const providerSet = buildActiveProviderSet(
      options.sessionModel?.value ?? null,
      options.reasoningEffort?.value ?? null,
    );
    if (providerSet) {
      if (usesDeviceBearerAuth(providerSet) && !providerReadiness.value) {
        await initCloud();
      }
      const cloudCtx = usesDeviceBearerAuth(providerSet)
        ? providerReadiness.value
        : null;
      const readiness = validateProviderSetChatReady(providerSet, cloudCtx);
      if (!readiness.ok) {
        ensureProviderSetChatReady(providerSet, cloudCtx);
        error.value = withChatCorrelation(
          {
            code: chatErrorCodeForReadiness(readiness.reason),
            message: chatErrorMessageForReadiness(readiness.reason),
            retryable: false,
          },
          correlationContext(),
        );
        return false;
      }
    } else {
      const legacyChat = buildActiveLlmConfigs().chat;
      if (!legacyChat) {
        error.value = withChatCorrelation(
          {
            code: 'no_model',
            message: t('chat.page.noModelConfigured'),
            retryable: false,
          },
          correlationContext(),
        );
        return false;
      }
    }

    error.value = null;
    setIdlePaused(false);
    lastUserText = trimmed;

    const sentAttachments = payload.attachments ?? [];
    const regenerateUserId = payload.regenerateFromUserId?.trim() || null;

    lastPayload = {
      attachments: payload.attachments,
      parentId: payload.parentId,
    };

    let userMessage: ChatMessage;
    if (regenerateUserId) {
      const existing = messages.value.find((m) => m.id === regenerateUserId);
      if (!existing || existing.role !== 'user') {
        return false;
      }
      userMessage = existing;
      lastRegenerateUserId = regenerateUserId;
    } else {
      lastRegenerateUserId = null;
      userMessage = {
        id: createMessageId(),
        role: 'user',
        content: trimmed,
        parentId: payload.parentId ?? null,
        createdAt: new Date().toISOString(),
      };
      if (sentAttachments.length) {
        userMessage.attachments = sentAttachments.map((a) => ({
          id: a.id,
          fileName: a.fileName,
          mimeType: a.mimeType,
          sizeBytes: a.sizeBytes,
          kind: a.kind,
          status: a.status,
          ...(a.error ? { error: a.error } : {}),
          ...(a.contentBase64 ? { contentBase64: a.contentBase64 } : {}),
        }));
      }
      messages.value.push(userMessage);
    }

    const assistantMessage: ChatMessage = {
      id: createMessageId(),
      role: 'assistant',
      content: '',
      streaming: true,
      toolCalls: [],
      parts: [{ type: 'text', id: createPartId(), content: '' }],
      parentId: userMessage.id,
      createdAt: new Date().toISOString(),
    };

    messages.value.push(assistantMessage);

    streaming.value = true;

    abortController = new AbortController();
    currentAssistantId = assistantMessage.id;
    currentTurnId = null;
    currentWorkId = null;
    syncStreamCorrelation();
    fallbackNotifiedTurnId = null;
    pendingTokens = '';
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    const idleState = { timedOut: false };

    try {
      const history = messages.value.filter(
        (m) => m.id !== userMessage.id && m.id !== assistantMessage.id,
      );
      const documents = options.documents?.value ?? [];
      const llmConfigs = mergeLlmConfigsWithSessionReasoning(
        buildActiveLlmConfigs(),
        options.reasoningEffort?.value ?? null,
        options.sessionModel?.value ?? null,
        providerSet,
      );
      const chatConfig = llmConfigs.chat;
      const contextWindow = providerSet
        ? contextWindowForSet(providerSet, chatConfig?.model)
        : chatConfig
          ? contextWindowFor(
              chatConfig.provider as LlmProviderName,
              chatConfig.model,
            )
          : null;
      const pluginDataDir = await resolveAgentPluginDataDir(
        activePluginIds.value,
        getPluginDataDir,
      );
      const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
      const body = buildAgentTurnPayload(
        options.sessionId.value,
        projectPath,
        trimmed,
        history,
        documents,
        options.workspaceDataDir?.value,
        options.workspaceTitle?.value ?? null,
        llmConfigs,
        options.uiMode?.value,
        contextWindow,
        true,
        sentAttachments,
        locale.value,
        providerSet,
        activePluginIds.value,
        pluginDataDir,
        buildSidecarSecurityContext(
          settingsLocked.value,
          permissionsNetwork.value,
          locale.value,
          codeExecute.value,
          auditEnabled.value,
        ),
        options.browserPilotagePaused?.value ?? false,
        confirmBeforeWriteEffective.value,
        cloudPluginDataDir,
      );

      const workspaceDataDir = options.workspaceDataDir?.value;
      if (workspaceDataDir) {
        await Promise.all(
          sentAttachments
            .filter((att) => att.contentBase64 && att.status === 'ready')
            .map((att) =>
              callReprocessAttachment({
                workspaceDataDir,
                projectPath,
                attachmentId: att.id,
                filePath: chatAttachmentRelativePath(
                  options.sessionId.value,
                  att.id,
                  att.fileName,
                ),
                mimeType: att.mimeType,
                contentBase64: att.contentBase64,
                persistOnly: true,
              }),
            ),
        );
      }

      const response = await fetch(`${getAiSidecarUrl()}/agent/turn`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'X-Internal-Secret': getDesktopSecret(),
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw await SidecarHttpError.fromResponse(response);
      }

      await consumeSseStream(
        response,
        applyEvent,
        abortController,
        idleState,
        {
          isPaused: () => idlePaused,
        },
        (data) => {
          applyAttachmentStatusEvent(attachmentStatuses.value, data);
        },
      );
    } catch (err) {
      const name = (err as Error)?.name;

      if (name === 'StreamIdleTimeoutError') {
        const chatError = withChatCorrelation(
          {
            code: 'idle_timeout',
            message: t('errors.idleTimeout'),
            retryable: true,
          },
          correlationContext(),
        );
        const idleSummary = localizeAgentError('idle_timeout', '');
        for (const message of messages.value) {
          if (message.role !== 'assistant') continue;
          finalizeIncompleteToolsOnMessage(message, 'idle_timeout', idleSummary);
        }
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        } else {
          error.value = chatError;
        }
      } else if (name === 'AbortError') {
        // Abort utilisateur (stop / navigation) ou gate morte (confirm 404) :
        // silencieux. On conserve error.value terminal déjà posé (ex.
        // confirmation_not_found) et le contenu partiel streamé.
      } else if (
        error.value &&
        error.value.retryable === false &&
        error.value.code === 'confirmation_not_found'
      ) {
        // Erreur terminale déjà exposée par confirm() : ne pas l'écraser.
      } else if (err instanceof SidecarHttpError) {
        const chatError = chatErrorFromSidecarHttp(err, correlationContext());
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        } else {
          error.value = chatError;
        }
      } else {
        const detail = err instanceof Error ? err.message : '';
        const chatError = withChatCorrelation(
          {
            code: 'sidecar_unreachable',
            message: t('errors.sidecarUnreachable', {
              detail: detail ? t('errors.sidecarUnreachableDetail', { detail }) : '',
            }),
            retryable: true,
          },
          correlationContext(),
        );
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        } else {
          error.value = chatError;
        }
      }
    } finally {
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      flushPendingTokens();
      resetStreamingFlag();
      // Fin de SSE = gate backend morte : nettoyer toute confirmation orpheline,
      // même si idle était en pause (coupure pendant une attente humaine).
      const streamEndedSummary = localizeAgentError('stream_ended', '');
      for (const message of messages.value) {
        if (message.role !== 'assistant') continue;
        if (
          message.pendingConfirmation ||
          message.preparingConfirmation ||
          message.pendingPlan?.status === 'pending'
        ) {
          finalizeIncompleteToolsOnMessage(message, 'stream_ended', streamEndedSummary);
        }
      }
      releaseConfirmingIfNoPendingGate();
      setIdlePaused(false);
      currentAssistantId = null;
      streaming.value = false;
      abortController = null;
    }
    return true;
  }

  function findMessageIndex(messageId: string): number {
    return messages.value.findIndex((m) => m.id === messageId);
  }

  function attachmentsFromUserMessage(
    userMessage: ChatMessage,
  ): SendMessagePayload['attachments'] {
    if (!userMessage.attachments?.length) return undefined;
    return userMessage.attachments.map((a) => ({
      id: a.id,
      fileName: a.fileName,
      mimeType: a.mimeType,
      sizeBytes: a.sizeBytes,
      kind: a.kind,
      status: a.status,
      ...(a.error ? { error: a.error } : {}),
      ...(a.contentBase64 ? { contentBase64: a.contentBase64 } : {}),
    }));
  }

  async function retry(): Promise<void> {
    if (!lastUserText || streaming.value) return;
    const msgs = messages.value;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs.splice(i, 1);
        break;
      }
    }
    if (lastRegenerateUserId) {
      await send(lastUserText, {
        regenerateFromUserId: lastRegenerateUserId,
        attachments: lastPayload.attachments,
      });
      return;
    }
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        msgs.splice(i, 1);
        break;
      }
    }
    await send(lastUserText, lastPayload);
  }

  async function editAndResend(
    userMessageId: string,
    newText: string,
  ): Promise<void> {
    const trimmed = newText.trim();
    if (!trimmed || streaming.value || hasActiveHumanGate()) return;

    const idx = findMessageIndex(userMessageId);
    if (idx < 0) return;

    const userMessage = messages.value[idx];
    if (userMessage.role !== 'user' || userMessage.messageKind === 'compaction') {
      return;
    }

    error.value = null;
    messages.value.splice(idx);
    const attachments = attachmentsFromUserMessage(userMessage);
    await send(trimmed, attachments ? { attachments } : {});
  }

  async function regenerateFrom(assistantMessageId: string): Promise<boolean> {
    if (streaming.value || hasActiveHumanGate()) return false;

    const idx = findMessageIndex(assistantMessageId);
    if (idx < 0) return false;

    const assistant = messages.value[idx];
    if (assistant.role !== 'assistant') return false;
    if (assistant.streaming) return false;
    if (assistant.pendingConfirmation) return false;
    if (assistant.pendingPlan?.status === 'pending') return false;

    let userIdx = idx - 1;
    if (assistant.parentId) {
      const parentIdx = findMessageIndex(assistant.parentId);
      if (parentIdx >= 0) userIdx = parentIdx;
    }

    const userMessage = messages.value[userIdx];
    if (!userMessage || userMessage.role !== 'user') return false;

    const userText = userMessage.content.trim();
    if (!userText) return false;

    error.value = null;
    const removed = messages.value.splice(idx);
    const attachments = attachmentsFromUserMessage(userMessage);
    const started = await send(userText, {
      regenerateFromUserId: userMessage.id,
      ...(attachments ? { attachments } : {}),
    });
    if (!started) {
      messages.value.splice(idx, 0, ...removed);
      return false;
    }
    return true;
  }

  async function confirm(decision: 'approve' | 'deny' | 'approve_remaining'): Promise<void> {
    const assistant = messages.value.find((m) => m.pendingConfirmation);
    const pending = assistant?.pendingConfirmation;
    if (!pending || confirming.value) return;
    if (submittedConfirmationId === pending.confirmationId) return;

    confirming.value = true;
    error.value = null;

    // turn_id (préférence : celui attaché à la confirmation, sinon le tour
    // courant) pour une résolution isolée côté backend.
    const turnId = pending.turnId ?? currentTurnId ?? null;

    try {
      const response = await fetch(`${getAiSidecarUrl()}/agent/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Internal-Secret': getDesktopSecret(),
        },
        body: JSON.stringify({
          session_id: options.sessionId.value,
          confirmation_id: pending.confirmationId,
          decision,
          locale: locale.value,
          ...(turnId ? { turn_id: turnId } : {}),
        }),
      });
      if (!response.ok) {
        throw await SidecarHttpError.fromResponse(response);
      }
      submittedConfirmationId = pending.confirmationId;
      if (assistant && decision !== 'deny') {
        const tool = assistant.toolCalls?.find((t) => t.id === pending.toolCallId);
        if (
          tool &&
          (tool.status === 'pending_confirmation' || tool.status === 'awaiting_confirmation')
        ) {
          tool.status = 'running';
        }
        const handoff = assistant.specialistHandoff;
        const nestedTool = handoff?.nestedTools?.find((entry) => entry.id === pending.toolCallId);
        if (nestedTool && handoff) {
          assistant.specialistHandoff = upsertSpecialistNestedTool(handoff, {
            ...nestedTool,
            status: 'running',
          });
        }
        const nestedMatch = assistant.specialistHandoff?.nestedTools?.some(
          (entry) => entry.id === pending.toolCallId,
        );
        // Reprendre le handoff après approve : summon lui-même, tool nested,
        // ou confirmation orpheline pendant un handoff pending.
        if (
          tool?.name === 'summon_specialist' ||
          nestedMatch ||
          assistant.specialistHandoff?.status === 'pending'
        ) {
          markSpecialistHandoffAsRunning(assistant);
        }
      }
      // Succès POST : confirming reste true jusqu'à disparition de pendingConfirmation (SSE).
    } catch (err) {
      confirming.value = false;
      submittedConfirmationId = null;
      const ctx = correlationContext();
      if (isConfirmationNotFoundError(err)) {
        const detail =
          err instanceof SidecarHttpError ? err.message : err instanceof Error ? err.message : '';
        const summary = localizeAgentError('confirmation_not_found', detail);
        if (assistant) {
          finalizeIncompleteToolsOnMessage(assistant, 'confirmation_not_found', summary);
        }
        releaseConfirmingIfNoPendingGate();
        error.value = withChatCorrelation(
          {
            code: 'confirmation_not_found',
            message: summary,
            retryable: false,
          },
          ctx,
        );
        // Gate morte côté backend : couper le SSE pour éviter des events
        // contradictoires (ex. confirmation_timeout) après l'erreur terminale.
        setIdlePaused(false);
        abortController?.abort();
        abortController = null;
      } else if (err instanceof SidecarHttpError && err.code) {
        error.value = chatErrorFromSidecarHttp(err, ctx);
      } else {
        const detail = err instanceof Error ? err.message : '';
        error.value = withChatCorrelation(
          {
            code: 'confirm_failed',
            message: t('errors.confirmFailed', {
              detail: detail ? t('errors.confirmFailedDetail', { detail }) : '',
            }),
            retryable: true,
          },
          ctx,
        );
      }
    }
  }

  async function reprocessAttachment(
    attachmentId: string,
    meta: {
      fileName: string;
      mimeType: string;
      kind: import('#types').ChatAttachmentKind;
    },
  ): Promise<void> {
    const projectPath = options.projectPath?.value;
    const workspaceDataDir = options.workspaceDataDir?.value;
    if (!projectPath || !workspaceDataDir) {
      throw new Error(t('errors.noSpaceOpen'));
    }

    const providerSet = buildActiveProviderSet(
      options.sessionModel?.value ?? null,
      options.reasoningEffort?.value ?? null,
    );
    if (providerSet) {
      if (usesDeviceBearerAuth(providerSet) && !providerReadiness.value) {
        await initCloud();
      }
      const cloudCtx = usesDeviceBearerAuth(providerSet)
        ? providerReadiness.value
        : null;
      const readiness = validateProviderSetChatReady(providerSet, cloudCtx);
      if (!readiness.ok) {
        ensureProviderSetChatReady(providerSet, cloudCtx);
        throw new Error(chatErrorMessageForReadiness(readiness.reason));
      }
    }

    const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    const pluginDataDir = await resolveAgentPluginDataDir(
      activePluginIds.value,
      getPluginDataDir,
    );
    const result = await callReprocessAttachment({
      workspaceDataDir,
      projectPath,
      attachmentId,
      filePath: chatAttachmentRelativePath(
        options.sessionId.value,
        attachmentId,
        meta.fileName,
      ),
      mimeType: meta.mimeType,
      providerSet,
      locale: locale.value,
      cloudPluginDataDir,
      pluginDataDir,
    });

    applyAttachmentStatusEvent(attachmentStatuses.value, {
      attachment_id: attachmentId,
      status_key: result.status_key,
      label_locale: result.label_locale,
    });
  }

  async function approvePlan(approved: boolean): Promise<void> {
    const assistant = messages.value.find((m) => m.pendingPlan?.status === 'pending');
    const plan = assistant?.pendingPlan;
    if (!plan || approvingPlan.value) return;

    approvingPlan.value = true;
    error.value = null;

    try {
      const ok = await approveAgentPlan({
        session_id: options.sessionId.value,
        plan_id: plan.planId,
        approved,
        locale: locale.value,
        ...(currentTurnId ? { turn_id: currentTurnId } : {}),
      });
      if (!ok) {
        throw new Error('plan_approve_failed');
      }
      plan.status = approved ? 'approved' : 'rejected';
      assistant!.pendingPlan = null;
      setIdlePaused(false);
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      error.value = withChatCorrelation(
        {
          code: 'confirm_failed',
          message: t('errors.confirmFailed', {
            detail: detail ? t('errors.confirmFailedDetail', { detail }) : '',
          }),
          retryable: true,
        },
        correlationContext(),
      );
    } finally {
      approvingPlan.value = false;
    }
  }

  return {
    messages,
    streaming,
    error,
    confirming,
    approvingPlan,
    lastUsage,
    completedTurns,
    lastCompaction,
    attachmentStatuses,
    streamCorrelation,
    send,
    confirm,
    approvePlan,
    retry,
    editAndResend,
    regenerateFrom,
    abort,
    loadMessages,
    reprocessAttachment,
  };
}
