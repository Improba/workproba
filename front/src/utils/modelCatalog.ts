import type { LlmProviderName, ProviderSet } from '@composables/useDesktop.types';
import {
  contextWindowForSet,
  findSetModel,
  hasSetModelChoice,
  isModelApplicableForSet,
  modelsForSet,
} from '@utils/providerSetModels';

export const DEFAULT_CONTEXT_WINDOW = 16384;

export interface ModelOption {
  /** Identifiant exact envoyé au provider. */
  model: string;
  /** Libellé lisible pour un utilisateur non technique. */
  label: string;
  /** Courte description orientée usage. */
  hint?: string;
  /** Taille de fenêtre de contexte en tokens. */
  contextWindow?: number;
}

/**
 * Quelques modèles suggérés par provider, présentés en clair pour un
 * utilisateur non technique. L'objectif n'est pas d'être exhaustif mais
 * d'offrir un choix rapide et compréhensible depuis le compositeur.
 *
 * Pour les providers à modèle libre (openai_compat, ollama, vllm…), on ne
 * propose pas de liste fixe : l'utilisateur garde le modèle qu'il a configuré
 * dans les réglages.
 */
const PROVIDER_MODELS: Partial<Record<LlmProviderName, ModelOption[]>> = {
  mistral: [
    { model: 'mistral-small-latest', label: 'Mistral Small', hint: 'Hybride : chat, code et raisonnement à la demande. Rapide et économique.', contextWindow: 256000 },
    { model: 'mistral-medium-latest', label: 'Mistral Medium', hint: 'Modèle frontier pour agents, code long et workflows multi-étapes.', contextWindow: 256000 },
    { model: 'mistral-large-latest', label: 'Mistral Large', hint: 'Flagship multilingue et multimodal. Qualité maximale.', contextWindow: 256000 },
  ],
  openai: [
    { model: 'gpt-4o-mini', label: 'GPT-4o mini', hint: 'Rapide et économique', contextWindow: 128000 },
    { model: 'gpt-4o', label: 'GPT-4o', hint: 'Polyvalent', contextWindow: 128000 },
    { model: 'o1', label: 'o1', hint: 'Raisonnement avancé', contextWindow: 200000 },
  ],
  anthropic: [
    { model: 'claude-3-5-sonnet-latest', label: 'Claude 3.5 Sonnet', hint: 'Polyvalent', contextWindow: 200000 },
    { model: 'claude-3-7-sonnet-latest', label: 'Claude 3.7 Sonnet', hint: 'Raisonnement avancé', contextWindow: 200000 },
    { model: 'claude-opus-4-latest', label: 'Claude Opus 4', hint: 'Le plus puissant', contextWindow: 200000 },
  ],
};

/** Modèles suggérés pour un provider (liste vide si non applicable). */
export function modelsForProvider(
  provider: LlmProviderName,
  set?: ProviderSet | null,
): ModelOption[] {
  if (set) return modelsForSet(set);
  return PROVIDER_MODELS[provider] ?? [];
}

/** Indique si le provider propose un choix de modèles depuis le compositeur. */
export function hasModelChoice(
  provider: LlmProviderName,
  set?: ProviderSet | null,
): boolean {
  if (set) return hasSetModelChoice(set);
  return modelsForProvider(provider).length > 0;
}

/**
 * Indique si un modèle est utilisable par le provider donné. Pour les
 * providers à modèle libre (sans catalogue), on accepte tout modèle non vide
 * (on ne peut pas valider). Pour les providers catalogués, le modèle doit
 * figurer dans le catalogue.
 *
 * Sert à invalider un `model` persisté par session quand l'utilisateur a
 * changé de provider entre-temps (ex. session Mistral rouverte sous OpenAI).
 */
export function isModelApplicable(
  provider: LlmProviderName,
  model: string | null | undefined,
  set?: ProviderSet | null,
): boolean {
  if (set) return isModelApplicableForSet(set, model);
  const list = PROVIDER_MODELS[provider];
  const value = (model ?? '').trim().toLowerCase();
  if (!value) return false;
  if (!list) return true;
  return list.some((opt) => opt.model.toLowerCase() === value);
}

/**
 * Fenêtre de contexte en tokens pour un couple (provider, modèle).
 * Retourne la valeur cataloguée ou {@link DEFAULT_CONTEXT_WINDOW}.
 */
export function contextWindowFor(
  provider: LlmProviderName,
  model: string | null | undefined,
  set?: ProviderSet | null,
): number {
  if (set) return contextWindowForSet(set, model);
  const list = PROVIDER_MODELS[provider];
  const value = (model ?? '').trim().toLowerCase();
  if (!list || !value) return DEFAULT_CONTEXT_WINDOW;
  const match = list.find((opt) => opt.model.toLowerCase() === value);
  return match?.contextWindow ?? DEFAULT_CONTEXT_WINDOW;
}

/**
 * Libellé lisible d'un modèle. On utilise le catalogue quand on trouve une
 * correspondance (insensible à la casse), sinon on retraite l'identifiant
 * (ex. "mistral-small-latest" -> "Mistral Small").
 */
export function friendlyModelLabel(
  provider: LlmProviderName,
  model: string,
  set?: ProviderSet | null,
): string {
  const raw = (model ?? '').trim();
  if (!raw) return 'Modèle';

  const setMatch = set ? findSetModel(set, raw) : null;
  if (setMatch) return setMatch.label;

  const list = PROVIDER_MODELS[provider];
  if (list) {
    const lower = raw.toLowerCase();
    const match = list.find((m) => m.model.toLowerCase() === lower);
    if (match) return match.label;
  }
  return prettifyModelId(raw);
}

function prettifyModelId(id: string): string {
  const ACRO = /^(gpt|o\d*|glm|llama|qwen|mistral|claude)$/i;
  return id
    .split(/[-_]/)
    .filter((part) => part.toLowerCase() !== 'latest')
    .map((part) => (ACRO.test(part) ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1)))
    .join(' ');
}
