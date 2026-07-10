import { ref, type Ref } from 'vue';

export type SidecarState = 'connected' | 'idle' | 'working' | 'error';

const streaming = ref(false);
const sidecarState = ref<SidecarState>('idle');

export interface UseChatActivityReturn {
  streaming: Ref<boolean>;
  sidecarState: Ref<SidecarState>;
  setStreaming: (value: boolean) => void;
  setSidecarState: (value: SidecarState) => void;
}

export function useChatActivity(): UseChatActivityReturn {
  function setStreaming(value: boolean): void {
    streaming.value = value;
  }

  function setSidecarState(value: SidecarState): void {
    sidecarState.value = value;
  }

  return {
    streaming,
    sidecarState,
    setStreaming,
    setSidecarState,
  };
}
