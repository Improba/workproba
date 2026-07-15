import { computed, ref, type ComputedRef, type Ref } from 'vue';
import {
  activatePlugin as tauriActivate,
  deactivatePlugin as tauriDeactivate,
  getPluginDataDir as tauriGetDataDir,
  installLocalPlugin as tauriInstallLocal,
  listPlugins as tauriListPlugins,
  uninstallLocalPlugin as tauriUninstallLocal,
  type PluginInfo,
} from './useDesktop';

export const PROJET_PLUGIN_ID = 'workproba.projet';
export const PERSONAS_PLUGIN_ID = 'workproba.personas';
export const BROWSER_PLUGIN_ID = 'workproba.browser';
export const CLOUD_PLUGIN_ID = 'workproba.cloud';

const UPCOMING_PLUGIN_IDS = new Set<string>();

export function isUpcomingPluginId(id: string): boolean {
  return UPCOMING_PLUGIN_IDS.has(id);
}

/** Install local extension: dev builds or explicit VITE_LOCAL_PLUGIN_INSTALL=true. */
export function localPluginInstallAvailable(): boolean {
  return (
    import.meta.env.DEV ||
    import.meta.env.VITE_LOCAL_PLUGIN_INSTALL === 'true'
  );
}

const plugins = ref<PluginInfo[]>([]);
const loading = ref(false);
const loadError = ref<string | null>(null);
let loadedOnce = false;

const activePluginIds = computed(() =>
  plugins.value
    .filter((p) => p.enabledScoped && !isUpcomingPluginId(p.manifest.id))
    .map((p) => p.manifest.id),
);

const isProjetPluginActive = computed(() =>
  activePluginIds.value.includes(PROJET_PLUGIN_ID),
);

const isPersonasPluginActive = computed(() =>
  activePluginIds.value.includes(PERSONAS_PLUGIN_ID),
);

const isBrowserPluginActive = computed(() =>
  activePluginIds.value.includes(BROWSER_PLUGIN_ID),
);

const isCloudPluginActive = computed(() =>
  activePluginIds.value.includes(CLOUD_PLUGIN_ID),
);

export interface UsePluginsReturn {
  plugins: Ref<PluginInfo[]>;
  loading: Ref<boolean>;
  loadError: Ref<string | null>;
  activePluginIds: ComputedRef<string[]>;
  isProjetPluginActive: ComputedRef<boolean>;
  isPersonasPluginActive: ComputedRef<boolean>;
  isBrowserPluginActive: ComputedRef<boolean>;
  isCloudPluginActive: ComputedRef<boolean>;
  refresh: () => Promise<void>;
  activatePlugin: (id: string) => Promise<void>;
  deactivatePlugin: (id: string) => Promise<void>;
  getPluginDataDir: (id: string) => Promise<string | null>;
  installLocalPlugin: (folderPath: string) => Promise<PluginInfo>;
  uninstallLocalPlugin: (id: string) => Promise<void>;
}

export function usePlugins(): UsePluginsReturn {
  async function refresh(): Promise<void> {
    loading.value = true;
    loadError.value = null;
    try {
      const list = await tauriListPlugins();
      plugins.value = list;
      loadedOnce = true;
    } catch (err) {
      loadError.value =
        err instanceof Error ? err.message : 'plugins_load_failed';
      plugins.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (!loadedOnce && !loading.value) {
      await refresh();
    }
  }

  async function activatePlugin(id: string): Promise<void> {
    if (isUpcomingPluginId(id)) {
      throw new Error('plugin_upcoming');
    }
    await tauriActivate(id);
    await refresh();
  }

  async function deactivatePlugin(id: string): Promise<void> {
    await tauriDeactivate(id);
    await refresh();
  }

  async function getPluginDataDir(id: string): Promise<string | null> {
    return tauriGetDataDir(id);
  }

  async function installLocalPlugin(folderPath: string): Promise<PluginInfo> {
    const info = await tauriInstallLocal(folderPath);
    await refresh();
    return info;
  }

  async function uninstallLocalPlugin(id: string): Promise<void> {
    await tauriUninstallLocal(id);
    await refresh();
  }

  void ensureLoaded();

  return {
    plugins,
    loading,
    loadError,
    activePluginIds,
    isProjetPluginActive,
    isPersonasPluginActive,
    isBrowserPluginActive,
    isCloudPluginActive,
    refresh,
    activatePlugin,
    deactivatePlugin,
    getPluginDataDir,
    installLocalPlugin,
    uninstallLocalPlugin,
  };
}
