import type { LlmProviderEntry, LlmProviderName } from '@composables/useDesktop.types';

export type GuidedCardId = 'mistral' | 'ollama' | 'cloud';

export type CloudProviderName = 'openai' | 'anthropic';

export interface GuidedCardPreset {
  provider: LlmProviderName;
  baseUrl: string;
  label: string;
  defaultModel: string;
  embeddingModel: string;
}

export const GUIDED_CARD_PRESETS: Record<GuidedCardId, GuidedCardPreset> = {
  mistral: {
    provider: 'mistral',
    baseUrl: 'https://api.mistral.ai/v1',
    label: 'Mistral',
    defaultModel: 'mistral-small-latest',
    embeddingModel: 'mistral-embed',
  },
  ollama: {
    provider: 'ollama',
    baseUrl: 'http://localhost:11434',
    label: 'Local (Ollama)',
    defaultModel: 'mistral',
    embeddingModel: 'nomic-embed-text',
  },
  cloud: {
    provider: 'openai',
    baseUrl: '',
    label: 'Cloud tiers',
    defaultModel: 'gpt-4o-mini',
    embeddingModel: 'text-embedding-3-small',
  },
};

export const CLOUD_PROVIDER_PRESETS: Record<CloudProviderName, Partial<GuidedCardPreset>> = {
  openai: {
    provider: 'openai',
    baseUrl: '',
    defaultModel: 'gpt-4o-mini',
    embeddingModel: 'text-embedding-3-small',
  },
  anthropic: {
    provider: 'anthropic',
    baseUrl: '',
    defaultModel: 'claude-3-5-sonnet-latest',
    embeddingModel: '',
  },
};

export interface ModelOption {
  value: string;
  label: string;
}

export const MISTRAL_MODEL_OPTIONS: ModelOption[] = [
  { value: 'mistral-small-latest', label: 'Mistral Small, rapide et économique' },
  { value: 'mistral-medium-latest', label: 'Mistral Medium, équilibré' },
  { value: 'mistral-large-latest', label: 'Mistral Large, le plus capable' },
];

export const OPENAI_MODEL_OPTIONS: ModelOption[] = [
  { value: 'gpt-4o-mini', label: 'GPT-4o mini, rapide et économique' },
  { value: 'gpt-4o', label: 'GPT-4o, le plus capable' },
];

export const ANTHROPIC_MODEL_OPTIONS: ModelOption[] = [
  { value: 'claude-3-5-haiku-latest', label: 'Claude Haiku, rapide et économique' },
  { value: 'claude-3-5-sonnet-latest', label: 'Claude Sonnet, le plus capable' },
];

export function isCloudProvider(provider: LlmProviderName): provider is CloudProviderName {
  return provider === 'openai' || provider === 'anthropic';
}

export function inferGuidedCard(entry: LlmProviderEntry | null | undefined): GuidedCardId {
  if (!entry) return 'mistral';
  if (entry.provider === 'mistral') return 'mistral';
  if (entry.provider === 'ollama') return 'ollama';
  if (isCloudProvider(entry.provider)) return 'cloud';
  return 'mistral';
}

export function inferCloudProvider(entry: LlmProviderEntry | null | undefined): CloudProviderName {
  if (entry?.provider === 'anthropic') return 'anthropic';
  return 'openai';
}

export function applyGuidedCard(
  card: GuidedCardId,
  cloudProvider: CloudProviderName = 'openai',
): {
  provider: LlmProviderName;
  baseUrl: string;
  label: string;
  model: string;
  embeddingModel: string | null;
} {
  if (card === 'cloud') {
    const cloudPreset = CLOUD_PROVIDER_PRESETS[cloudProvider];
    return {
      provider: cloudPreset.provider ?? 'openai',
      baseUrl: cloudPreset.baseUrl ?? '',
      label: cloudProvider === 'anthropic' ? 'Anthropic' : 'OpenAI',
      model: cloudPreset.defaultModel ?? 'gpt-4o-mini',
      embeddingModel: cloudPreset.embeddingModel ?? null,
    };
  }

  const preset = GUIDED_CARD_PRESETS[card];
  return {
    provider: preset.provider,
    baseUrl: preset.baseUrl,
    label: preset.label,
    model: preset.defaultModel,
    embeddingModel: preset.embeddingModel,
  };
}

export function normalizeOllamaBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim() || 'http://localhost:11434';
  return trimmed.replace(/\/v1\/?$/, '');
}
