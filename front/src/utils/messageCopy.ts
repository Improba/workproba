import type { ChatMessage, ChatTextPart } from '#types';

/** Texte visible de la réponse assistant, y compris l'analyse de l'agent métier. */
export function getAssistantCopyText(message: ChatMessage): string {
  const chunks: string[] = [];
  const parts = message.parts ?? [];
  if (parts.length > 0) {
    const textParts = parts
      .filter((p): p is ChatTextPart => p.type === 'text')
      .map((p) => p.content.trim())
      .filter(Boolean);
    chunks.push(...textParts);
  } else {
    const legacy = message.content?.trim() ?? '';
    if (legacy) chunks.push(legacy);
  }

  const handoff = message.specialistHandoff;
  if (handoff?.status === 'done') {
    const analysis = handoff.content.trim();
    if (analysis) {
      const name = handoff.specialistName.trim();
      chunks.push(name ? `${name}\n${analysis}` : analysis);
    }
  }

  return chunks.join('\n\n');
}
