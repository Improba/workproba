import { computed, ref, type ComputedRef, type Ref } from 'vue';
import type { PersonaInfo } from '@services/aiSidecar';

const selectedAgent = ref<PersonaInfo | null>(null);

export interface UseBusinessAgentConsultationReturn {
  open: ComputedRef<boolean>;
  selectedAgent: Ref<PersonaInfo | null>;
  requestConsultation: (agent: PersonaInfo) => void;
  closeConsultation: () => void;
}

export function useBusinessAgentConsultation(): UseBusinessAgentConsultationReturn {
  const open = computed(() => selectedAgent.value != null);

  function requestConsultation(agent: PersonaInfo): void {
    selectedAgent.value = agent;
  }

  function closeConsultation(): void {
    selectedAgent.value = null;
  }

  return {
    open,
    selectedAgent,
    requestConsultation,
    closeConsultation,
  };
}

export function resetBusinessAgentConsultationForTests(): void {
  selectedAgent.value = null;
}
