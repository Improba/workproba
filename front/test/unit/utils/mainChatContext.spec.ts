import { describe, expect, it } from 'vitest';
import {
  formatMainChatContext,
  MAIN_CHAT_CONTEXT_MAX_CHARS,
} from '@utils/mainChatContext';
import type { ChatMessage } from '#types';

function msg(partial: Partial<ChatMessage> & Pick<ChatMessage, 'role' | 'content'>): ChatMessage {
  return {
    id: partial.id ?? 'm1',
    role: partial.role,
    content: partial.content,
    createdAt: partial.createdAt ?? '2026-01-01T00:00:00.000Z',
    ...partial,
  };
}

describe('formatMainChatContext', () => {
  it('formate les messages user et assistant', () => {
    const context = formatMainChatContext([
      msg({ id: '1', role: 'user', content: 'Je fais mon CV' }),
      msg({ id: '2', role: 'assistant', content: 'Par quoi commencer ?' }),
    ]);

    expect(context).toBe(
      'Utilisateur : Je fais mon CV\nAssistant : Par quoi commencer ?',
    );
  });

  it('utilise les libellés anglais quand la locale est en', () => {
    const context = formatMainChatContext(
      [msg({ role: 'user', content: 'Hello' })],
      { locale: 'en-US' },
    );

    expect(context).toBe('User : Hello');
  });

  it('ignore les messages en streaming ou sans contenu', () => {
    const context = formatMainChatContext([
      msg({ role: 'user', content: '  ' }),
      msg({ role: 'assistant', content: 'OK', streaming: true }),
    ]);

    expect(context).toBe('');
  });

  it('inclut les cartes personas inline', () => {
    const context = formatMainChatContext([
      msg({
        role: 'assistant',
        content: '',
        personasOpinion: {
          id: 'op1',
          question: 'Ce CV est-il clair ?',
          opinions: [],
          streaming: false,
        },
      }),
    ]);

    expect(context).toBe(
      'Assistant : [Avis personas sur « Ce CV est-il clair ? »]',
    );
  });

  it('conserve les messages récents quand le budget est dépassé', () => {
    const long = 'x'.repeat(100);
    const context = formatMainChatContext(
      [
        msg({ id: '1', role: 'user', content: long }),
        msg({ id: '2', role: 'assistant', content: 'récent' }),
      ],
      { maxChars: 80 },
    );

    expect(context).toContain('récent');
    expect(context).not.toContain(long);
    expect(context).toContain('message antérieur omis');
  });

  it('expose un budget par défaut raisonnable', () => {
    expect(MAIN_CHAT_CONTEXT_MAX_CHARS).toBeGreaterThanOrEqual(8_000);
  });
});
