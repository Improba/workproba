import { ref, type Ref } from 'vue';
import type {
  ChatConfirmation,
  ChatError,
  ChatErrorCode,
  ChatMessage,
  ChatMessagePart,
  ChatStreamEvent,
  ChatToolCall,
  SendMessagePayload,
} from '#types';
import type { LocalDocumentEntry } from '@composables/useDesktop.types';
import {
  buildAgentTurnPayload,
  getAiSidecarUrl,
  getDesktopSecret,
  type UiMode,
} from '@services/aiSidecar';
import { buildActiveLlmConfigs } from '@composables/useAppSettings';

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

function parseSseChunk(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const events: ChatStreamEvent[] = [];
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
      events.push({
        type: eventType as ChatStreamEvent['type'],
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

/** Mappe un event SSE Python vers le format interne du front (testable). */
export function mapPythonSseEvent(event: ChatStreamEvent): ChatStreamEvent {
  const data = event.data;

  switch (event.type) {
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
          error: isError ? data.result ?? true : null,
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
        },
      };
    case 'done':
      return {
        type: 'done',
        data: { content: String(data.content ?? '') },
      };
    case 'error':
      return {
        type: 'error',
        data: {
          code: String(data.code ?? 'agent_error'),
          message: localizeAgentError(
            String(data.code ?? 'agent_error'),
            String(data.message ?? 'Erreur agent'),
          ),
        },
      };
    default:
      return event;
  }
}

function createMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function createPartId(): string {
  return `part_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/** Reconstruit des `parts` ordonnées pour un message legacy sans parts. */
function buildLegacyParts(message: ChatMessage): ChatMessagePart[] {
  const parts: ChatMessagePart[] = [];
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
}

function syncContent(assistant: ChatMessage): void {
  assistant.content = (assistant.parts ?? [])
    .filter(
      (p): p is { type: 'text'; id: string; content: string } => p.type === 'text',
    )
    .map((p) => p.content)
    .join('');
}

/** Traduit un code d'erreur agent en message français affichable. */
function localizeAgentError(code: string, fallback: string): string {
  switch (code) {
    case 'max_iterations_reached':
      return "L'agent a atteint sa limite d'itérations sans réponse finale. Reformulez ou réessayez.";
    case 'agent_model_error':
      return 'Le modèle a renvoyé une réponse inattendue. Réessayez.';
    default:
      return fallback || 'Une erreur est survenue pendant la génération.';
  }
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
  return typeof versionPath === 'string' && versionPath ? versionPath : undefined;
}

function applyStreamEvent(
  messages: ChatMessage[],
  assistantMessageId: string,
  event: ChatStreamEvent,
  onConfirmationRequest?: () => void,
): void {
  const assistant = messages.find((m) => m.id === assistantMessageId);
  if (!assistant) return;

  switch (event.type) {
    case 'tool_call_start': {
      const startSummary = String(event.data.humanSummary ?? '').trim();
      const toolCall: ChatToolCall = {
        id: String(event.data.id ?? createMessageId()),
        name: String(event.data.name ?? 'tool'),
        status: 'running',
        args: (event.data.args as Record<string, unknown>) ?? {},
        startedAt: Date.now(),
        filePath:
          typeof event.data.filePath === 'string' ? event.data.filePath : undefined,
        humanSummary: startSummary || undefined,
      };
      assistant.toolCalls = [...(assistant.toolCalls ?? []), toolCall];
      // On insère la carte d'outil dans le flux, à la suite du texte courant,
      // pour respecter l'ordre réel (texte -> outil -> texte).
      const parts = assistant.parts ?? (assistant.parts = []);
      parts.push({ type: 'tool_call', id: createPartId(), toolCallId: toolCall.id });
      break;
    }
    case 'confirmation_request': {
      const toolId = String(event.data.toolCallId ?? '');
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.status = 'awaiting_confirmation';
      }
      const confirmation: ChatConfirmation = {
        confirmationId: String(event.data.confirmationId ?? ''),
        toolCallId: toolId,
        toolName: String(event.data.toolName ?? ''),
        action: event.data.action === 'modify' ? 'modify' : 'create',
        proposedPath: String(event.data.proposedPath ?? ''),
        humanSummary: String(event.data.humanSummary ?? '').trim(),
      };
      assistant.pendingConfirmation = confirmation;
      onConfirmationRequest?.();
      break;
    }
    case 'tool_call_result': {
      const toolId = String(event.data.id ?? '');
      const tool = assistant.toolCalls?.find((t) => t.id === toolId);
      if (tool) {
        tool.result = event.data.result;
        tool.status =
          event.data.error != null
            ? 'error'
            : ((event.data.status as ChatToolCall['status']) ?? 'success');
        tool.endedAt = Date.now();
        if (typeof event.data.filePath === 'string') {
          tool.filePath = event.data.filePath;
        } else if (!tool.filePath) {
          const fromResult = extractFilePathFromResult(event.data.result);
          if (fromResult) tool.filePath = fromResult;
        }
        const snapshotPath = extractSnapshotPathFromResult(event.data.result);
        if (snapshotPath) {
          tool.snapshotPath = snapshotPath;
        }
        const resultSummary = String(event.data.humanSummary ?? '').trim();
        if (resultSummary) {
          tool.humanSummary = resultSummary;
        }
        if (assistant.pendingConfirmation?.toolCallId === toolId) {
          assistant.pendingConfirmation = null;
        }
      }
      break;
    }
    case 'done': {
      assistant.streaming = false;
      const finalContent =
        typeof event.data.content === 'string' ? event.data.content : '';
      // On ne remplace JAMAIS le contenu streamé : ce serait écraser le texte
      // produit avant les appels d'outil et casser le rendu interleaved. On
      // n'utilise done.content qu'en fallback quand rien n'a été streamé
      // (provider non streaming ou tour sans tokens).
      if (finalContent && !assistant.content) {
        const parts = assistant.parts ?? (assistant.parts = []);
        const firstText = parts.find(
          (p): p is { type: 'text'; id: string; content: string } => p.type === 'text',
        );
        if (firstText) {
          firstText.content = finalContent;
        } else {
          parts.unshift({ type: 'text', id: createPartId(), content: finalContent });
        }
        syncContent(assistant);
      }
      break;
    }
    case 'error': {
      assistant.streaming = false;
      assistant.error = {
        code: String(event.data.code ?? 'agent_error') as ChatErrorCode,
        message: String(event.data.message ?? 'stream interrompu'),
        retryable: true,
      };
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
        applyEvent(mapPythonSseEvent(rawEvent));
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
  documents?: Ref<LocalDocumentEntry[]>;
  uiMode?: Ref<UiMode | undefined>;
}

export interface UseChatStreamReturn {
  messages: Ref<ChatMessage[]>;
  streaming: Ref<boolean>;
  error: Ref<ChatError | null>;
  confirming: Ref<boolean>;
  send: (text: string, options?: Partial<SendMessagePayload>) => Promise<void>;
  confirm: (decision: 'approve' | 'deny') => Promise<void>;
  retry: () => Promise<void>;
  abort: () => void;
  loadMessages: (items: ChatMessage[]) => void;
}

/** SSE via sidecar Python local (application bureau). */
export function useChatStream(options: UseChatStreamOptions): UseChatStreamReturn {
  // ref (profond) : les objets messages sont réactifs, donc muter
  // `assistant.content` déclenche directement le rendu. Pas de clonage du
  // tableau à chaque token.
  const messages = ref<ChatMessage[]>(options.initialMessages ?? []);
  const streaming = ref(false);
  const error = ref<ChatError | null>(null);
  const confirming = ref(false);

  let abortController: AbortController | null = null;
  let currentAssistantId: string | null = null;
  let pendingTokens = '';
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let lastUserText = '';
  let lastPayload: Partial<SendMessagePayload> = {};
  let idlePaused = false;

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
    if (!currentAssistantId) return;
    if (event.type === 'token') {
      pendingTokens += String(event.data.token ?? '');
      scheduleFlush();
      return;
    }
    // Non-token : on commit d'abord les tokens en attente, puis on applique.
    flushPendingTokens();
    if (event.type === 'error') {
      error.value = {
        code: String(event.data.code ?? 'agent_error') as ChatErrorCode,
        message: String(event.data.message ?? 'stream interrompu'),
        retryable: true,
      };
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
        message: "Aucun dossier projet ouvert. Ouvrez un dossier pour discuter avec l'agent.",
        retryable: false,
      };
      return;
    }

    error.value = null;
    streaming.value = true;
    lastUserText = trimmed;
    lastPayload = payload;

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: 'user',
      content: trimmed,
      parentId: payload.parentId ?? null,
      createdAt: new Date().toISOString(),
    };

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
      const body = buildAgentTurnPayload(
        options.sessionId.value,
        projectPath,
        trimmed,
        history,
        documents,
        options.workspaceDataDir?.value,
        buildActiveLlmConfigs(),
        options.uiMode?.value,
      );

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
        throw new Error(`HTTP ${response.status}`);
      }

      await consumeSseStream(response, applyEvent, abortController, idleState, {
        isPaused: () => idlePaused,
      });
    } catch (err) {
      const name = (err as Error)?.name;

      if (name === 'StreamIdleTimeoutError') {
        const chatError: ChatError = {
          code: 'idle_timeout',
          message: 'Le modèle a mis trop de temps à répondre. Vous pouvez réessayer.',
          retryable: true,
        };
        error.value = chatError;
        const assistant = messages.value.find((m) => m.id === assistantMessage.id);
        if (assistant) {
          assistant.streaming = false;
          assistant.error = chatError;
        }
      } else if (name === 'AbortError') {
        // Abort utilisateur (stop / navigation) : silencieux, le finally normalise.
        // On conserve le contenu partiel déjà streamé, sans marquer d'erreur.
      } else {
        const detail = err instanceof Error ? err.message : '';
        const chatError: ChatError = {
          code: 'sidecar_unreachable',
          message: `Le service IA n'est pas accessible${
            detail ? ` (${detail})` : ''
          }. Vérifiez qu'il est démarré depuis les réglages.`,
          retryable: true,
        };
        error.value = chatError;
        const assistant = messages.value.find((m) => m.id === assistantMessage.id);
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
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      error.value = {
        code: 'confirm_failed',
        message: `Impossible d'envoyer votre choix${detail ? ` (${detail})` : ''}. Réessayez.`,
        retryable: true,
      };
    } finally {
      confirming.value = false;
    }
  }

  return {
    messages,
    streaming,
    error,
    confirming,
    send,
    confirm,
    retry,
    abort,
    loadMessages,
  };
}
