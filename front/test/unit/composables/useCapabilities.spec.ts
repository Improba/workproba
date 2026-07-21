import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PluginInfo } from '@composables/useDesktop';
import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
  PROJET_PLUGIN_ID,
} from '@composables/usePlugins';
import type { ManagedConnector } from '@services/aiSidecar';

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
const permissionsNetworkImprobaCloud = ref(true);
const settings = ref({
  version: 1,
  providers: [],
  settingsLocked: false,
  settingsMode: 'guided' as const,
  pluginsAllowed: null as string[] | null,
  permissionsNetwork: true,
  permissionsProjectSync: true,
  permissionsNetworkImprobaCloud: true,
});

const openRightPanel = vi.fn();
const openSideChat = vi.fn();
const closeCapabilities = vi.fn();

const isEnrolled = ref(false);
const connectors = ref<ManagedConnector[]>([]);
const initCloud = vi.fn(async () => undefined);
const setManagedConnectorEnabled = vi.fn(async (connectorId: string, enabled: boolean) => {
  connectors.value = connectors.value.map((c) =>
    c.id === connectorId ? { ...c, enabled } : c,
  );
  return true;
});

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
    permissionsNetworkImprobaCloud,
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openRightPanel,
    openSideChat,
    closeCapabilities,
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    isEnrolled,
    connectors,
    init: initCloud,
    setManagedConnectorEnabled,
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
      permissionsNetworkImprobaCloud: true,
    };
    settingsLocked.value = false;
    settingsMode.value = 'guided';
    permissionsNetwork.value = true;
    permissionsProjectSync.value = true;
    permissionsNetworkImprobaCloud.value = true;
    isEnrolled.value = false;
    connectors.value = [];
    activatePlugin.mockClear();
    deactivatePlugin.mockClear();
    openRightPanel.mockClear();
    openSideChat.mockClear();
    closeCapabilities.mockClear();
    initCloud.mockClear();
    setManagedConnectorEnabled.mockClear();
  });

  it('mappe active et available selon les plugins actifs', () => {
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];
    isEnrolled.value = true;

    const { getById } = useCapabilities();

    expect(getById('projects')?.state.kind).toBe('active');
    expect(getById('regards')?.state.kind).toBe('available');
    expect(getById('workproba_cloud')?.state.kind).toBe('active');
  });

  it('projects reste available si le cloud parent n’est pas actif', () => {
    activePluginIds.value = [PROJET_PLUGIN_ID];

    const { getById } = useCapabilities();
    expect(getById('projects')?.state.kind).toBe('available');
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

  it('marque workproba_cloud blocked quand project_sync est désactivé par preset', () => {
    settingsLocked.value = true;
    settings.value.settingsLocked = true;
    settings.value.permissionsProjectSync = false;
    permissionsProjectSync.value = false;

    const { getById } = useCapabilities();
    const cloud = getById('workproba_cloud');

    expect(cloud?.state.kind).toBe('blocked');
    expect(cloud?.state.managedByOrganization).toBe(true);
  });

  it('activateAndOpen projects active le cloud parent puis le plugin projet', async () => {
    const { activateAndOpen } = useCapabilities();
    await activateAndOpen('projects');

    expect(activatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
    expect(activatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(openRightPanel).toHaveBeenCalledWith('workproba.projet:right_panel');
  });

  it('deactivate workproba_cloud désactive aussi la gestion de projet nested', async () => {
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];

    const { deactivate } = useCapabilities();
    await deactivate('workproba_cloud');

    expect(deactivatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(deactivatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
  });

  it('deactivate projects ne désactive pas le cloud', async () => {
    activePluginIds.value = [PROJET_PLUGIN_ID, CLOUD_PLUGIN_ID];

    const { deactivate } = useCapabilities();
    await deactivate('projects');

    expect(deactivatePlugin).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(deactivatePlugin).not.toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
  });

  it('open ouvre le side chat pour regards', () => {
    activePluginIds.value = [PERSONAS_PLUGIN_ID];
    const { open } = useCapabilities();

    open('regards');

    expect(openSideChat).toHaveBeenCalledWith(PERSONAS_PLUGIN_ID);
  });

  it('activateAndOpen workproba_cloud active uniquement le plugin cloud', async () => {
    const { activateAndOpen } = useCapabilities();
    await activateAndOpen('workproba_cloud');

    expect(activatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
    expect(activatePlugin).not.toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(openRightPanel).toHaveBeenCalledWith('workproba.cloud:right_panel');
  });

  it('workproba_cloud est needs_setup si cloud actif mais non enrollé', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = false;

    const { getById } = useCapabilities();
    expect(getById('workproba_cloud')?.state.kind).toBe('needs_setup');
  });

  it('workproba_cloud est active si cloud actif et enrollé', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;

    const { getById } = useCapabilities();
    expect(getById('workproba_cloud')?.state.kind).toBe('active');
  });

  it('open workproba_cloud ouvre l’onglet cloud', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;

    const { open } = useCapabilities();
    open('workproba_cloud');

    expect(openSideChat).not.toHaveBeenCalled();
    expect(openRightPanel).toHaveBeenCalledWith('workproba.cloud:right_panel');
  });

  it('deactivate workproba_cloud désactive uniquement le plugin cloud quand pas d’enfant actif', async () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];

    const { deactivate } = useCapabilities();
    await deactivate('workproba_cloud');

    expect(deactivatePlugin).toHaveBeenCalledWith(CLOUD_PLUGIN_ID);
  });

  it('expose les capacités managées sous workproba_cloud quand enrollé', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [
      { id: 'echo', name: 'Echo', description: 'stub', enabled: true },
      { id: 'ihora', name: 'IHora', description: 'Absences', enabled: true },
      { id: 'ihora.shaped', name: 'IHora stub', description: 'stub', enabled: true },
    ];

    const { capabilities, getById } = useCapabilities();
    const managed = capabilities.value.filter((v) => v.definition.source === 'managed');

    // Mode guidé : echo et ihora.shaped masqués
    expect(managed.map((v) => v.definition.managedConnectorId)).toEqual(['ihora']);
    expect(getById('managed:ihora')?.definition.parentId).toBe('workproba_cloud');
    expect(getById('managed:ihora')?.state.kind).toBe('active');
    expect(getById('managed:ihora')?.state.managedByOrganization).toBe(true);
  });

  it('capacité managée désactivée localement reste available', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [{ id: 'ihora', name: 'IHora', enabled: false }];

    const { getById } = useCapabilities();
    expect(getById('managed:ihora')?.state.kind).toBe('available');
  });

  it('montre aussi echo en mode avancé', () => {
    settingsMode.value = 'advanced';
    settings.value.settingsMode = 'advanced';
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [
      { id: 'echo', name: 'Echo', enabled: true },
      { id: 'ihora', name: 'IHora', enabled: true },
    ];

    const { capabilities } = useCapabilities();
    const ids = capabilities.value
      .filter((v) => v.definition.source === 'managed')
      .map((v) => v.definition.managedConnectorId);
    expect(ids).toEqual(['echo', 'ihora']);
  });

  it('n’expose pas de capacités managées si non enrollé', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = false;
    connectors.value = [{ id: 'ihora', name: 'IHora', enabled: true }];

    const { capabilities } = useCapabilities();
    expect(capabilities.value.some((v) => v.definition.source === 'managed')).toBe(false);
  });

  it('activateAndOpen managée active sans ouvrir de panneau', async () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [{ id: 'ihora', name: 'IHora', enabled: false }];

    const { activateAndOpen } = useCapabilities();
    await activateAndOpen('managed:ihora');

    expect(setManagedConnectorEnabled).toHaveBeenCalledWith('ihora', true);
    expect(closeCapabilities).not.toHaveBeenCalled();
    expect(openRightPanel).not.toHaveBeenCalled();
  });

  it('deactivate d’une capacité managée désactive localement', async () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [{ id: 'ihora', name: 'IHora', enabled: true }];

    const { deactivate } = useCapabilities();
    await deactivate('managed:ihora');

    expect(setManagedConnectorEnabled).toHaveBeenCalledWith('ihora', false);
    expect(deactivatePlugin).not.toHaveBeenCalled();
  });

  it('open d’une capacité managée est un no-op', () => {
    activePluginIds.value = [CLOUD_PLUGIN_ID];
    isEnrolled.value = true;
    connectors.value = [{ id: 'ihora', name: 'IHora', enabled: true }];

    const { open } = useCapabilities();
    open('managed:ihora');

    expect(openRightPanel).not.toHaveBeenCalled();
    expect(openSideChat).not.toHaveBeenCalled();
  });
});
