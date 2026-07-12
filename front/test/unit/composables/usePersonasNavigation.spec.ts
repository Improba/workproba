import { describe, expect, it } from 'vitest';
import { nextTick } from 'vue';
import { watch } from 'vue';
import { usePersonasNavigation } from '@composables/usePersonasNavigation';

describe('usePersonasNavigation', () => {
  it('consumeAction vide pendingAction après lecture', () => {
    const { requestAction, consumeAction, pendingAction } = usePersonasNavigation();

    requestAction('meeting');
    expect(pendingAction.value).toBe('meeting');

    const action = consumeAction();
    expect(action).toBe('meeting');
    expect(pendingAction.value).toBeNull();
  });

  it('déclenche le handler quand une action est demandée sur la même route', async () => {
    const applied: string[] = [];
    const { requestAction, consumeAction, pendingAction } = usePersonasNavigation();

    watch(pendingAction, (action) => {
      if (!action) return;
      const consumed = consumeAction();
      if (consumed) applied.push(consumed);
    });

    requestAction('opinion');
    await nextTick();

    expect(applied).toEqual(['opinion']);
  });
});
