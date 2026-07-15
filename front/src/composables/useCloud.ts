import { ref, type Ref } from 'vue';
import {
  configCloud,
  fetchCloudStatus,
  syncCloud,
  type CloudStatus,
} from '@services/aiSidecar';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';

const status = ref<CloudStatus | null>(null);
const loading = ref(false);
const syncing = ref(false);
const loadError = ref<string | null>(null);
let pluginDataDir: string | null = null;

export interface UseCloudReturn {
  status: Ref<CloudStatus | null>;
  loading: Ref<boolean>;
  syncing: Ref<boolean>;
  loadError: Ref<string | null>;
  init: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  configure: (mountPath: string) => Promise<boolean>;
  sync: (projectId: string) => Promise<string[]>;
}

export function useCloud(): UseCloudReturn {
  const { getPluginDataDir } = usePlugins();

  async function init(): Promise<void> {
    pluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    await refreshStatus();
  }

  async function refreshStatus(): Promise<void> {
    if (!pluginDataDir) {
      status.value = null;
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      status.value = await fetchCloudStatus(pluginDataDir);
    } catch (err) {
      status.value = null;
      loadError.value = err instanceof Error ? err.message : 'cloud_status_failed';
    } finally {
      loading.value = false;
    }
  }

  async function configure(mountPath: string): Promise<boolean> {
    if (!pluginDataDir || !mountPath.trim()) return false;
    const ok = await configCloud(pluginDataDir, mountPath.trim());
    if (ok) {
      await refreshStatus();
    }
    return ok;
  }

  async function sync(projectId: string): Promise<string[]> {
    if (!pluginDataDir || !projectId) return [];
    const mountPath = status.value?.mount_path ?? '';
    if (!mountPath) return [];
    syncing.value = true;
    loadError.value = null;
    try {
      const result = await syncCloud({
        pluginDataDir,
        projectId,
        mountPath,
      });
      await refreshStatus();
      return result.synced;
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'cloud_sync_failed';
      return [];
    } finally {
      syncing.value = false;
    }
  }

  return {
    status,
    loading,
    syncing,
    loadError,
    init,
    refreshStatus,
    configure,
    sync,
  };
}
