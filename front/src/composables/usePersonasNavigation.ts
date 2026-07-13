import { computed, ref } from 'vue';
import type { DiscussionMessage } from '@composables/usePersonas';

export type PersonasNavAction = 'meeting' | 'discuss' | 'opinion';

export interface PersonasResumePayload {
  discussionId: string;
  personaIds: string[];
  messages: DiscussionMessage[];
}

export interface PersonasNavPayload {
  action: PersonasNavAction;
  personaIds?: string[];
  resume?: PersonasResumePayload;
}

const pendingPayload = ref<PersonasNavPayload | null>(null);

export function usePersonasNavigation() {
  const pendingAction = computed(() => pendingPayload.value?.action ?? null);

  function requestAction(
    action: PersonasNavAction,
    opts?: { personaIds?: string[]; resume?: PersonasResumePayload },
  ): void {
    pendingPayload.value = {
      action,
      personaIds: opts?.personaIds?.length ? [...opts.personaIds] : undefined,
      resume: opts?.resume,
    };
  }

  function consumeAction(): PersonasNavPayload | null {
    const payload = pendingPayload.value;
    pendingPayload.value = null;
    return payload;
  }

  return {
    pendingAction,
    requestAction,
    consumeAction,
  };
}
