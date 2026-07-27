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

  it('injecte le catalogue Mistral sur un set custom mistral sans models', () => {
    const custom = {
      ...MISTRAL_BUILTIN_SET,
      id: 'custom-set',
      isBuiltin: false,
      chat: { ...MISTRAL_BUILTIN_SET.chat, models: undefined },
    };
    const enriched = enrichSetFromBuiltin(custom);
    expect(enriched.chat.models?.map((m) => m.model)).toEqual([
      'mistral-small-latest',
      'mistral-medium-latest',
      'mistral-large-latest',
    ]);
  });

  it('injecte un catalogue mono-modèle sur un set openai_compat sans models', () => {
    const custom = {
      id: 'custom-openai',
      name: 'Compat',
      description: '',
      badges: [] as string[],
      chat: {
        provider: 'openai_compat' as const,
        model: 'gpt-4o-mini',
        baseUrl: 'https://api.example.com/v1',
        reasoning: 'none' as const,
      },
      embeddings: null,
      ocr: null,
      vision: { mode: 'none' as const },
      capabilities: {
        reasoning: 'low' as const,
        vision: false,
        tools: true,
        webSearch: false,
      },
      isDefault: false,
      isBuiltin: false,
    };
    const enriched = enrichSetFromBuiltin(custom);
    expect(enriched.chat.models?.map((m) => m.model)).toEqual(['gpt-4o-mini']);
  });

  it('migre small+auto vers medium+high sur les builtins Mistral', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      chat: {
        ...MISTRAL_BUILTIN_SET.chat,
        model: 'mistral-small-latest' as const,
        reasoning: 'auto' as const,
      },
    };
    const enriched = enrichSetFromBuiltin(stored);
    expect(enriched.chat.model).toBe('mistral-medium-latest');
    expect(enriched.chat.reasoning).toBe('high');
  });

  it('ne force pas medium+high si le builtin a déjà un modèle choisi', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      chat: {
        ...MISTRAL_BUILTIN_SET.chat,
        model: 'mistral-large-latest' as const,
        reasoning: 'none' as const,
      },
    };
    const enriched = enrichSetFromBuiltin(stored);
    expect(enriched.chat.model).toBe('mistral-large-latest');
    expect(enriched.chat.reasoning).toBe('none');
  });
});
