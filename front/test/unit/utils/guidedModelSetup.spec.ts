import { describe, expect, it } from 'vitest';
import {
  applyGuidedCard,
  GUIDED_CARD_PRESETS,
  inferGuidedCard,
} from '@utils/guidedModelSetup';
import type { LlmProviderEntry } from '@composables/useDesktop.types';

describe('guidedModelSetup', () => {
  it('applique mistral avec provider et baseUrl attendus', () => {
    const applied = applyGuidedCard('mistral');

    expect(applied.provider).toBe('mistral');
    expect(applied.baseUrl).toBe('https://api.mistral.ai/v1');
    expect(applied.model).toBe(GUIDED_CARD_PRESETS.mistral.defaultModel);
  });

  it('applique ollama avec provider et baseUrl locaux', () => {
    const applied = applyGuidedCard('ollama');

    expect(applied.provider).toBe('ollama');
    expect(applied.baseUrl).toBe('http://localhost:11434');
  });

  it('applique cloud openai par défaut', () => {
    const applied = applyGuidedCard('cloud', 'openai');

    expect(applied.provider).toBe('openai');
    expect(applied.model).toBe('gpt-4o-mini');
  });

  it('applique cloud anthropic quand demandé', () => {
    const applied = applyGuidedCard('cloud', 'anthropic');

    expect(applied.provider).toBe('anthropic');
    expect(applied.model).toBe('claude-3-5-sonnet-latest');
  });

  it('déduit la carte guidée depuis un provider existant', () => {
    const mistralEntry: LlmProviderEntry = {
      id: 'p1',
      label: 'Mistral',
      provider: 'mistral',
      model: 'mistral-small-latest',
      baseUrl: 'https://api.mistral.ai/v1',
    };

    expect(inferGuidedCard(mistralEntry)).toBe('mistral');
    expect(inferGuidedCard({ ...mistralEntry, provider: 'ollama' })).toBe('ollama');
    expect(inferGuidedCard({ ...mistralEntry, provider: 'openai' })).toBe('cloud');
  });
});
