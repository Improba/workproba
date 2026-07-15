import type { ChatMessage, ChatTextPart } from '#types';

/** Texte visible de la réponse assistant (segments texte uniquement). */
export function getAssistantCopyText(message: ChatMessage): string {
  const parts = message.parts ?? [];
  if (parts.length > 0) {
    const textParts = parts
      .filter((p): p is ChatTextPart => p.type === 'text')
      .map((p) => p.content.trim())
      .filter(Boolean);
    if (textParts.length > 0) return textParts.join('\n\n');
  }
  return message.content?.trim() ?? '';
}
