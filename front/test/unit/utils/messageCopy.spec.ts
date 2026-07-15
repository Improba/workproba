import { describe, expect, it } from 'vitest';
import { getAssistantCopyText } from '@utils/messageCopy';
import type { ChatMessage } from '#types';

describe('getAssistantCopyText', () => {
  it('concatène les segments texte ordonnés', () => {
    const message: ChatMessage = {
      id: 'a1',
      role: 'assistant',
      content: 'legacy',
      parts: [
        { type: 'text', id: 't1', content: 'Premier bloc.' },
        { type: 'thinking', id: 'th1', thinkingId: 'think-0', content: 'secret', done: true },
        { type: 'text', id: 't2', content: 'Deuxième bloc.' },
      ],
      createdAt: '2026-01-01T00:00:00.000Z',
    };

    expect(getAssistantCopyText(message)).toBe('Premier bloc.\n\nDeuxième bloc.');
  });

  it('retombe sur content quand parts est absent', () => {
    const message: ChatMessage = {
      id: 'a2',
      role: 'assistant',
      content: '  Réponse simple.  ',
      createdAt: '2026-01-01T00:00:00.000Z',
    };

    expect(getAssistantCopyText(message)).toBe('Réponse simple.');
  });

  it('retourne une chaîne vide sans texte copiable', () => {
    const message: ChatMessage = {
      id: 'a3',
      role: 'assistant',
      content: '   ',
      parts: [{ type: 'thinking', id: 'th1', thinkingId: 'think-0', content: 'raisonnement', done: true }],
      createdAt: '2026-01-01T00:00:00.000Z',
    };

    expect(getAssistantCopyText(message)).toBe('');
  });
});
