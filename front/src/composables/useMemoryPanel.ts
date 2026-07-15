import { ref, type Ref } from 'vue';

export interface MemoryPanelRequest {
  memoryId?: string;
}

const panelRequest = ref<MemoryPanelRequest | null>(null);

export interface UseMemoryPanelReturn {
  panelRequest: Ref<MemoryPanelRequest | null>;
  openMemoryPanel: (memoryId?: string) => void;
  clearMemoryPanelRequest: () => void;
}

export function resetMemoryPanelForTests(): void {
  panelRequest.value = null;
}

export function useMemoryPanel(): UseMemoryPanelReturn {
  function openMemoryPanel(memoryId?: string): void {
    panelRequest.value = memoryId ? { memoryId } : {};
  }

  function clearMemoryPanelRequest(): void {
    panelRequest.value = null;
  }

  return {
    panelRequest,
    openMemoryPanel,
    clearMemoryPanelRequest,
  };
}
