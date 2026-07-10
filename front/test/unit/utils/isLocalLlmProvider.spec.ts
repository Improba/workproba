import { describe, expect, it } from 'vitest';
import { isLocalLlmProvider } from '../../../src/utils/isLocalLlmProvider';
import type { LlmProviderEntry } from '../../../src/composables/useDesktop.types';

function entry(overrides: Partial<LlmProviderEntry>): LlmProviderEntry {
  return {
    id: 'test',
    label: 'Test',
    provider: 'openai',
    model: 'gpt-4',
    ...overrides,
  };
}

describe('isLocalLlmProvider', () => {
  it('retourne true sans provider actif', () => {
    expect(isLocalLlmProvider(null)).toBe(true);
    expect(isLocalLlmProvider(undefined)).toBe(true);
  });

  it('détecte Ollama et vLLM comme locaux', () => {
    expect(isLocalLlmProvider(entry({ provider: 'ollama' }))).toBe(true);
    expect(isLocalLlmProvider(entry({ provider: 'vllm' }))).toBe(true);
  });

  it('détecte un endpoint localhost comme local', () => {
    expect(
      isLocalLlmProvider(
        entry({
          provider: 'openai_compat',
          baseUrl: 'http://127.0.0.1:11434/v1',
        }),
      ),
    ).toBe(true);
  });

  it('considère OpenAI distant comme cloud', () => {
    expect(isLocalLlmProvider(entry({ provider: 'openai' }))).toBe(false);
    expect(
      isLocalLlmProvider(
        entry({
          provider: 'mistral',
          baseUrl: 'https://api.mistral.ai',
        }),
      ),
    ).toBe(false);
  });
});
