import { ref } from 'vue';

export type PersonasNavAction = 'meeting' | 'discuss' | 'opinion';

const pendingAction = ref<PersonasNavAction | null>(null);

export function usePersonasNavigation() {
  function requestAction(action: PersonasNavAction): void {
    pendingAction.value = action;
  }

  function consumeAction(): PersonasNavAction | null {
    const action = pendingAction.value;
    pendingAction.value = null;
    return action;
  }

  return {
    pendingAction,
    requestAction,
    consumeAction,
  };
}
