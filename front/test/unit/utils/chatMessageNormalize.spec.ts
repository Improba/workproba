import { describe, expect, it } from 'vitest';
import { normalizeChatMessage, normalizeChatMessages } from '@utils/chatMessageNormalize';

describe('chatMessageNormalize', () => {
  it('rejette un message malformé sans crash', () => {
    expect(normalizeChatMessage(null)).toBeNull();
    expect(normalizeChatMessage({ role: 'bot', content: 'x' })).toBeNull();
    expect(normalizeChatMessage({ id: '', role: 'user', content: 'x' })).toBeNull();
  });

  it('normalise un message valide et filtre les parts invalides', () => {
    const normalized = normalizeChatMessage({
      id: 'm1',
      role: 'assistant',
      content: 'Bonjour',
      parts: [
        { type: 'text', id: 'p1', content: 'Bonjour' },
        { type: 'tool_call', id: 'p2' },
        { type: 'unknown', id: 'p3' },
      ],
      toolCalls: [
        { id: 'tc1', name: 'list_files', status: 'success' },
        { id: '', name: 'broken' },
      ],
      error: { code: 'turn_timeout', message: 'Timeout', retryable: true },
      createdAt: '2026-01-01T00:00:00.000Z',
    });

    expect(normalized).toMatchObject({
      id: 'm1',
      role: 'assistant',
      content: 'Bonjour',
      error: { code: 'turn_timeout', message: 'Timeout', retryable: true },
    });
    expect(normalized?.parts).toHaveLength(1);
    expect(normalized?.toolCalls).toHaveLength(1);
  });

  it('normalise un tableau mixte valide / invalide', () => {
    const messages = normalizeChatMessages([
      { id: 'ok', role: 'user', content: 'hi', createdAt: '2026-01-01T00:00:00.000Z' },
      { id: 'bad', role: 'bot', content: 'nope' },
      'not-an-object',
    ]);

    expect(messages).toHaveLength(1);
    expect(messages[0].id).toBe('ok');
  });

  it('accepte le rôle user compaction et persiste messageKind', () => {
    const normalized = normalizeChatMessage({
      id: 'sum1',
      role: 'user',
      content: 'Résumé',
      messageKind: 'compaction',
      createdAt: '2026-01-01T00:00:00.000Z',
    });

    expect(normalized).toMatchObject({
      id: 'sum1',
      role: 'user',
      content: 'Résumé',
      messageKind: 'compaction',
    });
  });

  it('accepte le rôle system legacy et persiste messageKind compaction', () => {
    const normalized = normalizeChatMessage({
      id: 'sys1',
      role: 'system',
      content: 'Résumé',
      messageKind: 'compaction',
      createdAt: '2026-01-01T00:00:00.000Z',
    });

    expect(normalized).toMatchObject({
      id: 'sys1',
      role: 'system',
      content: 'Résumé',
      messageKind: 'compaction',
    });
  });

  it('infère messageKind compaction depuis le préfixe i18n sans messageKind stocké', () => {
    const normalized = normalizeChatMessage({
      id: 'sum2',
      role: 'user',
      content: 'Résumé des échanges précédents :\n\nContenu résumé',
      createdAt: '2026-01-01T00:00:00.000Z',
    });

    expect(normalized?.messageKind).toBe('compaction');
  });
});
