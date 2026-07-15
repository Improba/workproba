import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import RightPanel from '@components/workproba/RightPanel.vue';

const rightPanelPluginTabs = ref([
  {
    key: 'workproba.projet:right_panel',
    pluginId: 'workproba.projet',
    label: 'Projet',
    icon: 'folder-kanban',
    component: { template: '<div class="project-pane" />' },
  },
]);

vi.mock('@composables/usePluginSlots', () => ({
  usePluginSlots: () => ({
    rightPanelPluginTabs,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settingsLocked: ref(false),
    settingsMode: ref('guided'),
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    rightPanelTab: ref('files'),
  }),
}));

vi.mock('@composables/usePlugins', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@composables/usePlugins')>();
  return {
    ...actual,
    usePlugins: () => ({
      isProjetPluginActive: ref(true),
      isPersonasPluginActive: ref(false),
      getPluginDataDir: vi.fn().mockResolvedValue(null),
    }),
  };
});

vi.mock('@composables/usePersonasActions', () => ({
  usePersonasActions: () => ({
    askOpinion: vi.fn(),
    startMeeting: vi.fn(),
    discuss: vi.fn(),
    relaunchMeeting: vi.fn(),
    resumeDiscussion: vi.fn(),
  }),
}));

describe('RightPanel plugin tabs', () => {
  it('réinitialise l’onglet actif quand les onglets plugin disparaissent', async () => {
    const wrapper = shallowMount(RightPanel, {
      props: { activePath: null, open: true },
      global: {
        stubs: {
          Lucide: true,
          FileExplorer: { template: '<div class="file-explorer-stub" />' },
          DocumentPreview: true,
          VersionsPanel: true,
          PublishToProjectDialog: true,
        },
      },
    });
    await flushPromises();

    const pluginTab = wrapper.findAll('.wp-right-panel__tab')[2];
    expect(pluginTab?.text()).toContain('Projet');
    await pluginTab!.trigger('click');

    rightPanelPluginTabs.value = [];
    await flushPromises();

    expect(wrapper.find('.file-explorer-stub').isVisible()).toBe(true);
  });
});
