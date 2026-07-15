import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WorkprobaLayout from '../../../src/layouts/WorkprobaLayout.vue';

const sideChatOpen = ref(false);
const rightPanelOpen = ref(false);
const capabilitiesOpen = ref(false);
const openSideChat = vi.fn();
const closeSideChat = vi.fn();
const toggleSideChat = vi.fn();
const toggleRightPanel = vi.fn();
const openCapabilities = vi.fn();
const closeCapabilities = vi.fn();
const sideChatPluginPanels = ref([{ pluginId: 'workproba.personas', key: 'workproba.personas:side_chat' }]);

vi.mock('@composables/useDesktop', () => ({
  getAppSettings: vi.fn().mockResolvedValue({ version: 1, providers: [], density: 'comfortable' }),
  saveAppSettings: vi.fn(async (s: unknown) => s),
}));

vi.mock('@composables/useProject', () => ({
  useProject: () => ({
    activePath: ref<string | null>(null),
    activeDataDir: ref<string | null>(null),
    workspaceTitle: ref<string | null>('Projet test'),
  }),
}));

vi.mock('@composables/useSidecarHealth', () => ({
  useSidecarHealth: vi.fn(),
}));

vi.mock('@composables/usePluginSlots', () => ({
  usePluginSlots: () => ({
    sideChatPluginPanels,
    rightPanelPluginTabs: ref([]),
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    rightPanelOpen,
    capabilitiesOpen,
    sideChatOpen,
    toggleRightPanel,
    toggleSideChat,
    openCapabilities,
    closeCapabilities,
    closeSideChat,
  }),
}));

describe('WorkprobaLayout side chat', () => {
  afterEach(() => {
    sideChatOpen.value = false;
    rightPanelOpen.value = false;
    capabilitiesOpen.value = false;
    openSideChat.mockClear();
    closeSideChat.mockClear();
    toggleSideChat.mockClear();
    sideChatPluginPanels.value = [{ pluginId: 'workproba.personas', key: 'workproba.personas:side_chat' }];
  });

  it('bascule le side chat via Ctrl+Shift+L', async () => {
    const wrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div />' },
      global: {
        stubs: {
          WorkprobaTitleBar: true,
          WorkspaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
        },
      },
    });
    await flushPromises();

    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'l', ctrlKey: true, shiftKey: true }),
    );
    expect(toggleSideChat).toHaveBeenCalledWith('workproba.personas');

    wrapper.unmount();
  });

  it('n’écoute pas Ctrl+Shift+L quand hasSideChat est faux', async () => {
    sideChatPluginPanels.value = [];
    const wrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div />' },
      global: {
        stubs: {
          WorkprobaTitleBar: true,
          WorkspaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
        },
      },
    });
    await flushPromises();

    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'l', ctrlKey: true, shiftKey: true }),
    );
    expect(toggleSideChat).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('replie l’explorateur de fichiers à l’ouverture du side chat', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
    const wrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div />' },
      global: {
        stubs: {
          WorkprobaTitleBar: {
            template: '<button class="toggle-side-chat" @click="$emit(\'toggle-side-chat\')" />',
          },
          WorkspaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
        },
      },
    });
    await flushPromises();

    await wrapper.find('.toggle-side-chat').trigger('click');
    expect(toggleSideChat).toHaveBeenCalledWith('workproba.personas');

    wrapper.unmount();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
  });
});
