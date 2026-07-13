import type { ChatMessage } from '#types';

/** Budget caractères pour le contexte chat principal (~3000 tokens). */
export const MAIN_CHAT_CONTEXT_MAX_CHARS = 12_000;

export interface MainChatContextOptions {
  locale?: string;
  maxChars?: number;
}

function roleLabels(locale?: string): { user: string; assistant: string } {
  if (locale?.toLowerCase().startsWith('en')) {
    return { user: 'User', assistant: 'Assistant' };
  }
  return { user: 'Utilisateur', assistant: 'Assistant' };
}

function messageLine(message: ChatMessage, labels: { user: string; assistant: string }): string | null {
  if (message.streaming) return null;

  const trimmed = message.content?.trim();
  if (trimmed) {
    const label = message.role === 'user' ? labels.user : labels.assistant;
    return `${label} : ${trimmed}`;
  }

  const opinion = message.personasOpinion;
  if (opinion?.question?.trim()) {
    const label = labels.assistant;
    return `${label} : [Avis personas sur « ${opinion.question.trim()} »]`;
  }

  return null;
}

function truncationMarker(omitted: number, locale?: string): string {
  if (locale?.toLowerCase().startsWith('en')) {
    return omitted === 1
      ? '… (1 earlier message omitted)'
      : `… (${omitted} earlier messages omitted)`;
  }
  return omitted === 1
    ? '… (1 message antérieur omis)'
    : `… (${omitted} messages antérieurs omis)`;
}

function truncateToBudget(lines: string[], maxChars: number, locale?: string): string {
  if (lines.length === 0 || maxChars <= 0) return '';

  const kept: string[] = [];
  let total = 0;
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]!;
    const extra = kept.length > 0 ? line.length + 1 : line.length;
    if (total + extra > maxChars) break;
    kept.unshift(line);
    total += extra;
  }

  if (kept.length < lines.length && kept.length > 0) {
    const marker = truncationMarker(lines.length - kept.length, locale);
    const markerBudget = marker.length + 1;
    if (total + markerBudget <= maxChars) {
      kept.unshift(marker);
    }
  }

  return kept.join('\n');
}

/** Formate les messages du chat principal pour le contexte personas. */
export function formatMainChatContext(
  messages: ChatMessage[],
  options?: MainChatContextOptions,
): string {
  const maxChars = options?.maxChars ?? MAIN_CHAT_CONTEXT_MAX_CHARS;
  const labels = roleLabels(options?.locale);

  const lines = messages
    .map((message) => messageLine(message, labels))
    .filter((line): line is string => Boolean(line));

  return truncateToBudget(lines, maxChars, options?.locale);
}
