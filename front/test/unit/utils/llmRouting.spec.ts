import { describe, expect, it } from 'vitest';
import { MISTRAL_BUILTIN_SET, applySessionOverridesToSet, toChatLlmConfigFromSet } from '@utils/providerSets';
import { mergeLlmConfigsWithSessionReasoning } from '@utils/llmRouting';

describe('llmRouting', () => {
  it('applySessionOverridesToSet + toChatLlmConfigFromSet route le modèle de session', () => {
    const routed = applySessionOverridesToSet(
      MISTRAL_BUILTIN_SET,
      'mistral-large-latest',
      'high',
    );
    const chat = toChatLlmConfigFromSet(routed);
    expect(chat?.model).toBe('mistral-large-latest');
    expect(chat?.reasoning_effort).toBe('high');
  });

  it('mergeLlmConfigsWithSessionReasoning substitue le modèle de session (legacy)', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: {
          provider: 'mistral',
          model: 'mistral-small-latest',
          base_url: null,
          api_key: null,
        },
        embedding: null,
      },
      null,
      'mistral-large-latest',
    );
    expect(merged.chat?.model).toBe('mistral-large-latest');
  });
});
