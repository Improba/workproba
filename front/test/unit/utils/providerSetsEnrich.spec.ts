import { describe, expect, it } from 'vitest';
import {
  MISTRAL_BUILTIN_SET,
  enrichSetFromBuiltin,
  resolveSets,
} from '@utils/providerSets';

describe('providerSets enrichSetFromBuiltin', () => {
  it('injecte le catalogue modèles sur un set Mistral stocké sans models', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      chat: { ...MISTRAL_BUILTIN_SET.chat, models: undefined },
    };
    const enriched = enrichSetFromBuiltin(stored);
    expect(enriched.chat.models?.map((m) => m.model)).toEqual([
      'mistral-small-latest',
      'mistral-medium-latest',
      'mistral-large-latest',
    ]);
  });

  it('resolveSets enrichit les sets persistés', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      chat: { ...MISTRAL_BUILTIN_SET.chat, models: undefined },
    };
    const resolved = resolveSets([stored]);
    expect(resolved[0]?.chat.models?.length).toBe(3);
  });

  it('ne modifie pas un set custom sans template builtin', () => {
    const custom = {
      ...MISTRAL_BUILTIN_SET,
      id: 'custom-set',
      isBuiltin: false,
      chat: { ...MISTRAL_BUILTIN_SET.chat, models: undefined },
    };
    const enriched = enrichSetFromBuiltin(custom);
    expect(enriched.chat.models).toBeUndefined();
  });

  it('rafraîchit labels et hints sur un set builtin déjà catalogué', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      chat: {
        ...MISTRAL_BUILTIN_SET.chat,
        models: MISTRAL_BUILTIN_SET.chat.models!.map((m) => ({
          ...m,
          hint: 'Ancienne description',
        })),
      },
    };
    const enriched = enrichSetFromBuiltin(stored);
    expect(enriched.chat.models?.[0]?.hint).toBe(
      'Hybride : chat, code et raisonnement à la demande. Rapide et économique.',
    );
  });
});
