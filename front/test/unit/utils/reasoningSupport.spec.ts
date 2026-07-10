import { describe, expect, it } from 'vitest';
import {
  clampReasoningEffort,
  defaultReasoningEffort,
  supportsReasoning,
  supportedReasoningEfforts,
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

  describe('supportedReasoningEfforts', () => {
    it('limite mistral-small à none/high (API Mistral)', () => {
      expect(supportedReasoningEfforts('mistral', 'mistral-small-latest')).toEqual([
        'none',
        'high',
      ]);
    });

    it('garde la plage complète pour les autres modèles Mistral', () => {
      expect(supportedReasoningEfforts('mistral', 'mistral-medium-latest')).toEqual([
        'none',
        'low',
        'medium',
        'high',
      ]);
      expect(supportedReasoningEfforts('mistral', 'mistral-large-latest')).toEqual([
        'none',
        'low',
        'medium',
        'high',
      ]);
    });

    it('garde la plage complète pour OpenAI/Anthropic de raisonnement', () => {
      expect(supportedReasoningEfforts('openai', 'gpt-5-preview')).toEqual([
        'none',
        'low',
        'medium',
        'high',
      ]);
      expect(supportedReasoningEfforts('anthropic', 'claude-sonnet-4-20250514')).toEqual([
        'none',
        'low',
        'medium',
        'high',
      ]);
    });

    it('retourne uniquement none pour les modèles sans raisonnement', () => {
      expect(supportedReasoningEfforts('ollama', 'llama3')).toEqual(['none']);
      expect(supportedReasoningEfforts('mistral', 'mistral-embed')).toEqual(['none']);
    });
  });

  describe('defaultReasoningEffort', () => {
    it('retourne low pour un modèle supportant low', () => {
      expect(defaultReasoningEffort('mistral', 'mistral-medium-latest')).toBe('low');
    });

    it('retourne none pour mistral-small (low non supporté)', () => {
      expect(defaultReasoningEffort('mistral', 'mistral-small-latest')).toBe('none');
    });

    it('retourne none pour un modèle incompatible', () => {
      expect(defaultReasoningEffort('ollama', 'llama3')).toBe('none');
    });
  });

  describe('clampReasoningEffort', () => {
    it('garde un effort supporté', () => {
      expect(clampReasoningEffort('mistral', 'mistral-small-latest', 'high')).toBe('high');
      expect(clampReasoningEffort('mistral', 'mistral-small-latest', 'none')).toBe('none');
    });

    it('ramène low à none pour mistral-small', () => {
      expect(clampReasoningEffort('mistral', 'mistral-small-latest', 'low')).toBe('none');
      expect(clampReasoningEffort('mistral', 'mistral-small-latest', 'medium')).toBe('none');
    });

    it('garde low pour un modèle qui le supporte', () => {
      expect(clampReasoningEffort('mistral', 'mistral-medium-latest', 'low')).toBe('low');
    });
  });
});
