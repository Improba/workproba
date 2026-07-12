import { ref } from 'vue';
import type { ReasoningEffort } from '#types';
import type { ProviderSet } from '@composables/useDesktop.types';
import {
  buildRoutedProviderSet,
  buildSessionAwareLlmConfigs,
} from '@utils/llmRouting';

interface SessionLlmContext {
  model: string | null;
  reasoning: ReasoningEffort | null;
}

const contexts = new Map<string, SessionLlmContext>();
const activeSessionId = ref<string | null>(null);

/** Publie les overrides LLM de la conversation (personas, PJ, utility). */
export function setLlmSessionContext(
  sessionId: string,
  model: string | null,
  reasoning: ReasoningEffort | null,
): void {
  const id = sessionId.trim();
  if (!id) return;
  activeSessionId.value = id;
  contexts.set(id, { model, reasoning });
}

export function clearLlmSessionContext(sessionId?: string): void {
  if (sessionId) {
    contexts.delete(sessionId);
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null;
    }
    return;
  }
  contexts.clear();
  activeSessionId.value = null;
}

function activeContext(): SessionLlmContext | null {
  const id = activeSessionId.value;
  if (!id) return null;
  return contexts.get(id) ?? null;
}

export function useLlmSessionContext(): {
  activeSessionId: typeof activeSessionId;
  buildContextProviderSet: () => ProviderSet | null;
  buildContextLlmConfigs: () => ReturnType<typeof buildSessionAwareLlmConfigs>;
} {
  function buildContextProviderSet(): ProviderSet | null {
    const ctx = activeContext();
    return buildRoutedProviderSet(ctx?.model ?? null, ctx?.reasoning ?? null);
  }

  function buildContextLlmConfigs() {
    const ctx = activeContext();
    return buildSessionAwareLlmConfigs(ctx?.model ?? null, ctx?.reasoning ?? null);
  }

  return {
    activeSessionId,
    buildContextProviderSet,
    buildContextLlmConfigs,
  };
}
