import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PluginInfo } from '@composables/useDesktop';
import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
  PROJET_PLUGIN_ID,
} from '@composables/usePlugins';

const plugins = ref<PluginInfo[]>([]);
const activePluginIds = ref<string[]>([]);
const activatePlugin = vi.fn(async (id: string) => {
  if (!activePluginIds.value.includes(id)) {
    activePluginIds.value = [...activePluginIds.value, id];
  }
});
const deactivatePlugin = vi.fn(async (id: string) => {
  activePluginIds.value = activePluginIds.value.filter((pluginId) => pluginId !== id);
});

const settingsLocked = ref(false);
const settingsMode = ref<'guided' | 'advanced'>('guided');
const permissionsNetwork = ref(true);
const permissionsProjectSync = ref(true);
const settings = ref({
  version: 1,
  providers: [],
  settingsLocked: false,
  settingsMode: 'guided' as const,
  pluginsAllowed: null as string[] | null,
  permissionsNetwork: true,
  permissionsProjectSync: true,
});

const openRightPanel = vi.fn();
const openSideChat = vi.fn();
const closeCapabilities = vi.fn();

vi.mock('@composables/usePlugins', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@composables/usePlugins')>();
  return {
    ...actual,
    usePlugins: () => ({
      plugins,
      activePluginIds,
      activatePlugin,
      deactivatePlugin,
    }),
  };
});

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settings,
    settingsLocked,
    settingsMode,
    permissionsNetwork,
    permissionsProjectSync,
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openRightPanel,
    openSideChat,
    closeCapabilities,
  }),
}));

import { useCapabilities } from '@composables/useCapabilities';

function makePlugin(id: string): PluginInfo {
  return {
    manifest: {
      id,
      name: id,
      version: '1.0.0',
      description: '',
      permissions: [],
      defaultEnabled: false,
      uiSlots: [],
      hooks: [],
      isBuiltin: true,
    },
    enabled: false,
    enabledScoped: false,
    source: 'builtin',
  };
}

describe('useCapabilities', () => {
  beforeEach(() => {
    plugins.value = [
      makePlugin(PERSONAS_PLUGIN_ID),
      makePlugin(PROJET_PLUGIN_ID),
      makePlugin(BROWSER_PLUGIN_ID),
      makePlugin(CLOUD_PLUGIN_ID),
    ];
    activePluginIds.value = [];
    settings.value = {
      version: 1,
      providers: [],
      settingsLocked: false,
      settingsMode: 'guided',
      pluginsAllowed: null,
      permissionsNetwork: true,
      permissionsProjectSync: true,
    };
    settingsLocked.value = false;
    settingsMode.value = 'guided';
    permissionsNetwork.value = true;
    permissionsProjectSync.value = true;
    activatePlugin.mockClear();
    deactivatePlugin.mockClear();
    openRightPanel.mockClear();
    openSideChat.mockClear();
    closeCapabilities.mockClear();
  });

  it('mappe active et available selon les plugins actifs', () => {
    activePluginIds.value = [PROJET_PLUGIN_ID];

    const { getById } = useCapabilities();

    expect(getById('projects')?.state.kind).toBe('active');
    expect(getById('regards')?.state.kind).toBe('available');
    expect(getById('project_sync')?.state.kind).toBe('coming_soon');
  });

  it('marque blocked avec managedByOrganization quand le preset bloque', () => {
    settingsLocked.value = true;
    settings.value.settingsLocked = true;
    settings.value.pluginsAllowed = [PROJET_PLUGIN_ID];

    const { getById } = useCapabilities();
    const browser = getById('web_navigation');

    expect(browser?.state.kind).toBe('blocked');
    expect(browser?.state.managedByOrganization).toBe(true);
  });

  it('marque project_sync blocked quand project_sync est désactivé par preset', () => {
    settingsLocked.value = true;
    settings.value.settingsLocked = true;
    settings.value.permissionsProjectSync = false;
    permissionsProjectSync.value = false;

    const { getById } = useCapabilities();
    const sync = getById('project_sync');

    expect(sync?.state.kind).toBe('blocked');
    expect(sync?.state.managedByOrganization).toBe(true);
  });

  it('activateAndOpen active le plugin puis ouvre la surface shell', async () => {
    const { activateAndOpen } = useCapabilities();

    await activateAndOpen('projects');

    expect(activatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(closeCapabilities).toHaveBeenCalled();
    expect(openRightPanel).toHaveBeenCalledWith('workproba.projet:right_panel');
  });

  it('open ouvre le side chat pour regards', () => {
    activePluginIds.value = [PERSONAS_PLUGIN_ID];
    const { open } = useCapabilities();

    open('regards');

    expect(openSideChat).toHaveBeenCalledWith(PERSONAS_PLUGIN_ID);
  });

  it('activateAndOpen project_sync active le parent puis le cloud', async () => {
    settingsMode.value = 'advanced';
    settings.value.settingsMode = 'advanced';

    const { activateAndOpen } = useCapabilities();
    await activateAndOpen('project_sync');

    expect(activatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(activatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
    expect(openRightPanel).toHaveBeenCalledWith('workproba.cloud:right_panel');
  });

  it('project_sync reste available si seul le cloud est actif', () => {
    settingsMode.value = 'advanced';
    settings.value.settingsMode = 'advanced';
    activePluginIds.value = [CLOUD_PLUGIN_ID];

    const { getById } = useCapabilities();
    expect(getById('project_sync')?.state.kind).toBe('available');
  });

  it('open project_sync ouvre l’onglet cloud', () => {
    settingsMode.value = 'advanced';
    settings.value.settingsMode = 'advanced';
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];

    const { open } = useCapabilities();
    open('project_sync');

    expect(openSideChat).not.toHaveBeenCalled();
    expect(openRightPanel).toHaveBeenCalledWith('workproba.cloud:right_panel');
  });

  it('deactivate project_sync désactive uniquement le plugin cloud', async () => {
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];

    const { deactivate } = useCapabilities();
    await deactivate('project_sync');

    expect(deactivatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
    expect(deactivatePlugin).not.toHaveBeenCalledWith(PROJET_PLUGIN_ID);
  });

  it('deactivate projects désactive aussi les capacités imbriquées', async () => {
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];

    const { deactivate } = useCapabilities();
    await deactivate('projects');

    expect(deactivatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
    expect(deactivatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
  });
});
