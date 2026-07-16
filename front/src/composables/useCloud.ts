import { computed, ref, type ComputedRef, type Ref } from 'vue';
import {
  configCloud,
  disconnectCloud,
  enrollCloud,
  fetchCloudStatus,
  pullCloud,
  syncCloud,
  syncManagedRegards,
  type CloudPullResult,
  type CloudStatus,
  type CloudSyncRegardsResult,
  type CloudSyncResult,
  type SidecarResult,
} from '@services/aiSidecar';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';

const status = ref<CloudStatus | null>(null);
const loading = ref(false);
const syncing = ref(false);
const pulling = ref(false);
const syncingRegards = ref(false);
const loadError = ref<string | null>(null);
let pluginDataDir: string | null = null;

export interface UseCloudReturn {
  status: Ref<CloudStatus | null>;
  loading: Ref<boolean>;
  syncing: Ref<boolean>;
  pulling: Ref<boolean>;
  syncingRegards: Ref<boolean>;
  loadError: Ref<string | null>;
  /** Cloud enrolled — « projet partagé » product vocabulary (not mount-only). */
  isActive: ComputedRef<boolean>;
  isEnrolled: ComputedRef<boolean>;
  /** Technical sync available: mount folder and/or cloud enrolled. */
  canSync: ComputedRef<boolean>;
  init: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  configure: (mountPath: string) => Promise<boolean>;
  enroll: (opts: {
    baseUrl: string;
    bearerToken?: string;
    joinToken?: string;
  }) => Promise<boolean>;
  disconnect: () => Promise<boolean>;
  sync: (projectId: string) => Promise<SidecarResult<CloudSyncResult>>;
  pull: (projectId: string) => Promise<SidecarResult<CloudPullResult>>;
  syncRegards: () => Promise<SidecarResult<CloudSyncRegardsResult>>;
}

export function useCloud(): UseCloudReturn {
  const { getPluginDataDir } = usePlugins();

  const isEnrolled = computed(() => Boolean(status.value?.enrolled));
  const canSync = computed(() => Boolean(status.value?.configured || status.value?.enrolled));
  const isActive = computed(() => isEnrolled.value);

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
      const result = await fetchCloudStatus(pluginDataDir);
      if (!result.ok) {
        status.value = null;
        loadError.value = result.error;
        return;
      }
      status.value = result.data;
    } catch (err) {
      status.value = null;
      loadError.value = err instanceof Error ? err.message : 'cloud_status_failed';
    } finally {
      loading.value = false;
    }
  }

  async function configure(mountPath: string): Promise<boolean> {
    if (!pluginDataDir || !mountPath.trim()) return false;
    loadError.value = null;
    const result = await configCloud(pluginDataDir, mountPath.trim());
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    return result.data;
  }

  async function enroll(opts: {
    baseUrl: string;
    bearerToken?: string;
    joinToken?: string;
  }): Promise<boolean> {
    if (!pluginDataDir || !opts.baseUrl.trim()) return false;
    const hasJoin = Boolean(opts.joinToken?.trim());
    const hasBearer = Boolean(opts.bearerToken?.trim());
    if (!hasJoin && !hasBearer) return false;
    loadError.value = null;
    const result = await enrollCloud({
      pluginDataDir,
      baseUrl: opts.baseUrl.trim(),
      bearerToken: opts.bearerToken?.trim(),
      joinToken: opts.joinToken?.trim(),
    });
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    return result.data.authenticated;
  }

  async function disconnect(): Promise<boolean> {
    if (!pluginDataDir) return false;
    loadError.value = null;
    const result = await disconnectCloud(pluginDataDir);
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    return result.data;
  }

  async function sync(projectId: string): Promise<SidecarResult<CloudSyncResult>> {
    if (!pluginDataDir || !projectId) {
      return { ok: false, error: 'cloud_sync_missing_context' };
    }
    if (!canSync.value) {
      return { ok: false, error: 'cloud_not_configured' };
    }
    syncing.value = true;
    loadError.value = null;
    try {
      const result = await syncCloud({
        pluginDataDir,
        projectId,
        mountPath: status.value?.mount_path ?? undefined,
      });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      await refreshStatus();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_sync_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      syncing.value = false;
    }
  }

  async function pull(projectId: string): Promise<SidecarResult<CloudPullResult>> {
    if (!pluginDataDir || !projectId) {
      return { ok: false, error: 'cloud_pull_missing_context' };
    }
    if (!status.value?.enrolled) {
      return { ok: false, error: 'cloud_not_enrolled' };
    }
    pulling.value = true;
    loadError.value = null;
    try {
      const result = await pullCloud({ pluginDataDir, projectId });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      await refreshStatus();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_pull_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      pulling.value = false;
    }
  }

  async function syncRegards(): Promise<SidecarResult<CloudSyncRegardsResult>> {
    if (!pluginDataDir) {
      return { ok: false, error: 'cloud_sync_regards_missing_context' };
    }
    if (!status.value?.enrolled) {
      return { ok: false, error: 'cloud_not_enrolled' };
    }
    syncingRegards.value = true;
    loadError.value = null;
    try {
      const result = await syncManagedRegards({
        pluginDataDir,
        orgId: status.value.org_id ?? undefined,
      });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_sync_regards_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      syncingRegards.value = false;
    }
  }

  return {
    status,
    loading,
    syncing,
    pulling,
    syncingRegards,
    loadError,
    isActive,
    isEnrolled,
    canSync,
    init,
    refreshStatus,
    configure,
    enroll,
    disconnect,
    sync,
    pull,
    syncRegards,
  };
}
