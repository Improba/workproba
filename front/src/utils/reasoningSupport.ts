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

export const REASONING_EFFORT_OPTIONS: { value: ReasoningEffort; label: string }[] = [
  { value: 'none', label: 'Aucune' },
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyenne' },
  { value: 'high', label: 'Élevée' },
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

/** Effort par défaut : faible si le modèle le supporte, sinon aucun. */
export function defaultReasoningEffort(
  provider: LlmProviderName,
  model: string,
): ReasoningEffort {
  return supportsReasoning(provider, model) ? 'low' : 'none';
}
