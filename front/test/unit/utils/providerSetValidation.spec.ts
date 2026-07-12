import { describe, expect, it } from 'vitest';
import { MISTRAL_BUILTIN_SET, OLLAMA_BUILTIN_SET } from '@utils/providerSets';
import {
  validateProviderSetChatReady,
  validateProviderSetEmbeddingsReady,
} from '@utils/providerSetValidation';

describe('providerSetValidation', () => {
  it('exige une clé API pour Mistral sans clé renseignée', () => {
    const check = validateProviderSetChatReady(MISTRAL_BUILTIN_SET);
    expect(check.ok).toBe(false);
    if (!check.ok) expect(check.reason).toBe('missing_api_key');
  });

  it('accepte Mistral avec clé API', () => {
    const set = {
      ...MISTRAL_BUILTIN_SET,
      chat: { ...MISTRAL_BUILTIN_SET.chat, apiKey: 'sk-test' },
    };
    expect(validateProviderSetChatReady(set).ok).toBe(true);
  });

  it('n’exige pas de clé pour Ollama local', () => {
    expect(validateProviderSetChatReady(OLLAMA_BUILTIN_SET).ok).toBe(true);
    expect(validateProviderSetEmbeddingsReady(OLLAMA_BUILTIN_SET).ok).toBe(true);
  });
});
