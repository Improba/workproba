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
  ChatStreamCompactionData,
  ChatStreamEvent,
  ChatStreamFallbackData,
  ChatToolCall,
  ChatUsage,
  RawChatStreamEvent,
  ReasoningEffort,
  SendMessagePayload,
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
  usePlugins,
} from '@composables/usePlugins';
import type { LlmProviderName } from '@composables/useDesktop.types';
import { mergeLlmConfigsWithSessionReasoning } from '@utils/llmRouting';
import { isBrowserAgentTool, type BrowserAgentToolName } from '@utils/browserTools';
import { ensureProviderSetChatReady } from '@utils/providerSetNotify';
import { contextWindowFor } from '@utils/modelCatalog';
import { t } from '@utils/i18nT';

/** Délai sans aucune donnée SSE avant de déclarer le stream mort (ms). */
const IDLE_TIMEOUT_MS = 30_000;
/** Intervalle de regroupement des tokens avant mutation réactive (ms). */
const FLUSH_THROTTLE_MS = 50;

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

/** Mappe un event SSE Python vers le format interne du front (testable). */
export function mapPythonSseEvent(
  event: RawChatStreamEvent,
): ChatStreamEvent | null {
  const data = event.data;

  switch (event.type) {
    case 'turn_start':
      return {
        type: 'turn_start',
        data: { turnId: String(data.turn_id ?? '') },
      };
    case 'token':
      return {
        type: 'token',
        data: { token: String(data.content ?? data.token ?? '') },
      };
    case 'tool_call_start':
      return {
        type: 'tool_call_start',
        data: {
          id: String(data.tool_call_id ?? data.id ?? ''),
          name: String(data.tool_name ?? data.name ?? 'tool'),
          args: (data.arguments ?? data.args ?? {}) as Record<string, unknown>,
          humanSummary: extractHumanSummary(data),
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
        },
      };
    }
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
          effect: data.effect ?? null,
          targets: Array.isArray(data.targets) ? data.targets : [],
          headline: String(data.headline ?? ''),
          protectionLabels: Array.isArray(data.protection_labels)
            ? data.protection_labels.map(String)
            : Array.isArray(data.protectionLabels)
              ? data.protectionLabels.map(String)
              : [],
        },
      };
    case 'thinking_start':
      return {
        type: 'thinking_start',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
        },
      };
    case 'thinking_delta':
      return {
        type: 'thinking_delta',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
          content: String(data.content ?? ''),
        },
      };
    case 'thinking_end':
      return {
        type: 'thinking_end',
        data: {
          thinkingId: String(data.thinking_id ?? ''),
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
    case 'error':
      return {
        type: 'error',
        data: {
          code: normalizeChatErrorCode(String(data.code ?? 'agent_error')),
          message: localizeAgentError(
            String(data.code ?? 'agent_error'),
            String(data.message ?? ''),
          ),
        },
      };
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
    case 'work_contribution':
    case 'work_completed':
    case 'work_failed':
      if (import.meta.env.DEV) {
        console.debug('[useChatStream] ignoring work event', event.type);
      }
      return null;
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

/** Reconstruit des `parts` ordonnées pour un message legacy sans parts. */
function buildLegacyParts(message: ChatMessage): ChatMessagePart[] {
  const parts: ChatMessagePart[] = [];
  if (message.thinking) {
    parts.push({
      type: 'thinking',
      id: `${message.id}__thinking`,
      thinkingId: 'think-0',
      content: message.thinking,
      done: true,
    });
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
    case 'usage_limit_exceeded':
      return t('errors.agentUsageLimit');
    case 'turn_in_progress':
      return t('errors.agentTurnInProgress');
    case 'input_too_large':
      return t('errors.agentInputTooLarge');
    case 'api_key_missing':
      return t('errors.apiKeyMissing');
    case 'internal_error':
    case 'parse_error':
      return t('errors.agentInternalError');
    default:
      return fallback || t('errors.agentGeneric');
  }
}

const NON_RETRYABLE_AGENT_CODES = new Set(['api_key_missing', 'input_too_large', 'no_project']);

function chatErrorFromSidecarHttp(err: SidecarHttpError): ChatError {
  const code = err.code ? normalizeChatErrorCode(err.code) : 'sidecar_unreachable';
  if (code !== 'sidecar_unreachable' && code !== 'unknown') {
    return {
      code,
      message: localizeAgentError(err.code!, err.message),
      retryable: !NON_RETRYABLE_AGENT_CODES.has(err.code!),
    };
  }
  return {
    code: 'sidecar_unreachable',
    message: t('errors.sidecarUnreachable', {
      detail: err.message
        ? t('errors.sidecarUnreachableDetail', { detail: err.message })
        : '',
    }),
    retryable: true,
  };
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

export function applyStreamEvent(
  messages: ChatMessage[],
  assistantMessageId: string,
  event: ChatStreamEvent,
  onConfirmationRequest?: () => void,
): void {
  const assistant = messages.find((m) => m.id === assistantMessageId);
  if (!assistant) return;

  switch (event.type) {
    case 'tool_call_start': {
      const startSummary = event.data.humanSummary?.trim() ?? '';
      const toolCall: ChatToolCall = {
        id: event.data.id || createMessageId(),
        name: event.data.name || 'tool',
        status: 'running',
        args: event.data.args ?? {},
        startedAt: Date.now(),
        filePath: event.data.filePath,
        humanSummary: startSummary || undefined,
      };
      assistant.toolCalls = [...(assistant.toolCalls ?? []), toolCall];
      const parts = assistant.parts ?? (assistant.parts = []);
      parts.push({
        type: 'tool_call',
        id: createPartId(),
        toolCallId: toolCall.id,
      });
      break;
    }
    case 'confirmation_request': {
      const toolId = event.data.toolCallId;
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.status = 'awaiting_confirmation';
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
      };
      assistant.pendingConfirmation = confirmation;
      onConfirmationRequest?.();
      break;
    }
    case 'tool_call_result': {
      const toolId = event.data.id;
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
      }
      break;
    }
    case 'thinking_start': {
      const thinkingId = event.data.thinkingId;
      if (!thinkingId) break;
      const parts = assistant.parts ?? (assistant.parts = []);
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
      const parts = assistant.parts ?? [];
      const part = [...parts]
        .reverse()
        .find(
          (p): p is Extract<ChatMessagePart, { type: 'thinking' }> =>
            p.type === 'thinking' && p.thinkingId === thinkingId,
        );
      if (part) {
        part.content += delta;
      }
      assistant.thinking = (assistant.thinking ?? '') + delta;
      break;
    }
    case 'thinking_end': {
      const thinkingId = event.data.thinkingId;
      if (!thinkingId) break;
      const parts = assistant.parts ?? [];
      const part = [...parts]
        .reverse()
        .find(
          (p): p is Extract<ChatMessagePart, { type: 'thinking' }> =>
            p.type === 'thinking' && p.thinkingId === thinkingId,
        );
      if (part) {
        part.done = true;
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
            tool.status = 'error';
            tool.humanSummary = localizeAgentError('confirmation_timeout', '');
          }
          assistant.pendingConfirmation = null;
        }
        break;
      }
      assistant.streaming = false;
      assistant.error = {
        code: event.data.code,
        message: event.data.message,
        retryable: true,
      };
      break;
    }
    case 'plan_proposed': {
      const plan: ChatProposedPlan = {
        planId: event.data.planId,
        steps: event.data.steps,
        rationale: event.data.rationale,
        status: 'pending',
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
  /** Callback outils personas (ask_personas, simulate_meeting) après résultat. */
  onPersonasToolCall?: (
    toolName: 'ask_personas' | 'simulate_meeting',
    payload: { args: Record<string, unknown>; result: unknown },
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
  send: (text: string, options?: Partial<SendMessagePayload>) => Promise<void>;
  confirm: (decision: 'approve' | 'deny') => Promise<void>;
  approvePlan: (approved: boolean) => Promise<void>;
  retry: () => Promise<void>;
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
  const { locale, settingsLocked, permissionsNetwork } = useAppSettings();
  const { activePluginIds, getPluginDataDir } = usePlugins();
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

  let abortController: AbortController | null = null;
  let currentAssistantId: string | null = null;
  let pendingTokens = '';
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let lastUserText = '';
  let lastPayload: Partial<SendMessagePayload> = {};
  let idlePaused = false;
  // Identifiant de tour fourni par le backend (event turn_start). Utilisé pour
  // isoler la résolution d'une confirmation parmi plusieurs tours concurrents.
  let currentTurnId: string | null = null;
  let fallbackNotifiedTurnId: string | null = null;

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

  function applyEvent(event: ChatStreamEvent): void {
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
      fallbackNotifiedTurnId = null;
      return;
    }
    if (!currentAssistantId) return;
    if (event.type === 'token') {
      pendingTokens += event.data.token;
      scheduleFlush();
      return;
    }
    // Non-token : on commit d'abord les tokens en attente, puis on applique.
    flushPendingTokens();
    if (event.type === 'tool_call_result') {
      const toolName = event.data.name;
      if (toolName === 'ask_personas' || toolName === 'simulate_meeting') {
        const tool = messages.value
          .find((m) => m.id === currentAssistantId)
          ?.toolCalls?.find((t) => t.id === event.data.id);
        options.onPersonasToolCall?.(toolName, {
          args: tool?.args ?? {},
          result: event.data.result,
        });
      }
      if (isBrowserAgentTool(toolName) && event.data.error == null && event.data.status !== 'error') {
        options.onBrowserToolCall?.(toolName, event.data.result);
      }
    }
    if (event.type === 'error') {
      error.value = {
        code: event.data.code,
        message: event.data.message,
        retryable: true,
      };
    }
    if (event.type === 'done') {
      lastUsage.value = {
        inputTokens: parseOptionalInt(event.data.input_tokens),
        outputTokens: parseOptionalInt(event.data.output_tokens),
        totalTokens: parseOptionalInt(event.data.total_tokens),
      };
      completedTurns.value += 1;
    }
    applyStreamEvent(messages.value, currentAssistantId, event, () => {
      setIdlePaused(true);
    });
    if (event.type === 'tool_call_result') {
      setIdlePaused(false);
    }
  }

  function loadMessages(items: ChatMessage[]): void {
    flushPendingTokens();
    currentAssistantId = null;
    currentTurnId = null;
    fallbackNotifiedTurnId = null;
    error.value = null;
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    pendingTokens = '';
    // Normalise les messages sans `parts` (vieilles sessions) pour un rendu
    // uniforme : texte puis outils. Les messages déjà munis de parts gardent
    // leur ordre interleaved.
    messages.value = items.map((m) =>
      m.parts?.length ? m : { ...m, parts: buildLegacyParts(m) },
    );
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
    abortController?.abort();
    abortController = null;
    flushPendingTokens();
    resetStreamingFlag();
    currentAssistantId = null;
    currentTurnId = null;
    fallbackNotifiedTurnId = null;
    streaming.value = false;
  }

  async function send(
    text: string,
    payload: Partial<SendMessagePayload> = {},
  ): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || streaming.value) return;

    const projectPath = options.projectPath?.value;
    if (!projectPath) {
      error.value = {
        code: 'no_project',
        message: t('errors.noSpaceOpen'),
        retryable: false,
      };
      return;
    }

    const providerSet = buildActiveProviderSet(
      options.sessionModel?.value ?? null,
      options.reasoningEffort?.value ?? null,
    );
    if (providerSet) {
      if (!ensureProviderSetChatReady(providerSet)) {
        error.value = {
          code: 'api_key_missing',
          message: t('errors.apiKeyMissing'),
          retryable: false,
        };
        return;
      }
    } else {
      const legacyChat = buildActiveLlmConfigs().chat;
      if (!legacyChat) {
        error.value = {
          code: 'no_model',
          message: t('chat.page.noModelConfigured'),
          retryable: false,
        };
        return;
      }
    }

    error.value = null;
    streaming.value = true;
    lastUserText = trimmed;
    lastPayload = payload;

    const sentAttachments = payload.attachments ?? [];

    const userMessage: ChatMessage = {
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
      }));
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

    messages.value.push(userMessage, assistantMessage);

    abortController = new AbortController();
    currentAssistantId = assistantMessage.id;
    currentTurnId = null;
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
      );
      const providerSet = buildActiveProviderSet(
        options.sessionModel?.value ?? null,
        options.reasoningEffort?.value ?? null,
      );
      const chatConfig = llmConfigs.chat;
      const contextWindow = chatConfig
        ? contextWindowFor(
            chatConfig.provider as LlmProviderName,
            chatConfig.model,
          )
        : null;
      const pluginDataDir = await resolveAgentPluginDataDir(
        activePluginIds.value,
        getPluginDataDir,
      );
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
        ),
        options.browserPilotagePaused?.value ?? false,
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
        const chatError: ChatError = {
          code: 'idle_timeout',
          message: t('errors.idleTimeout'),
          retryable: true,
        };
        error.value = chatError;
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        }
      } else if (name === 'AbortError') {
        // Abort utilisateur (stop / navigation) : silencieux, le finally normalise.
        // On conserve le contenu partiel déjà streamé, sans marquer d'erreur.
      } else if (err instanceof SidecarHttpError) {
        const chatError = chatErrorFromSidecarHttp(err);
        error.value = chatError;
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        }
      } else {
        const detail = err instanceof Error ? err.message : '';
        const chatError: ChatError = {
          code: 'sidecar_unreachable',
          message: t('errors.sidecarUnreachable', {
            detail: detail ? t('errors.sidecarUnreachableDetail', { detail }) : '',
          }),
          retryable: true,
        };
        error.value = chatError;
        const assistant = messages.value.find(
          (m) => m.id === assistantMessage.id,
        );
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        }
      }
    } finally {
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      flushPendingTokens();
      resetStreamingFlag();
      currentAssistantId = null;
      streaming.value = false;
      abortController = null;
    }
  }

  async function retry(): Promise<void> {
    if (!lastUserText || streaming.value) return;
    // Retire la paire user+assistant du dernier tour échoué pour éviter un
    // doublon, puis relance le même message.
    const msgs = messages.value;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs.splice(i, 1);
        break;
      }
    }
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        msgs.splice(i, 1);
        break;
      }
    }
    await send(lastUserText, lastPayload);
  }

  async function confirm(decision: 'approve' | 'deny'): Promise<void> {
    const assistant = messages.value.find((m) => m.pendingConfirmation);
    const pending = assistant?.pendingConfirmation;
    if (!pending || confirming.value) return;

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
    } catch (err) {
      if (err instanceof SidecarHttpError && err.code) {
        error.value = chatErrorFromSidecarHttp(err);
      } else {
        const detail = err instanceof Error ? err.message : '';
        error.value = {
          code: 'confirm_failed',
          message: t('errors.confirmFailed', {
            detail: detail ? t('errors.confirmFailedDetail', { detail }) : '',
          }),
          retryable: true,
        };
      }
    } finally {
      confirming.value = false;
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
    if (providerSet && !ensureProviderSetChatReady(providerSet)) {
      throw new Error(t('errors.apiKeyMissing'));
    }

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
      error.value = {
        code: 'confirm_failed',
        message: t('errors.confirmFailed', {
          detail: detail ? t('errors.confirmFailedDetail', { detail }) : '',
        }),
        retryable: true,
      };
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
    send,
    confirm,
    approvePlan,
    retry,
    abort,
    loadMessages,
    reprocessAttachment,
  };
}
