import { describe, expect, it } from 'vitest';
import {
  defaultReasoningEffort,
  supportsReasoning,
} from '@utils/reasoningSupport';

describe('reasoningSupport', () => {
  describe('supportsReasoning', () => {
    it('accepte les modèles Mistral récents', () => {
      expect(supportsReasoning('mistral', 'mistral-small-latest')).toBe(true);
      expect(supportsReasoning('mistral', 'mistral-medium-latest')).toBe(true);
      expect(supportsReasoning('mistral', 'mistral-large-latest')).toBe(true);
      expect(supportsReasoning('mistral', 'mistral-medium-3-5')).toBe(true);
    });

    it('refuse mistral sans motif raisonnement', () => {
      expect(supportsReasoning('mistral', 'mistral-embed')).toBe(false);
    });

    it('accepte les modèles OpenAI de raisonnement', () => {
      expect(supportsReasoning('openai', 'gpt-5-preview')).toBe(true);
      expect(supportsReasoning('openai_compat', 'o3-mini')).toBe(true);
      expect(supportsReasoning('openai', 'gpt-4o-mini')).toBe(false);
    });

    it('accepte les modèles Anthropic de raisonnement', () => {
      expect(supportsReasoning('anthropic', 'claude-sonnet-4-20250514')).toBe(true);
      expect(supportsReasoning('anthropic', 'claude-3-5-haiku-latest')).toBe(false);
    });

    it('refuse ollama et vllm par défaut', () => {
      expect(supportsReasoning('ollama', 'deepseek-r1')).toBe(false);
      expect(supportsReasoning('vllm', 'some-model')).toBe(false);
    });
  });

  describe('defaultReasoningEffort', () => {
    it('retourne low pour un modèle compatible', () => {
      expect(defaultReasoningEffort('mistral', 'mistral-small-latest')).toBe('low');
    });

    it('retourne none pour un modèle incompatible', () => {
      expect(defaultReasoningEffort('ollama', 'llama3')).toBe('none');
    });
  });
});
