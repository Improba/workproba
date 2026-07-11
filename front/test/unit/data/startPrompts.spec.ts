import { describe, expect, it } from 'vitest';

import { getStartPrompts, type StartPrompt } from '../../../src/data/startPrompts';

const REQUIRED_KEYS: (keyof StartPrompt)[] = [
  'id',
  'icon',
  'title',
  'subtitle',
  'prompt',
];

describe('startPrompts', () => {
  it('expose au moins six suggestions de démarrage', () => {
    expect(getStartPrompts().length).toBeGreaterThanOrEqual(6);
  });

  it('chaque entrée a un id unique et tous les champs requis', () => {
    const ids = new Set<string>();

    for (const entry of getStartPrompts()) {
      for (const key of REQUIRED_KEYS) {
        expect(entry[key], `${entry.id ?? '?'}.${key}`).toBeTruthy();
      }
      expect(ids.has(entry.id), `id dupliqué: ${entry.id}`).toBe(false);
      ids.add(entry.id);
    }
  });
});
