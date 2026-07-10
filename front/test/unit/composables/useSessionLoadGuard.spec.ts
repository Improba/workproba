import { describe, expect, it } from 'vitest';
import { createSessionLoadGuard } from '@composables/useSessionLoadGuard';

describe('createSessionLoadGuard', () => {
  it('ignore une réponse tardive quand une charge plus récente a démarré', () => {
    const guard = createSessionLoadGuard();

    const loadA = guard.next();
    const loadB = guard.next();

    expect(guard.isStale(loadA)).toBe(true);
    expect(guard.isStale(loadB)).toBe(false);
  });
});
