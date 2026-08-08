import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';
import type { CapabilityId } from '@capabilities/capabilityCatalog';
import { useSideChat } from './useSideChat';

const rightPanelOpen = ref(false);
const rightPanelTab = ref('files');
const capabilitiesOpen = ref(false);
const focusCapabilityId = ref<CapabilityId | null>(null);
const environmentOpen = ref(false);
const selectedBusinessAgentId = ref<string | null>(null);

let shellWatcherStarted = false;

function ensureShellWatcher(): void {
  if (shellWatcherStarted) return;
  shellWatcherStarted = true;

  const { sideChatOpen, closeSideChat } = useSideChat();

  watch(sideChatOpen, (open) => {
    if (open) {
      rightPanelOpen.value = false;
      environmentOpen.value = false;
      selectedBusinessAgentId.value = null;
    }
  });

  watch(rightPanelOpen, (open) => {
    if (open && sideChatOpen.value) {
      closeSideChat();
    }
    if (open) {
      environmentOpen.value = false;
      selectedBusinessAgentId.value = null;
    }
  });
}

export interface UseShellSurfacesReturn {
  rightPanelOpen: Ref<boolean>;
  rightPanelTab: Ref<string>;
  capabilitiesOpen: Ref<boolean>;
  focusCapabilityId: Ref<CapabilityId | null>;
  environmentOpen: Ref<boolean>;
  selectedBusinessAgentId: Ref<string | null>;
  sideChatOpen: ComputedRef<boolean>;
  openRightPanel: (tabKey?: string) => void;
  closeRightPanel: () => void;
  toggleRightPanel: (tabKey?: string) => void;
  openSideChat: (pluginId: string) => void;
  closeSideChat: () => void;
  toggleSideChat: (pluginId: string) => void;
  openCapabilities: (focusId?: CapabilityId) => void;
  closeCapabilities: () => void;
  openEnvironment: (businessAgentId?: string | null) => void;
  closeEnvironment: () => void;
  selectBusinessAgent: (agentId: string) => void;
  clearBusinessAgentSelection: () => void;
  closeTransientPanels: () => void;
}

export function resetShellSurfacesForTests(): void {
  rightPanelOpen.value = false;
  rightPanelTab.value = 'files';
  capabilitiesOpen.value = false;
  focusCapabilityId.value = null;
  environmentOpen.value = false;
  selectedBusinessAgentId.value = null;
}

export function useShellSurfaces(): UseShellSurfacesReturn {
  ensureShellWatcher();

  const {
    sideChatOpen,
    openSideChat: openSideChatInternal,
    closeSideChat,
  } = useSideChat();

  function openRightPanel(tabKey = 'files'): void {
    closeSideChat();
    capabilitiesOpen.value = false;
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
    rightPanelTab.value = tabKey;
    rightPanelOpen.value = true;
  }

  function closeRightPanel(): void {
    rightPanelOpen.value = false;
  }

  function toggleRightPanel(tabKey = 'files'): void {
    if (rightPanelOpen.value) {
      closeRightPanel();
      return;
    }
    openRightPanel(tabKey);
  }

  function openSideChat(pluginId: string): void {
    rightPanelOpen.value = false;
    capabilitiesOpen.value = false;
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
    openSideChatInternal(pluginId);
  }

  function toggleSideChat(pluginId: string): void {
    if (sideChatOpen.value) {
      closeSideChat();
      return;
    }
    openSideChat(pluginId);
  }

  function openCapabilities(focusId?: CapabilityId): void {
    rightPanelOpen.value = false;
    closeSideChat();
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
    focusCapabilityId.value = focusId ?? null;
    capabilitiesOpen.value = true;
  }

  function closeCapabilities(): void {
    capabilitiesOpen.value = false;
    focusCapabilityId.value = null;
  }

  function openEnvironment(businessAgentId?: string | null): void {
    rightPanelOpen.value = false;
    closeSideChat();
    capabilitiesOpen.value = false;
    focusCapabilityId.value = null;
    selectedBusinessAgentId.value = businessAgentId ?? null;
    environmentOpen.value = true;
  }

  function closeEnvironment(): void {
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
  }

  function selectBusinessAgent(agentId: string): void {
    selectedBusinessAgentId.value = agentId;
  }

  function clearBusinessAgentSelection(): void {
    selectedBusinessAgentId.value = null;
  }

  function closeTransientPanels(): void {
    capabilitiesOpen.value = false;
    focusCapabilityId.value = null;
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
    rightPanelOpen.value = false;
    closeSideChat();
  }

  return {
    rightPanelOpen,
    rightPanelTab,
    capabilitiesOpen,
    focusCapabilityId,
    environmentOpen,
    selectedBusinessAgentId,
    sideChatOpen,
    openRightPanel,
    closeRightPanel,
    toggleRightPanel,
    openSideChat,
    closeSideChat,
    toggleSideChat,
    openCapabilities,
    closeCapabilities,
    openEnvironment,
    closeEnvironment,
    selectBusinessAgent,
    clearBusinessAgentSelection,
    closeTransientPanels,
  };
}
