import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';

const MISTRAL_REASONING_MODELS = [
  'mistral-small-latest',
  'mistral-medium-3-5',
  'mistral-medium-latest',
  'mistral-large-latest',
];

const OPENAI_REASONING_RE = /gpt-5|o1|o3|o4|o-series/i;
const ANTHROPIC_REASONING_RE = /claude-3-7|claude-opus-4|claude-sonnet-4|opus|sonnet-4/i;

const ALL_EFFORTS: ReasoningEffort[] = ['none', 'low', 'medium', 'high'];

export const REASONING_EFFORT_OPTIONS: { value: ReasoningEffort; label: string }[] = [
  { value: 'none', label: 'Aucun' },
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
];

function mistralSupportsReasoning(model: string): boolean {
  const normalized = model.toLowerCase();
  if (MISTRAL_REASONING_MODELS.some((m) => normalized.includes(m))) return true;
  if (normalized.includes('medium') && normalized.includes('-latest')) return true;
  if (normalized.includes('large') && normalized.includes('-latest')) return true;
  if (normalized.includes('small') && normalized.includes('-latest')) return true;
  return false;
}

/** Indique si le couple provider/modèle supporte le raisonnement ajustable. */
export function supportsReasoning(provider: LlmProviderName, model: string): boolean {
  const normalized = model.trim().toLowerCase();
  if (!normalized) return false;

  switch (provider) {
    case 'mistral':
      return mistralSupportsReasoning(normalized);
    case 'openai':
    case 'openai_compat':
      return OPENAI_REASONING_RE.test(normalized);
    case 'anthropic':
      return ANTHROPIC_REASONING_RE.test(normalized);
    case 'vllm':
    case 'ollama':
    default:
      return false;
  }
}

/**
 * Efforts de raisonnement réellement acceptés par le couple provider/modèle.
 *
 * L'API Mistral n'accepte que `none` et `high` pour `mistral-small-latest`
 * (renvoie une 400 `reasoning_effort='low' is not supported` sinon). On filtre
 * donc les options proposées par modèle pour ne présenter que ce qui marche.
 */
export function supportedReasoningEfforts(
  provider: LlmProviderName,
  model: string,
): ReasoningEffort[] {
  if (!supportsReasoning(provider, model)) return ['none'];

  switch (provider) {
    case 'mistral': {
      const normalized = model.trim().toLowerCase();
      if (normalized.includes('small')) return ['none', 'high'];
      return ALL_EFFORTS;
    }
    case 'openai':
    case 'openai_compat':
    case 'anthropic':
      return ALL_EFFORTS;
    case 'vllm':
    case 'ollama':
    default:
      return ['none'];
  }
}

/**
 * Effort par défaut : `low` quand le modèle le supporte (légère réflexion),
 * sinon `none` (certains modèles comme `mistral-small-latest` n'acceptent que
 * `none`/`high`, on évite donc de forcer `high` sur chaque message).
 */
export function defaultReasoningEffort(
  provider: LlmProviderName,
  model: string,
): ReasoningEffort {
  const efforts = supportedReasoningEfforts(provider, model);
  return efforts.includes('low') ? 'low' : 'none';
}

/** Ramène un effort à une valeur supportée par le modèle (fallback sûr). */
export function clampReasoningEffort(
  provider: LlmProviderName,
  model: string,
  effort: ReasoningEffort,
): ReasoningEffort {
  const efforts = supportedReasoningEfforts(provider, model);
  return efforts.includes(effort) ? effort : defaultReasoningEffort(provider, model);
}
