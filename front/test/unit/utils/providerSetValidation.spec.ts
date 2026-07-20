import { describe, expect, it } from 'vitest';
import {
  MISTRAL_BUILTIN_SET,
  OLLAMA_BUILTIN_SET,
  WORKPROBA_CLOUD_BUILTIN_SET,
} from '@utils/providerSets';
import {
  canActivateProviderSet,
  getSetActivationReadiness,
  pickActivatableReadingSet,
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

  it('refuse workproba-cloud sans contexte cloud (fail-closed)', () => {
    const check = validateProviderSetChatReady(WORKPROBA_CLOUD_BUILTIN_SET);
    expect(check.ok).toBe(false);
    if (!check.ok) expect(check.reason).toBe('cloud_not_enrolled');
    const embedCheck = validateProviderSetEmbeddingsReady(WORKPROBA_CLOUD_BUILTIN_SET);
    expect(embedCheck.ok).toBe(false);
    if (!embedCheck.ok) expect(embedCheck.reason).toBe('cloud_not_enrolled');
  });

  it('accepte workproba-cloud enrollé avec quota ok', () => {
    const cloud = {
      enrolled: true,
      reachable: true,
      subscribed: true,
      quotaExceeded: false,
    };
    expect(validateProviderSetChatReady(WORKPROBA_CLOUD_BUILTIN_SET, cloud).ok).toBe(true);
    expect(validateProviderSetEmbeddingsReady(WORKPROBA_CLOUD_BUILTIN_SET, cloud).ok).toBe(true);
  });

  it('signale cloud_not_enrolled quand le contexte cloud est fourni', () => {
    const check = validateProviderSetChatReady(WORKPROBA_CLOUD_BUILTIN_SET, {
      enrolled: false,
      reachable: true,
    });
    expect(check.ok).toBe(false);
    if (!check.ok) expect(check.reason).toBe('cloud_not_enrolled');
  });

  it('signale quota_exceeded depuis le contexte cloud', () => {
    const check = validateProviderSetChatReady(WORKPROBA_CLOUD_BUILTIN_SET, {
      enrolled: true,
      reachable: true,
      subscribed: true,
      quotaExceeded: true,
    });
    expect(check.ok).toBe(false);
    if (!check.ok) expect(check.reason).toBe('quota_exceeded');
  });

  describe('getSetActivationReadiness / canActivateProviderSet', () => {
    it('refuse workproba-cloud sans contexte cloud (fail-closed)', () => {
      const check = getSetActivationReadiness(WORKPROBA_CLOUD_BUILTIN_SET);
      expect(check.ok).toBe(false);
      if (!check.ok) expect(check.reason).toBe('cloud_not_enrolled');
      expect(canActivateProviderSet(WORKPROBA_CLOUD_BUILTIN_SET)).toBe(false);
    });

    it('refuse workproba-cloud non enrollé', () => {
      const check = getSetActivationReadiness(WORKPROBA_CLOUD_BUILTIN_SET, {
        cloud: { enrolled: false, reachable: true },
      });
      expect(check.ok).toBe(false);
      if (!check.ok) expect(check.reason).toBe('cloud_not_enrolled');
    });

    it('accepte workproba-cloud enrollé avec quota ok', () => {
      const cloud = {
        enrolled: true,
        reachable: true,
        subscribed: true,
        quotaExceeded: false,
      };
      expect(getSetActivationReadiness(WORKPROBA_CLOUD_BUILTIN_SET, { cloud }).ok).toBe(true);
      expect(canActivateProviderSet(WORKPROBA_CLOUD_BUILTIN_SET, { cloud })).toBe(true);
    });

    it('exige une clé API pour Mistral sans clé renseignée', () => {
      const check = getSetActivationReadiness(MISTRAL_BUILTIN_SET);
      expect(check.ok).toBe(false);
      if (!check.ok) expect(check.reason).toBe('missing_api_key');
    });

    it('accepte Mistral avec clé API', () => {
      const set = {
        ...MISTRAL_BUILTIN_SET,
        chat: { ...MISTRAL_BUILTIN_SET.chat, apiKey: 'sk-test' },
      };
      expect(getSetActivationReadiness(set).ok).toBe(true);
    });

    it('accepte Ollama local sans contexte cloud', () => {
      expect(getSetActivationReadiness(OLLAMA_BUILTIN_SET).ok).toBe(true);
      expect(canActivateProviderSet(OLLAMA_BUILTIN_SET)).toBe(true);
    });
  });

  describe('pickActivatableReadingSet', () => {
    it('préfère un set ready plutôt que cloud non enrollé', () => {
      const mistralWithKey = {
        ...MISTRAL_BUILTIN_SET,
        chat: { ...MISTRAL_BUILTIN_SET.chat, apiKey: 'sk-test' },
      };
      const picked = pickActivatableReadingSet(
        [WORKPROBA_CLOUD_BUILTIN_SET, mistralWithKey],
        'document',
        { cloud: { enrolled: false, reachable: true } },
      );
      expect(picked?.id).toBe(mistralWithKey.id);
    });

    it('choisit cloud enrollé quand c\'est le seul ready avec lecture', () => {
      const cloud = {
        enrolled: true,
        reachable: true,
        subscribed: true,
        quotaExceeded: false,
      };
      const picked = pickActivatableReadingSet(
        [WORKPROBA_CLOUD_BUILTIN_SET, MISTRAL_BUILTIN_SET],
        'document',
        { cloud },
      );
      expect(picked?.id).toBe(WORKPROBA_CLOUD_BUILTIN_SET.id);
    });

    it('retourne null si aucun set activable ne lit les pièces jointes', () => {
      const picked = pickActivatableReadingSet(
        [OLLAMA_BUILTIN_SET],
        'document',
        null,
      );
      expect(picked).toBeNull();
    });
  });
});
