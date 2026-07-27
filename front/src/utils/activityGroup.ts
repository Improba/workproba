import type {
  ChatMessagePart,
  ChatThinkingPart,
  ChatToolCall,
  ChatToolCallPart,
} from '#types';

export interface ActivityGroupData {
  /** Clé stable : id de la première part du run. */
  id: string;
  parts: (ChatThinkingPart | ChatToolCallPart)[];
  toolCallIds: string[];
}

export type MessageRenderBlock =
  | { kind: 'text'; part: Extract<ChatMessagePart, { type: 'text' }> }
  | { kind: 'activity_group'; group: ActivityGroupData };

/**
 * Regroupe les runs consécutifs `thinking` | `tool_call` entre segments `text`
 * en un bloc `activity_group` (pastille compacte), y compris sans outil.
 */
export function groupMessageParts(parts: ChatMessagePart[]): MessageRenderBlock[] {
  const result: MessageRenderBlock[] = [];
  let i = 0;

  while (i < parts.length) {
    const part = parts[i];

    if (part.type === 'text') {
      result.push({ kind: 'text', part });
      i += 1;
      continue;
    }

    const runParts: (ChatThinkingPart | ChatToolCallPart)[] = [];
    while (i < parts.length) {
      const current = parts[i];
      if (current.type !== 'thinking' && current.type !== 'tool_call') break;
      runParts.push(current as ChatThinkingPart | ChatToolCallPart);
      i += 1;
    }

    // Type hors union ou run vide : avancer pour éviter une boucle infinie.
    if (runParts.length === 0) {
      i += 1;
      continue;
    }

    result.push({
      kind: 'activity_group',
      group: {
        id: runParts[0].id,
        parts: runParts,
        toolCallIds: runParts
          .filter((p): p is ChatToolCallPart => p.type === 'tool_call')
          .map((p) => p.toolCallId),
      },
    });
  }

  return result;
}

/**
 * Id du groupe d'activité contenant `parts[index]` : id de la première part
 * du run `thinking`|`tool_call` (aligné sur `groupMessageParts`).
 * Null si l'index est hors bornes ou pointe un segment texte.
 */
export function activityGroupIdAt(
  parts: ChatMessagePart[],
  index: number,
): string | null {
  const part = parts[index];
  if (!part || (part.type !== 'thinking' && part.type !== 'tool_call')) {
    return null;
  }
  let start = index;
  while (start > 0) {
    const prev = parts[start - 1];
    if (prev.type !== 'thinking' && prev.type !== 'tool_call') break;
    start -= 1;
  }
  return parts[start]?.id ?? null;
}

/** Extrait le connecteur d'un outil `managed__{connector}__{tool}`. */
export function extractManagedConnector(toolName: string): string | null {
  if (!toolName.startsWith('managed__')) return null;
  const rest = toolName.slice('managed__'.length);
  const sep = rest.lastIndexOf('__');
  if (sep <= 0 || sep + 2 >= rest.length) return null;
  return rest.slice(0, sep);
}

/**
 * Suffixe connecteur pour le résumé : un seul connecteur, ou plusieurs joints
 * par virgule. Null si aucun outil managed.
 */
export function deriveConnectorSuffix(toolCalls: ChatToolCall[]): string | null {
  const connectors = new Set<string>();
  for (const tc of toolCalls) {
    const connector = extractManagedConnector(tc.name);
    if (connector) connectors.add(connector);
  }
  if (connectors.size === 0) return null;
  return [...connectors].sort().join(', ');
}

export interface ActivityGroupStats {
  toolCount: number;
  errorCount: number;
  hasRunning: boolean;
}

export function computeActivityGroupStats(
  toolCallParts: ChatToolCallPart[],
  toolCallsById: ReadonlyMap<string, ChatToolCall>,
): ActivityGroupStats {
  let errorCount = 0;
  let hasRunning = false;

  for (const part of toolCallParts) {
    const tc = toolCallsById.get(part.toolCallId);
    if (!tc) continue;
    if (tc.status === 'error') errorCount += 1;
    if (
      tc.status === 'running' ||
      tc.status === 'pending_confirmation' ||
      tc.status === 'awaiting_confirmation'
    ) {
      hasRunning = true;
    }
  }

  return {
    toolCount: toolCallParts.length,
    errorCount,
    hasRunning,
  };
}
