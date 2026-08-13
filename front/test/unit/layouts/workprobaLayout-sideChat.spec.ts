import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WorkprobaLayout from '../../../src/layouts/WorkprobaLayout.vue';

const sideChatOpen = ref(false);
const rightPanelOpen = ref(false);
const capabilitiesOpen = ref(false);
const environmentOpen = ref(false);
const selectedBusinessAgentId = ref<string | null>(null);
const openSideChat = vi.fn();
const closeSideChat = vi.fn();
const toggleSideChat = vi.fn();
const toggleRightPanel = vi.fn();
const openCapabilities = vi.fn();
const closeCapabilities = vi.fn();
const openEnvironment = vi.fn();
const closeEnvironment = vi.fn();
const clearBusinessAgentSelection = vi.fn();
const sideChatPluginPanels = ref([{ pluginId: 'workproba.personas', key: 'workproba.personas:side_chat' }]);

vi.mock('@composables/useDesktop', () => ({
  getAppSettings: vi.fn().mockResolvedValue({ version: 1, providers: [], density: 'comfortable' }),
  saveAppSettings: vi.fn(async (s: unknown) => s),
}));

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activePath: ref<string | null>(null),
    activeDataDir: ref<string | null>(null),
    spaceTitle: ref<string | null>('Projet test'),
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
    environmentOpen,
    sideChatOpen,
    toggleRightPanel,
    toggleSideChat,
    openCapabilities,
    closeCapabilities,
    openEnvironment,
    closeEnvironment,
    clearBusinessAgentSelection,
    closeSideChat,
    selectedBusinessAgentId,
  }),
}));

describe('WorkprobaLayout side chat', () => {
  afterEach(() => {
    sideChatOpen.value = false;
    rightPanelOpen.value = false;
    capabilitiesOpen.value = false;
    environmentOpen.value = false;
    selectedBusinessAgentId.value = null;
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
          SpaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
          EnvironmentDrawer: true,
          BusinessAgentConsultDialog: true,
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
          SpaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
          EnvironmentDrawer: true,
          BusinessAgentConsultDialog: true,
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
    rightPanelOpen.value = true;
    const wrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div />' },
      global: {
        stubs: {
          WorkprobaTitleBar: true,
          SpaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
          EnvironmentDrawer: true,
          BusinessAgentConsultDialog: true,
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

  it('revient à la liste des agents avant de fermer l’environnement sur Escape', async () => {
    environmentOpen.value = true;
    selectedBusinessAgentId.value = 'org.rh';

    const wrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div />' },
      global: {
        stubs: {
          WorkprobaTitleBar: true,
          SpaceSidebar: true,
          RightPanel: true,
          SideChatPanel: true,
          KeyboardShortcutsHelp: true,
          CapabilitiesDrawer: true,
          EnvironmentDrawer: true,
          BusinessAgentConsultDialog: true,
        },
      },
    });
    await flushPromises();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(clearBusinessAgentSelection).toHaveBeenCalled();
    expect(closeEnvironment).not.toHaveBeenCalled();

    selectedBusinessAgentId.value = null;
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(closeEnvironment).toHaveBeenCalled();

    wrapper.unmount();
  });
});
