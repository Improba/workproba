import { describe, expect, it } from 'vitest';
import { nextTick } from 'vue';
import { watch } from 'vue';
import { usePersonasNavigation } from '@composables/usePersonasNavigation';

describe('usePersonasNavigation', () => {
  it('consumeAction vide pendingAction après lecture', () => {
    const { requestAction, consumeAction, pendingAction } = usePersonasNavigation();

    requestAction('meeting');
    expect(pendingAction.value).toBe('meeting');

    const payload = consumeAction();
    expect(payload?.action).toBe('meeting');
    expect(pendingAction.value).toBeNull();
  });

  it('transmet les personaIds avec l\'action', () => {
    const { requestAction, consumeAction } = usePersonasNavigation();

    requestAction('discuss', { personaIds: ['p1', 'p2'] });
    const payload = consumeAction();

    expect(payload).toEqual({ action: 'discuss', personaIds: ['p1', 'p2'] });
  });

  it('ignore les personaIds vides', () => {
    const { requestAction, consumeAction } = usePersonasNavigation();

    requestAction('discuss', { personaIds: [] });
    const payload = consumeAction();

    expect(payload).toEqual({ action: 'discuss', personaIds: undefined });
  });

  it('déclenche le handler quand une action est demandée sur la même route', async () => {
    const applied: string[] = [];
    const { requestAction, consumeAction, pendingAction } = usePersonasNavigation();

    watch(pendingAction, (action) => {
      if (!action) return;
      const consumed = consumeAction();
      if (consumed) applied.push(consumed.action);
    });

    requestAction('opinion');
    await nextTick();

    expect(applied).toEqual(['opinion']);
  });
});
