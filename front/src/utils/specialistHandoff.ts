import { toolResultToOpinionCard } from '@composables/usePersonas';
import type {
  ChatMessage,
  ChatMessagePart,
  ChatToolCall,
  PersonasOpinionCard,
  SpecialistHandoffCard,
  SpecialistHandoffMode,
  SpecialistHandoffStatus,
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

  return {
    id: createHandoffId(),
    toolCallId,
    specialistId: String(payload.specialist_id ?? specialistId).trim() || specialistId,
    specialistName: name,
    avatarColor: meta.avatarColor,
    avatarIcon: meta.avatarIcon,
    mode: normalizeHandoffMode(payload.mode ?? mode),
    task,
    content: String(payload.content ?? '').trim(),
    degradedTools: parseDegradedTools(payload.degraded_tools),
    status: 'done' satisfies SpecialistHandoffStatus,
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
  if (message.personasOpinion) {
    message.personasOpinion = {
      ...message.personasOpinion,
      streaming: false,
    };
  }
}
