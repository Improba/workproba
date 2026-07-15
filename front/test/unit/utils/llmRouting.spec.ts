import { describe, expect, it } from 'vitest';
import { MISTRAL_BUILTIN_SET, applySessionOverridesToSet, toChatLlmConfigFromSet, toUtilityLlmConfigFromSet } from '@utils/providerSets';
import { mergeLlmConfigsWithSessionReasoning } from '@utils/llmRouting';

describe('llmRouting', () => {
  it('toChatLlmConfigFromSet clampe medium vers high pour mistral-medium', () => {
    const set = {
      ...MISTRAL_BUILTIN_SET,
      chat: { ...MISTRAL_BUILTIN_SET.chat, model: 'mistral-medium-latest', reasoning: 'medium' as const },
    };
    const chat = toChatLlmConfigFromSet(set);
    expect(chat?.reasoning_effort).toBe('high');
  });

  it('applySessionOverridesToSet clampe medium vers high dans le set routé', () => {
    const routed = applySessionOverridesToSet(
      MISTRAL_BUILTIN_SET,
      'mistral-medium-latest',
      'medium',
    );
    expect(routed.chat.reasoning).toBe('high');
  });

  it('applySessionOverridesToSet + toChatLlmConfigFromSet route le modèle de session', () => {
    const routed = applySessionOverridesToSet(
      MISTRAL_BUILTIN_SET,
      'mistral-medium-latest',
      'high',
    );
    const chat = toChatLlmConfigFromSet(routed);
    expect(chat?.model).toBe('mistral-medium-latest');
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

  it('toUtilityLlmConfigFromSet ignore les overrides de session', () => {
    const routed = applySessionOverridesToSet(
      MISTRAL_BUILTIN_SET,
      'mistral-medium-latest',
      'high',
    );
    const chat = toChatLlmConfigFromSet(routed);
    expect(chat?.model).toBe('mistral-medium-latest');
    expect(chat?.reasoning_effort).toBe('high');

    const utility = toUtilityLlmConfigFromSet(MISTRAL_BUILTIN_SET);
    expect(utility?.model).toBe('mistral-small-latest');
    expect(utility?.reasoning_effort).toBeUndefined();
  });

  it('applySessionOverridesToSet sur mistral-large ignore le raisonnement', () => {
    const routed = applySessionOverridesToSet(
      MISTRAL_BUILTIN_SET,
      'mistral-large-latest',
      'high',
    );
    expect(routed.chat.model).toBe('mistral-large-latest');
    expect(routed.chat.reasoning).toBe('none');
    const chat = toChatLlmConfigFromSet(routed);
    expect(chat?.reasoning_effort).toBeUndefined();
  });

  it('applySessionOverridesToSet sans override reasoning réconcilie le set high sur large', () => {
    const setWithHigh = {
      ...MISTRAL_BUILTIN_SET,
      chat: { ...MISTRAL_BUILTIN_SET.chat, reasoning: 'high' as const },
    };
    const routed = applySessionOverridesToSet(
      setWithHigh,
      'mistral-large-latest',
      null,
    );
    expect(routed.chat.reasoning).toBe('none');
  });
});
