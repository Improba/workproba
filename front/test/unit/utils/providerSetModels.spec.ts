import { describe, expect, it } from 'vitest';
import { MISTRAL_BUILTIN_SET } from '@utils/providerSets';
import {
  clampReasoningEffortForSet,
  contextWindowForSet,
  defaultReasoningEffortForSet,
  findSetModel,
  hasSetModelChoice,
  isModelApplicableForSet,
  modelsForSet,
  supportedReasoningEffortsForSet,
  supportsReasoningForSet,
} from '@utils/providerSetModels';

describe('providerSetModels', () => {
  const set = MISTRAL_BUILTIN_SET;

  it('expose les modèles Mistral du set intégré', () => {
    expect(modelsForSet(set).map((m) => m.model)).toEqual([
      'mistral-small-latest',
      'mistral-medium-latest',
      'mistral-large-latest',
    ]);
    expect(hasSetModelChoice(set)).toBe(true);
  });

  it('résout les efforts de raisonnement par modèle', () => {
    expect(supportedReasoningEffortsForSet(set, 'mistral-small-latest')).toEqual([
      'none',
      'high',
    ]);
    expect(supportedReasoningEffortsForSet(set, 'mistral-large-latest')).toEqual(['none']);
    expect(supportsReasoningForSet(set, 'mistral-medium-latest')).toBe(true);
    expect(supportsReasoningForSet(set, 'mistral-large-latest')).toBe(false);
  });

  it('clamp et défaut alignés sur le catalogue du set', () => {
    expect(clampReasoningEffortForSet(set, 'mistral-small-latest', 'low')).toBe('high');
    expect(defaultReasoningEffortForSet(set, 'mistral-small-latest')).toBe('none');
    expect(clampReasoningEffortForSet(set, 'mistral-large-latest', 'high')).toBe('none');
  });

  it('expose la fenêtre de contexte cataloguée', () => {
    expect(contextWindowForSet(set, 'mistral-medium-latest')).toBe(256000);
    expect(findSetModel(set, 'mistral-large-latest')?.label).toBe('Mistral Large');
  });

  it('valide les modèles applicables au set', () => {
    expect(isModelApplicableForSet(set, 'mistral-small-latest')).toBe(true);
    expect(isModelApplicableForSet(set, 'gpt-4o')).toBe(false);
  });

  it('retourne none seul pour un modèle absent du catalogue', () => {
    expect(supportedReasoningEffortsForSet(set, 'mistral-unknown')).toEqual(['none']);
    expect(supportsReasoningForSet(set, 'mistral-unknown')).toBe(false);
  });
});
