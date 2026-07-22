import { describe, expect, it } from 'vitest';
import {
  BUILTIN_PROVIDER_SETS,
  MISTRAL_BUILTIN_SET,
  OLLAMA_BUILTIN_SET,
  WORKPROBA_CLOUD_BUILTIN_SET,
  defaultStateFromSet,
  effectiveReasoningEffortFromSet,
  toChatLlmConfigFromSet,
} from '@utils/providerSets';

describe('provider set default state', () => {
  it('workproba-cloud déclare medium + high', () => {
    expect(defaultStateFromSet(WORKPROBA_CLOUD_BUILTIN_SET)).toEqual({
      model: 'mistral-medium-latest',
      reasoningEffort: 'high',
    });
  });

  it('mistral-default déclare medium + high', () => {
    expect(defaultStateFromSet(MISTRAL_BUILTIN_SET)).toEqual({
      model: 'mistral-medium-latest',
      reasoningEffort: 'high',
    });
  });

  it('ollama-local déclare un effort explicite (pas auto)', () => {
    expect(OLLAMA_BUILTIN_SET.chat.reasoning).toBe('none');
    expect(defaultStateFromSet(OLLAMA_BUILTIN_SET)).toEqual({
      model: 'llama3.2',
      reasoningEffort: 'none',
    });
  });

  it('aucun builtin n’utilise auto comme default state', () => {
    for (const set of BUILTIN_PROVIDER_SETS) {
      expect(set.chat.reasoning).not.toBe('auto');
      expect(set.chat.reasoning).toBeTruthy();
    }
  });

  it('toChatLlmConfigFromSet envoie reasoning_effort high pour cloud', () => {
    const cfg = toChatLlmConfigFromSet(WORKPROBA_CLOUD_BUILTIN_SET);
    expect(cfg?.model).toBe('mistral-medium-latest');
    expect(cfg?.reasoning_effort).toBe('high');
  });

  it('effectiveReasoningEffortFromSet sans override lit le default state', () => {
    expect(effectiveReasoningEffortFromSet(WORKPROBA_CLOUD_BUILTIN_SET)).toBe(
      'high',
    );
  });

  it('effectiveReasoningEffortFromSet avec auto legacy reprend le default state', () => {
    const legacy = {
      ...WORKPROBA_CLOUD_BUILTIN_SET,
      chat: {
        ...WORKPROBA_CLOUD_BUILTIN_SET.chat,
        reasoning: 'auto' as const,
      },
    };
    expect(effectiveReasoningEffortFromSet(legacy)).toBe('high');
  });
});
