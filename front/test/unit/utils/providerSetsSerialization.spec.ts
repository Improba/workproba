import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { ProviderSet, ProviderSetChatModel } from '@composables/useDesktop.types';
import {
  MISTRAL_BUILTIN_SET,
  WORKPROBA_CLOUD_BUILTIN_SET,
  enrichSetFromBuiltin,
  normalizeStoredSet,
  providerSetToSidecar,
  sidecarSetToProviderSet,
} from '@utils/providerSets';

const FIXTURE_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../services/ai/tests/fixtures/mistral_builtin_sidecar.json',
);

function catalogFields(models: ProviderSetChatModel[] | undefined) {
  return (models ?? []).map((m) => ({
    model: m.model,
    label: m.label,
    hint: m.hint,
    contextWindow: m.contextWindow,
    reasoningEfforts: m.reasoningEfforts,
  }));
}

function sidecarCatalogFields(chat: Record<string, unknown>) {
  const models = chat.models;
  if (!Array.isArray(models)) return [];
  return models.map((item) => {
    const m = item as Record<string, unknown>;
    return {
      model: m.model,
      label: m.label,
      hint: m.hint,
      context_window: m.context_window,
      reasoning_efforts: m.reasoning_efforts,
    };
  });
}

describe('providerSets serialization contract', () => {
    it('providerSetToSidecar produit auth_mode device_bearer pour workproba-cloud', () => {
    const sidecar = providerSetToSidecar(WORKPROBA_CLOUD_BUILTIN_SET);
    expect(sidecar.id).toBe('workproba-cloud');
    expect(sidecar.is_default).toBe(true);
    expect(sidecar.auth_mode).toBe('device_bearer');
    expect(sidecar.ui_mode_locked).toBe(true);
    const chat = sidecar.chat as Record<string, unknown>;
    expect(chat.api_key_ref).toBeUndefined();
    expect(chat.base_url).toBeUndefined();
  });

  it('providerSetToSidecar produit du snake_case avec le catalogue Mistral', () => {
    const sidecar = providerSetToSidecar(MISTRAL_BUILTIN_SET);
    const chat = sidecar.chat as Record<string, unknown>;
    const caps = sidecar.capabilities as Record<string, unknown>;

    expect(sidecar.id).toBe('mistral-default');
    expect(sidecar.is_default).toBe(false);
    expect(sidecar.is_builtin).toBe(true);
    expect(chat.provider).toBe('mistral');
    expect(caps.web_search).toBe(true);
    expect(chat.api_key_ref).toBe('secrets/mistral');
    expect(chat.base_url).toBe('https://api.mistral.ai/v1');

    const catalog = sidecarCatalogFields(chat);
    expect(catalog).toEqual([
      {
        model: 'mistral-small-latest',
        label: 'Mistral Small',
        hint: 'Hybride : chat, code et raisonnement à la demande. Rapide et économique.',
        context_window: 256000,
        reasoning_efforts: ['none', 'high'],
      },
      {
        model: 'mistral-medium-latest',
        label: 'Mistral Medium',
        hint: 'Modèle frontier pour agents, code long et workflows multi-étapes.',
        context_window: 256000,
        reasoning_efforts: ['none', 'high'],
      },
      {
        model: 'mistral-large-latest',
        label: 'Mistral Large',
        hint: 'Flagship multilingue et multimodal. Qualité maximale.',
        context_window: 256000,
        reasoning_efforts: ['none'],
      },
    ]);
  });

  it('round-trip sidecar préserve le catalogue modèles', () => {
    const sidecar = providerSetToSidecar(MISTRAL_BUILTIN_SET);
    const round = sidecarSetToProviderSet(sidecar);

    expect(catalogFields(round.chat.models)).toEqual(
      catalogFields(MISTRAL_BUILTIN_SET.chat.models),
    );
  });

  it('sidecarSetToProviderSet accepte snake_case et camelCase sur les modèles', () => {
    const snake = providerSetToSidecar(MISTRAL_BUILTIN_SET);
    const camelChat = {
      ...(snake.chat as Record<string, unknown>),
      models: (MISTRAL_BUILTIN_SET.chat.models ?? []).map((m) => ({
        model: m.model,
        label: m.label,
        hint: m.hint,
        contextWindow: m.contextWindow,
        reasoningEfforts: m.reasoningEfforts,
      })),
    };
    const fromCamel = sidecarSetToProviderSet({
      ...snake,
      chat: camelChat,
    });

    expect(catalogFields(fromCamel.chat.models)).toEqual(
      catalogFields(MISTRAL_BUILTIN_SET.chat.models),
    );
  });

  it('correspond à la fixture JSON partagée avec le sidecar Python', () => {
    const fixture = JSON.parse(readFileSync(FIXTURE_PATH, 'utf8')) as Record<string, unknown>;
    const fromFixture = sidecarSetToProviderSet(fixture);
    const fromLive = sidecarSetToProviderSet(providerSetToSidecar(MISTRAL_BUILTIN_SET));

    expect(catalogFields(fromFixture.chat.models)).toEqual(
      catalogFields(fromLive.chat.models),
    );
    expect(fromFixture.id).toBe('mistral-default');
    expect((fromFixture.chat as ProviderSet['chat']).provider).toBe('mistral');
  });

  it('normalizeStoredSet parse la fixture snake_case comme un set camelCase enrichi', () => {
    const fixture = JSON.parse(readFileSync(FIXTURE_PATH, 'utf8')) as Record<string, unknown>;
    const normalized = normalizeStoredSet(fixture);

    expect(catalogFields(normalized.chat.models)).toEqual(
      catalogFields(MISTRAL_BUILTIN_SET.chat.models),
    );
    expect(normalized.isDefault).toBe(true);
    expect(normalized.isBuiltin).toBe(true);
  });

  it('enrichSetFromBuiltin restaure authMode device_bearer pour workproba-cloud legacy', () => {
    const legacy = {
      ...WORKPROBA_CLOUD_BUILTIN_SET,
      authMode: undefined,
      uiModeLocked: undefined,
    } as ProviderSet;
    const enriched = enrichSetFromBuiltin(legacy);
    expect(enriched.authMode).toBe('device_bearer');
    expect(enriched.uiModeLocked).toBe(true);
  });
});
