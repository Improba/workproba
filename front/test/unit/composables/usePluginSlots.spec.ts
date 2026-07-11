import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import type { PluginInfo } from '@composables/useDesktop';

const plugins = ref<PluginInfo[]>([]);
const activePluginIds = ref<string[]>([]);

vi.mock('@composables/usePlugins', () => ({
  usePlugins: () => ({
    plugins,
    activePluginIds,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../../src/plugins/pluginSlotComponents', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/plugins/pluginSlotComponents')>();
  return {
    ...actual,
    pluginSlotMeta: {
      'workproba.projet:right_panel': { labelKey: 'plugin.workproba.projet.tabLabel', icon: 'folder-kanban' },
      'workproba.personas:side_chat': { labelKey: 'plugin.workproba.personas.sideChat.title', icon: 'users' },
    },
  };
});

import { usePluginSlots } from '@composables/usePluginSlots';

function makePlugin(id: string, uiSlots: string[]): PluginInfo {
  return {
    manifest: {
      id,
      name: id,
      version: '1.0.0',
      description: '',
      permissions: [],
      defaultEnabled: true,
      uiSlots,
      hooks: [],
      isBuiltin: true,
    },
    enabled: true,
    enabledScoped: true,
    source: 'builtin',
  };
}

describe('usePluginSlots', () => {
  beforeEach(() => {
    plugins.value = [];
    activePluginIds.value = [];
  });

  it('expose les onglets right_panel des plugins actifs enregistrés', () => {
    plugins.value = [
      makePlugin('workproba.projet', ['right_panel']),
      makePlugin('workproba.browser', ['right_panel']),
      makePlugin('workproba.cloud', ['right_panel']),
    ];
    activePluginIds.value = ['workproba.projet', 'workproba.browser', 'workproba.cloud'];

    const { rightPanelPluginTabs } = usePluginSlots();
    const keys = rightPanelPluginTabs.value.map((tab) => tab.key);

    expect(keys).toEqual([
      'workproba.projet:right_panel',
      'workproba.browser:right_panel',
      'workproba.cloud:right_panel',
    ]);
  });

  it('masque les onglets right_panel des plugins inactifs', () => {
    plugins.value = [
      makePlugin('workproba.projet', ['right_panel']),
      makePlugin('workproba.browser', ['right_panel']),
    ];
    activePluginIds.value = ['workproba.projet'];

    const { rightPanelPluginTabs } = usePluginSlots();
    expect(rightPanelPluginTabs.value.map((tab) => tab.pluginId)).toEqual(['workproba.projet']);
  });

  it('expose le panneau side_chat du plugin personas actif', () => {
    plugins.value = [makePlugin('workproba.personas', ['left_panel', 'side_chat'])];
    activePluginIds.value = ['workproba.personas'];

    const { sideChatPluginPanels } = usePluginSlots();
    expect(sideChatPluginPanels.value).toHaveLength(1);
    expect(sideChatPluginPanels.value[0]?.key).toBe('workproba.personas:side_chat');
    expect(sideChatPluginPanels.value[0]?.icon).toBe('users');
  });

  it('ne retourne pas de side_chat si le plugin personas est inactif', () => {
    plugins.value = [makePlugin('workproba.personas', ['left_panel', 'side_chat'])];
    activePluginIds.value = [];

    const { sideChatPluginPanels } = usePluginSlots();
    expect(sideChatPluginPanels.value).toEqual([]);
  });

  it('ignore les slots sans entrée dans le registre', () => {
    plugins.value = [makePlugin('workproba.unknown', ['right_panel'])];
    activePluginIds.value = ['workproba.unknown'];

    const { rightPanelPluginTabs } = usePluginSlots();
    expect(rightPanelPluginTabs.value).toEqual([]);
  });

  it('ignore les ids actifs sans manifeste correspondant', () => {
    plugins.value = [makePlugin('workproba.projet', ['right_panel'])];
    activePluginIds.value = ['workproba.projet', 'workproba.missing'];

    const { rightPanelPluginTabs } = usePluginSlots();
    expect(rightPanelPluginTabs.value).toHaveLength(1);
    expect(rightPanelPluginTabs.value[0]?.pluginId).toBe('workproba.projet');
  });

  it('utilise des valeurs par défaut sans meta de slot', () => {
    plugins.value = [
      makePlugin('workproba.browser', ['right_panel']),
      makePlugin('workproba.projet', ['right_panel']),
    ];
    activePluginIds.value = ['workproba.browser', 'workproba.projet'];

    const { rightPanelPluginTabs } = usePluginSlots();
    const browserTab = rightPanelPluginTabs.value.find((tab) => tab.pluginId === 'workproba.browser');
    expect(browserTab?.label).toBe('workproba.browser');
    expect(browserTab?.icon).toBe('puzzle');
  });

  it('ignore les plugins actifs sans le slot cible', () => {
    plugins.value = [makePlugin('workproba.projet', ['settings'])];
    activePluginIds.value = ['workproba.projet'];

    const { rightPanelPluginTabs, sideChatPluginPanels } = usePluginSlots();
    expect(rightPanelPluginTabs.value).toEqual([]);
    expect(sideChatPluginPanels.value).toEqual([]);
  });
});
