import type { LlmProviderName, ProviderSet, ProviderSetChatModel } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import type { ModelOption } from '@utils/modelCatalog';
import {
  clampReasoningEffort,
  defaultReasoningEffort,
  supportedReasoningEfforts,
} from '@utils/reasoningSupport';

const DEFAULT_CONTEXT_WINDOW = 16384;

const LEGACY_CONTEXT_WINDOWS: Partial<Record<LlmProviderName, Record<string, number>>> = {
  mistral: {
    'mistral-small-latest': 256000,
    'mistral-medium-latest': 256000,
    'mistral-large-latest': 256000,
  },
  openai: {
    'gpt-4o-mini': 128000,
    'gpt-4o': 128000,
    o1: 200000,
  },
  anthropic: {
    'claude-3-5-sonnet-latest': 200000,
    'claude-3-7-sonnet-latest': 200000,
    'claude-opus-4-latest': 200000,
  },
};

const LEGACY_MODEL_IDS: Partial<Record<LlmProviderName, string[]>> = {
  mistral: ['mistral-small-latest', 'mistral-medium-latest', 'mistral-large-latest'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'o1'],
  anthropic: [
    'claude-3-5-sonnet-latest',
    'claude-3-7-sonnet-latest',
    'claude-opus-4-latest',
  ],
};

function setModels(set: ProviderSet | null | undefined): ProviderSetChatModel[] | null {
  const models = set?.chat.models;
  return models?.length ? models : null;
}

function providerForSet(set: ProviderSet | null | undefined) {
  return set?.chat.provider ?? null;
}

function legacyContextWindow(provider: LlmProviderName, model: string): number {
  const value = model.trim().toLowerCase();
  const map = LEGACY_CONTEXT_WINDOWS[provider];
  if (!map || !value) return DEFAULT_CONTEXT_WINDOW;
  return map[value] ?? DEFAULT_CONTEXT_WINDOW;
}

function legacyModelsForProvider(provider: LlmProviderName): ModelOption[] {
  const ids = LEGACY_MODEL_IDS[provider] ?? [];
  return ids.map((id) => ({
    model: id,
    label: id,
    contextWindow: legacyContextWindow(provider, id),
  }));
}

function legacyIsModelApplicable(provider: LlmProviderName, model: string): boolean {
  const list = LEGACY_MODEL_IDS[provider];
  const value = model.trim().toLowerCase();
  if (!value) return false;
  if (!list) return true;
  return list.some((id) => id.toLowerCase() === value);
}

/** Cherche un modèle catalogué dans le set actif. */
export function findSetModel(
  set: ProviderSet | null | undefined,
  model: string,
): ProviderSetChatModel | null {
  const list = setModels(set);
  if (!list) return null;
  const normalized = model.trim().toLowerCase();
  if (!normalized) return null;
  return list.find((entry) => entry.model.toLowerCase() === normalized) ?? null;
}

function toModelOption(entry: ProviderSetChatModel): ModelOption {
  return {
    model: entry.model,
    label: entry.label,
    hint: entry.hint,
    contextWindow: entry.contextWindow,
  };
}

/** Modèles suggérés pour le set (catalogue set ou legacy provider). */
export function modelsForSet(set: ProviderSet | null | undefined): ModelOption[] {
  const list = setModels(set);
  if (list) return list.map(toModelOption);
  const provider = providerForSet(set);
  return provider ? legacyModelsForProvider(provider) : [];
}

/** Efforts de raisonnement supportés pour un modèle du set. */
export function supportedReasoningEffortsForSet(
  set: ProviderSet | null | undefined,
  model: string,
): ReasoningEffort[] {
  const list = setModels(set);
  if (list) {
    const entry = findSetModel(set, model);
    if (entry?.reasoningEfforts?.length) return entry.reasoningEfforts;
    // Catalogue présent mais modèle inconnu : pas de raisonnement ajustable.
    return ['none'];
  }
  const provider = providerForSet(set);
  return provider ? supportedReasoningEfforts(provider, model) : ['none'];
}

/** Indique si le modèle du set supporte un raisonnement ajustable. */
export function supportsReasoningForSet(
  set: ProviderSet | null | undefined,
  model: string,
): boolean {
  const efforts = supportedReasoningEffortsForSet(set, model);
  return efforts.length > 1;
}

/** Ramène un effort à une valeur supportée par le catalogue du set. */
export function clampReasoningEffortForSet(
  set: ProviderSet | null | undefined,
  model: string,
  effort: ReasoningEffort,
): ReasoningEffort {
  const list = setModels(set);
  if (list) {
    const entry = findSetModel(set, model);
    if (entry?.reasoningEfforts?.length) {
      const efforts = entry.reasoningEfforts;
      if (efforts.includes(effort)) return effort;
      if (effort !== 'none' && efforts.includes('high')) return 'high';
      return efforts.includes('low') ? 'low' : 'none';
    }
    return 'none';
  }
  const provider = providerForSet(set);
  return provider ? clampReasoningEffort(provider, model, effort) : 'none';
}

/** Effort par défaut pour un modèle du set. */
export function defaultReasoningEffortForSet(
  set: ProviderSet | null | undefined,
  model: string,
): ReasoningEffort {
  const list = setModels(set);
  if (list) {
    const entry = findSetModel(set, model);
    if (entry?.reasoningEfforts?.length) {
      const efforts = entry.reasoningEfforts;
      return efforts.includes('low') ? 'low' : 'none';
    }
    return 'none';
  }
  const provider = providerForSet(set);
  return provider ? defaultReasoningEffort(provider, model) : 'none';
}

/** Fenêtre de contexte en tokens pour un modèle du set. */
export function contextWindowForSet(
  set: ProviderSet | null | undefined,
  model: string | null | undefined,
): number {
  const entry = findSetModel(set, model ?? '');
  if (entry?.contextWindow) return entry.contextWindow;
  const provider = providerForSet(set);
  return provider ? legacyContextWindow(provider, model ?? '') : DEFAULT_CONTEXT_WINDOW;
}

/** Indique si un modèle est utilisable dans le set actif. */
export function isModelApplicableForSet(
  set: ProviderSet | null | undefined,
  model: string | null | undefined,
): boolean {
  const list = setModels(set);
  const value = (model ?? '').trim().toLowerCase();
  if (!value) return false;
  if (list) {
    return list.some((entry) => entry.model.toLowerCase() === value);
  }
  const provider = providerForSet(set);
  return provider ? legacyIsModelApplicable(provider, value) : false;
}

/** Indique si le set propose un choix de modèles dans le compositeur. */
export function hasSetModelChoice(set: ProviderSet | null | undefined): boolean {
  const list = setModels(set);
  if (list) return list.length > 0;
  const provider = providerForSet(set);
  return provider ? legacyModelsForProvider(provider).length > 0 : false;
}
