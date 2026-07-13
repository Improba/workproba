import { describe, expect, it } from 'vitest';
import { estimateMessagesTokens, estimateTokens } from '@utils/tokenEstimate';

describe('tokenEstimate', () => {
  it('estimateTokens applique chars/4', () => {
    expect(estimateTokens('abcd')).toBe(1);
    expect(estimateTokens('')).toBe(0);
  });

  it('estimateMessagesTokens inclut thinking et toolCalls', () => {
    const tokens = estimateMessagesTokens([
      {
        role: 'assistant',
        content: 'abcd',
        thinking: 'efgh',
        toolCalls: [{ args: { path: 'x' }, result: { ok: true } }],
      },
    ]);
    expect(tokens).toBeGreaterThan(estimateTokens('abcd'));
  });
});
