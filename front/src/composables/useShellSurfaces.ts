import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';
import type { CapabilityId } from '@capabilities/capabilityCatalog';
import { useSideChat } from './useSideChat';

const rightPanelOpen = ref(false);
const rightPanelTab = ref('files');
const capabilitiesOpen = ref(false);
const focusCapabilityId = ref<CapabilityId | null>(null);

let shellWatcherStarted = false;

function ensureShellWatcher(): void {
  if (shellWatcherStarted) return;
  shellWatcherStarted = true;

  const { sideChatOpen, closeSideChat } = useSideChat();

  watch(sideChatOpen, (open) => {
    if (open) rightPanelOpen.value = false;
  });

  watch(rightPanelOpen, (open) => {
    if (open && sideChatOpen.value) {
      closeSideChat();
    }
  });
}

export interface UseShellSurfacesReturn {
  rightPanelOpen: Ref<boolean>;
  rightPanelTab: Ref<string>;
  capabilitiesOpen: Ref<boolean>;
  focusCapabilityId: Ref<CapabilityId | null>;
  sideChatOpen: ComputedRef<boolean>;
  openRightPanel: (tabKey?: string) => void;
  closeRightPanel: () => void;
  toggleRightPanel: (tabKey?: string) => void;
  openSideChat: (pluginId: string) => void;
  closeSideChat: () => void;
  toggleSideChat: (pluginId: string) => void;
  openCapabilities: (focusId?: CapabilityId) => void;
  closeCapabilities: () => void;
  closeTransientPanels: () => void;
}

export function resetShellSurfacesForTests(): void {
  rightPanelOpen.value = false;
  rightPanelTab.value = 'files';
  capabilitiesOpen.value = false;
  focusCapabilityId.value = null;
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
    focusCapabilityId.value = focusId ?? null;
    capabilitiesOpen.value = true;
  }

  function closeCapabilities(): void {
    capabilitiesOpen.value = false;
    focusCapabilityId.value = null;
  }

  function closeTransientPanels(): void {
    capabilitiesOpen.value = false;
    focusCapabilityId.value = null;
    rightPanelOpen.value = false;
    closeSideChat();
  }

  return {
    rightPanelOpen,
    rightPanelTab,
    capabilitiesOpen,
    focusCapabilityId,
    sideChatOpen,
    openRightPanel,
    closeRightPanel,
    toggleRightPanel,
    openSideChat,
    closeSideChat,
    toggleSideChat,
    openCapabilities,
    closeCapabilities,
    closeTransientPanels,
  };
}
