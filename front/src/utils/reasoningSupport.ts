import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';

const MISTRAL_REASONING_MODELS = [
  'mistral-small-latest',
  'mistral-medium-3-5',
  'mistral-medium-latest',
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
 * L'API Mistral n'accepte que `none` et `high` pour les modèles à raisonnement
 * ajustable (`mistral-small-latest`, `mistral-medium-3-5`, alias `mistral-medium-latest`).
 * donc les options proposées par modèle pour ne présenter que ce qui marche.
 */
export function supportedReasoningEfforts(
  provider: LlmProviderName,
  model: string,
): ReasoningEffort[] {
  if (!supportsReasoning(provider, model)) return ['none'];

  switch (provider) {
    case 'mistral':
      return ['none', 'high'];
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
 * sinon `none` (modèles Mistral à raisonnement : API binaire none/high).
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
  if (efforts.includes(effort)) return effort;
  if (effort !== 'none' && efforts.includes('high')) return 'high';
  return defaultReasoningEffort(provider, model);
}
