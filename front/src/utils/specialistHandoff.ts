import { toolResultToOpinionCard } from '@composables/usePersonas';
import type {
  ChatMessage,
  ChatMessagePart,
  ChatToolCall,
  PersonasOpinionCard,
  SpecialistHandoffCard,
  SpecialistHandoffMode,
  SpecialistHandoffStatus,
  SpecialistNestedTool,
} from '#types';

export const PERSPECTIVE_HANDOFF_TOOLS = ['ask_personas', 'summon_specialist'] as const;

export type PerspectiveHandoffTool = (typeof PERSPECTIVE_HANDOFF_TOOLS)[number];

export function isPerspectiveHandoffTool(name: string): name is PerspectiveHandoffTool {
  return name === 'ask_personas' || name === 'summon_specialist';
}

export function shouldHidePerspectiveToolCall(
  message: ChatMessage,
  toolCall?: ChatToolCall,
): boolean {
  if (!toolCall || !isPerspectiveHandoffTool(toolCall.name)) return false;
  const toolCallId = toolCall.id;
  if (
    message.pendingConfirmation?.toolCallId === toolCallId ||
    message.preparingConfirmation?.toolCallId === toolCallId
  ) {
    return false;
  }
  if (toolCall.name === 'ask_personas' && message.personasOpinion) return true;
  if (toolCall.name === 'summon_specialist' && message.specialistHandoff) return true;
  return false;
}

export function normalizeHandoffMode(raw: unknown): SpecialistHandoffMode {
  return raw === 'operative' ? 'operative' : 'regard';
}

function createHandoffId(): string {
  return `handoff_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function createOpinionId(): string {
  return `opinion_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

export interface SpecialistMeta {
  name?: string;
  avatarColor?: string;
  avatarIcon?: string;
}

export function resolveSpecialistLabel(
  specialistId: string,
  resolveMeta?: (id: string) => SpecialistMeta | null,
): SpecialistMeta {
  const meta = resolveMeta?.(specialistId);
  return {
    name: meta?.name?.trim() || specialistId,
    avatarColor: meta?.avatarColor,
    avatarIcon: meta?.avatarIcon,
  };
}

export function createRunningSpecialistHandoff(
  toolCallId: string,
  args: Record<string, unknown>,
  resolveMeta?: (id: string) => SpecialistMeta | null,
): SpecialistHandoffCard {
  const specialistId = String(args.specialist_id ?? '').trim();
  const meta = resolveSpecialistLabel(specialistId, resolveMeta);
  return {
    id: createHandoffId(),
    toolCallId,
    specialistId,
    specialistName: meta.name ?? specialistId,
    avatarColor: meta.avatarColor,
    avatarIcon: meta.avatarIcon,
    mode: normalizeHandoffMode(args.mode),
    task: String(args.task ?? '').trim(),
    content: '',
    status: 'running',
    streaming: true,
  };
}

function parseDegradedTools(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => String(item).trim()).filter(Boolean);
}

export function toolResultToSpecialistHandoff(
  toolCallId: string,
  args: Record<string, unknown>,
  result: unknown,
  error?: unknown,
  resolveMeta?: (id: string) => SpecialistMeta | null,
): SpecialistHandoffCard | null {
  const specialistId = String(args.specialist_id ?? '').trim();
  const meta = resolveSpecialistLabel(specialistId, resolveMeta);
  const mode = normalizeHandoffMode(args.mode);
  const task = String(args.task ?? '').trim();

  if (error != null) {
    return {
      id: createHandoffId(),
      toolCallId,
      specialistId,
      specialistName: meta.name ?? specialistId,
      avatarColor: meta.avatarColor,
      avatarIcon: meta.avatarIcon,
      mode,
      task,
      content: '',
      status: 'error',
      streaming: false,
    };
  }

  if (!result || typeof result !== 'object') return null;
  const payload = result as Record<string, unknown>;
  const name = String(payload.specialist_name ?? meta.name ?? specialistId).trim();
  const payloadError = payload.error != null ? String(payload.error).trim() : '';
  const content = String(payload.content ?? '').trim();
  const hasStructuredError = payloadError.length > 0;

  return {
    id: createHandoffId(),
    toolCallId,
    specialistId: String(payload.specialist_id ?? specialistId).trim() || specialistId,
    specialistName: name,
    avatarColor: meta.avatarColor,
    avatarIcon: meta.avatarIcon,
    mode: normalizeHandoffMode(payload.mode ?? mode),
    task,
    content,
    degradedTools: parseDegradedTools(payload.degraded_tools),
    status: hasStructuredError ? 'error' : ('done' satisfies SpecialistHandoffStatus),
    streaming: false,
  };
}

export function initStreamingPersonasOpinion(question: string): PersonasOpinionCard {
  return {
    id: createOpinionId(),
    question,
    opinions: [],
    streaming: true,
  };
}

export function filterPartsHidingPerspectiveTools(
  parts: ChatMessagePart[],
  message: ChatMessage,
): ChatMessagePart[] {
  const toolCalls = message.toolCalls ?? [];
  const byId = new Map(toolCalls.map((tc) => [tc.id, tc]));
  return parts.filter((part) => {
    if (part.type !== 'tool_call') return true;
    const toolCall = byId.get(part.toolCallId);
    return !shouldHidePerspectiveToolCall(message, toolCall);
  });
}

export function markRunningSpecialistHandoffAsError(message: ChatMessage): void {
  const handoff = message.specialistHandoff;
  if (!handoff) return;
  if (
    handoff.status !== 'running' &&
    handoff.status !== 'pending' &&
    handoff.streaming !== true
  ) {
    return;
  }
  message.specialistHandoff = {
    ...handoff,
    status: 'error',
    streaming: false,
  };
}

export function markSpecialistHandoffAsPending(message: ChatMessage): void {
  const handoff = message.specialistHandoff;
  if (!handoff) return;
  if (handoff.status === 'done' || handoff.status === 'error') return;
  message.specialistHandoff = {
    ...handoff,
    status: 'pending',
    streaming: false,
  };
}

export function markSpecialistHandoffAsRunning(message: ChatMessage): void {
  const handoff = message.specialistHandoff;
  if (!handoff) return;
  if (handoff.status !== 'pending') return;
  message.specialistHandoff = {
    ...handoff,
    status: 'running',
    streaming: true,
  };
}

export function appendSpecialistHandoffToken(
  card: SpecialistHandoffCard,
  token: string,
): SpecialistHandoffCard {
  if (!token) return card;
  return {
    ...card,
    content: card.content + token,
    streaming: true,
  };
}

export function appendSpecialistHandoffThinking(
  card: SpecialistHandoffCard,
  delta: string,
): SpecialistHandoffCard {
  if (!delta) return card;
  return {
    ...card,
    thinking: (card.thinking ?? '') + delta,
    thinkingDone: false,
  };
}

export function endSpecialistHandoffThinking(
  card: SpecialistHandoffCard,
): SpecialistHandoffCard {
  return {
    ...card,
    thinkingDone: true,
  };
}

export function upsertSpecialistNestedTool(
  card: SpecialistHandoffCard,
  tool: SpecialistNestedTool,
): SpecialistHandoffCard {
  const nestedTools = [...(card.nestedTools ?? [])];
  const index = nestedTools.findIndex((entry) => entry.id === tool.id);
  if (index >= 0) {
    nestedTools[index] = { ...nestedTools[index], ...tool };
  } else {
    nestedTools.push(tool);
  }
  return {
    ...card,
    nestedTools,
  };
}

export function markPersonasOpinionAsError(message: ChatMessage): void {
  const opinion = message.personasOpinion;
  if (!opinion) return;
  message.personasOpinion = {
    ...opinion,
    streaming: false,
    error: true,
  };
}

export function applyPersonasOpinionFromToolResult(
  message: ChatMessage,
  args: Record<string, unknown>,
  result: unknown,
): void {
  const question = String(args.question ?? message.personasOpinion?.question ?? '');
  const card = toolResultToOpinionCard(question, result);
  if (card) {
    message.personasOpinion = card;
    return;
  }
  if (!message.personasOpinion) {
    message.personasOpinion = initStreamingPersonasOpinion(question);
  }
  markPersonasOpinionAsError(message);
}

const INCOMPLETE_TOOL_STATUSES = new Set<ChatToolCall['status']>([
  'pending',
  'running',
  'pending_confirmation',
  'awaiting_confirmation',
]);

function findLatestPerspectiveToolCall(
  toolCalls: ChatToolCall[],
  name: PerspectiveHandoffTool,
): ChatToolCall | undefined {
  for (let i = toolCalls.length - 1; i >= 0; i -= 1) {
    if (toolCalls[i]?.name === name) return toolCalls[i];
  }
  return undefined;
}

export interface RehydratePerspectiveCardsOptions {
  resolveSpecialistMeta?: (id: string) => SpecialistMeta | null;
}

/** Reconstruit les cartes inline perspective à partir des toolCalls persistés. */
export function rehydratePerspectiveCards(
  message: ChatMessage,
  options?: RehydratePerspectiveCardsOptions,
): void {
  if (message.role !== 'assistant') return;
  const toolCalls = message.toolCalls ?? [];
  if (!toolCalls.length) return;

  const summonTool = findLatestPerspectiveToolCall(toolCalls, 'summon_specialist');
  if (summonTool && !message.specialistHandoff) {
    const args = summonTool.args ?? {};
    if (INCOMPLETE_TOOL_STATUSES.has(summonTool.status)) {
      message.specialistHandoff = createRunningSpecialistHandoff(
        summonTool.id,
        args,
        options?.resolveSpecialistMeta,
      );
      if (
        summonTool.status === 'pending_confirmation' ||
        summonTool.status === 'awaiting_confirmation'
      ) {
        markSpecialistHandoffAsPending(message);
      }
    } else if (summonTool.status === 'error') {
      const handoff = toolResultToSpecialistHandoff(
        summonTool.id,
        args,
        summonTool.result,
        true,
        options?.resolveSpecialistMeta,
      );
      if (handoff) {
        message.specialistHandoff = handoff;
      } else {
        message.specialistHandoff = createRunningSpecialistHandoff(
          summonTool.id,
          args,
          options?.resolveSpecialistMeta,
        );
        markRunningSpecialistHandoffAsError(message);
      }
    } else {
      const handoff = toolResultToSpecialistHandoff(
        summonTool.id,
        args,
        summonTool.result,
        undefined,
        options?.resolveSpecialistMeta,
      );
      if (handoff) {
        message.specialistHandoff = handoff;
      } else {
        message.specialistHandoff = createRunningSpecialistHandoff(
          summonTool.id,
          args,
          options?.resolveSpecialistMeta,
        );
        markRunningSpecialistHandoffAsError(message);
      }
    }
  }

  const askTool = findLatestPerspectiveToolCall(toolCalls, 'ask_personas');
  if (askTool && !message.personasOpinion) {
    const args = askTool.args ?? {};
    const question = String(args.question ?? '');
    if (INCOMPLETE_TOOL_STATUSES.has(askTool.status)) {
      message.personasOpinion = initStreamingPersonasOpinion(question);
    } else if (askTool.status === 'error') {
      message.personasOpinion = initStreamingPersonasOpinion(question);
      markPersonasOpinionAsError(message);
    } else {
      applyPersonasOpinionFromToolResult(message, args, askTool.result);
    }
  }
}
