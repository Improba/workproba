import { beforeEach, describe, expect, it, vi } from 'vitest';
import { computed, ref } from 'vue';

const sideChatOpen = ref(false);
const openSideChatInternal = vi.fn(() => {
  sideChatOpen.value = true;
});
const closeSideChatInternal = vi.fn(() => {
  sideChatOpen.value = false;
});

vi.mock('@composables/useSideChat', () => ({
  useSideChat: () => ({
    sideChatOpen: computed(() => sideChatOpen.value),
    openSideChat: openSideChatInternal,
    closeSideChat: closeSideChatInternal,
  }),
}));

import {
  resetShellSurfacesForTests,
  useShellSurfaces,
} from '@composables/useShellSurfaces';

describe('useShellSurfaces', () => {
  beforeEach(() => {
    resetShellSurfacesForTests();
    sideChatOpen.value = false;
    openSideChatInternal.mockClear();
    closeSideChatInternal.mockClear();
  });

  it('ouvre le panneau droit et ferme le side chat', () => {
    sideChatOpen.value = true;
    const { openRightPanel, rightPanelOpen, rightPanelTab } = useShellSurfaces();

    openRightPanel('workproba.projet:right_panel');

    expect(rightPanelOpen.value).toBe(true);
    expect(rightPanelTab.value).toBe('workproba.projet:right_panel');
    expect(closeSideChatInternal).toHaveBeenCalled();
  });

  it('ouvre le side chat et ferme le panneau droit', () => {
    const { openSideChat, rightPanelOpen, capabilitiesOpen } = useShellSurfaces();

    rightPanelOpen.value = true;
    capabilitiesOpen.value = true;
    openSideChat('workproba.personas');

    expect(rightPanelOpen.value).toBe(false);
    expect(capabilitiesOpen.value).toBe(false);
    expect(openSideChatInternal).toHaveBeenCalledWith('workproba.personas');
  });

  it('coordonne le tiroir Capacités', () => {
    const {
      openCapabilities,
      closeCapabilities,
      capabilitiesOpen,
      focusCapabilityId,
    } = useShellSurfaces();

    openCapabilities('projects');
    expect(capabilitiesOpen.value).toBe(true);
    expect(focusCapabilityId.value).toBe('projects');

    closeCapabilities();
    expect(capabilitiesOpen.value).toBe(false);
    expect(focusCapabilityId.value).toBeNull();
  });

  it('toggleRightPanel bascule l’état du panneau droit', () => {
    const { toggleRightPanel, rightPanelOpen } = useShellSurfaces();

    toggleRightPanel('preview');
    expect(rightPanelOpen.value).toBe(true);

    toggleRightPanel();
    expect(rightPanelOpen.value).toBe(false);
  });
});
