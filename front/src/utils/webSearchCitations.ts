import type { ChatMessage, WebSearchCitation } from '#types';

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function pushCitation(
  citations: WebSearchCitation[],
  seen: Set<string>,
  entry: Record<string, unknown>,
): void {
  const url = asString(entry.url);
  if (!url || seen.has(url)) return;
  seen.add(url);
  const title = asString(entry.title) || url;
  citations.push({
    url,
    title,
    snippet: asString(entry.snippet),
  });
}

/** Extrait les sources web des résultats `web_search` d'un message assistant. */
export function extractWebSearchCitations(message: ChatMessage): WebSearchCitation[] {
  const citations: WebSearchCitation[] = [];
  const seen = new Set<string>();

  for (const toolCall of message.toolCalls ?? []) {
    if (toolCall.name !== 'web_search' || toolCall.status === 'error') continue;
    const result = asRecord(toolCall.result);
    if (!result) continue;

    const results = Array.isArray(result.results) ? result.results : [];
    for (const item of results) {
      const entry = asRecord(item);
      if (entry) pushCitation(citations, seen, entry);
    }

    const resultCitations = Array.isArray(result.citations) ? result.citations : [];
    for (const item of resultCitations) {
      const entry = asRecord(item);
      if (entry) pushCitation(citations, seen, entry);
    }
  }

  return citations;
}
